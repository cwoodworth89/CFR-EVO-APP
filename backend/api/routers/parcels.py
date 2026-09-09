"""
Parcel & GIS Metadata Endpoints for CFR EVO API Gateway.
Provides municipal property lookups, autocomplete search, bounding-box spatial queries,
and Street View camera overrides on Coquitlam cadastral parcels.
"""
import re
import json
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

try:
    from backend.api.database import get_db
    from backend.api.models import ParcelModel
    from backend.api.schemas import ParcelCameraOverrideSchema, ParcelEntranceSchema
except ModuleNotFoundError:
    from api.database import get_db
    from api.models import ParcelModel
    from api.schemas import ParcelCameraOverrideSchema

router = APIRouter(prefix="/api/parcels", tags=["parcels"])


def _clean_streetview_address(addr: str) -> str:
    """Normalizes address strings, removing municipal suffixes and standardizing street types."""
    if not addr:
        return ""
    s = addr.upper()
    s = s.strip(' ,.-')
    if not s:
        return ""
    s = re.sub(r'(^|\b|,)\s*(COQUITLAM|PORT COQUITLAM|PORT MOODY|BC|BRITISH COLUMBIA)\b.*$', '', s, flags=re.IGNORECASE)
    s = s.strip(' ,.-')
    s = re.sub(r'^\s*(?:UNIT|APT|STE|SUITE|#)\.?\s*#?\s*\d+[\w-]*[,\-\s]+', '', s, flags=re.IGNORECASE)
    s = re.sub(r'[,\-\s]+\s*(?:UNIT|APT|STE|SUITE|#)\.?\s*#?\s*\d+[\w-]*[,\-\s]*$', '', s, flags=re.IGNORECASE)
    s = s.strip(' ,.-')
    s = re.sub(r'\bAVE?\b', 'AVE', s)
    s = re.sub(r'\bRD?\b', 'RD', s)
    s = re.sub(r'\bST?\b', 'ST', s)
    s = re.sub(r'\bDR?\b', 'DR', s)
    s = re.sub(r'\bHWY?\b', 'HIGHWAY', s)
    s = re.sub(r'\bBLVD?\b', 'BLVD', s)
    s = re.sub(r'\bWAY\b', 'WAY', s)
    s = re.sub(r'\bCRT?\b', 'CRT', s)
    s = re.sub(r'\bPL?\b', 'PL', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip(' ,.-')


def _rings_from_geojson(geojson) -> list:
    """The parcel outline as rings of [lng, lat] from a GeoJSON string; [] when absent.

    The same shape the dispatch resolver puts in a call's `target.rings`
    (address_resolver._extract_rings), so the workstation search can draw the parcel the
    way the kiosk does (operator, 2026-09-08). The geometry is PostGIS `geom`, not a model
    column, so the caller fetches it with ST_AsGeoJSON.
    """
    try:
        geom = json.loads(geojson) if isinstance(geojson, str) else geojson
        if not geom:
            return []
        gtype = geom.get("type")
        if gtype == "Polygon":
            return geom.get("coordinates", [])
        if gtype == "MultiPolygon":
            return [ring for poly in geom.get("coordinates", []) for ring in poly]
    except Exception:  # noqa: BLE001 -- a malformed geometry draws nothing; it does not break the lookup
        pass
    return []


def _parcel_geojson(db: Session, parcel_id) -> str | None:
    try:
        return db.execute(text("SELECT ST_AsGeoJSON(geom) FROM public.parcels WHERE id = :id"), {"id": parcel_id}).scalar()
    except Exception as e:  # noqa: BLE001
        logging.warning("Parcel geometry unavailable for id %s: %s", parcel_id, e)
        return None


def serialize_parcel(p: ParcelModel, rings=None) -> dict:
    """Serializes ParcelModel SQLAlchemy instance to dictionary."""
    return {
        "rings": rings or [],
        "id": p.id,
        "parcel_uuid": str(p.parcel_uuid) if p.parcel_uuid else None,
        "gis_id": p.gis_id,
        "address": p.address,
        "clean_address": p.address,  # Backward compatibility
        "full_address": p.address,
        "house": p.house,
        "street": p.street,
        "streettype": p.streettype,
        "unit": p.unit,
        "unittype": p.unittype,
        "postal": p.postal,
        "block": p.block,
        "plan": p.plan,
        "lot": p.lot,
        "legaldesc": p.legaldesc,
        "folio": p.folio,
        "zonetype1": p.zonetype1,
        "units": p.units,
        "status": p.status,
        "zone_id": p.zone_id,
        "lat": p.centroid_lat,
        "lng": p.centroid_lng,
        "front_lat": p.front_lat,
        "front_lng": p.front_lng,
        "entrance_lat": p.entrance_lat,
        "entrance_lng": p.entrance_lng,
        "entrance_note": p.entrance_note,
        "entrance_set_by": p.entrance_set_by,
        "entrance_set_at": p.entrance_set_at.isoformat() if p.entrance_set_at else None,
        "streetview_heading": p.streetview_heading,
        "streetview_pitch": p.streetview_pitch,
        "streetview_fov": p.streetview_fov,
        "streetview_pano_id": p.streetview_pano_id,
        "lock_box_notes": p.lock_box_notes,
        "hazard_notes": p.hazard_notes,
        "pre_plan_pdf_url": p.pre_plan_pdf_url,
        "construction_type": p.construction_type,
        "floor_count": p.floor_count,
        "is_pa_page": p.is_pa_page,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        "heading": p.streetview_heading,
        "pitch": p.streetview_pitch,
        "fov": p.streetview_fov
    }


@router.get("/lookup")
def lookup_parcel(query: str, db: Session = Depends(get_db)):
    """Searches for a parcel matching address string or GIS ID."""
    if not query or not query.strip():
        return {"found": False, "parcel": None}

    clean_addr = _clean_streetview_address(query)
    raw_upper = query.strip().upper()
    addr_norm = query.strip().lower()

    p = db.query(ParcelModel).filter(
        (ParcelModel.address == clean_addr) |
        (ParcelModel.address == raw_upper) |
        (ParcelModel.address_normalized == addr_norm) |
        (ParcelModel.gis_id == query.strip())
    ).first()

    if not p and clean_addr:
        p = db.query(ParcelModel).filter(ParcelModel.address.ilike(f"%{clean_addr}%")).first()

    if p:
        return {
            "found": True,
            "parcel": serialize_parcel(p, rings=_rings_from_geojson(_parcel_geojson(db, p.id)))
        }

    return {"found": False, "parcel": None}


@router.get("/search")
def search_parcels(q: str = Query(..., min_length=2), limit: int = 25, db: Session = Depends(get_db)):
    """Fast local autocomplete search against 65,400 ingested municipal parcels."""
    clean_q = q.strip().lower()
    results = db.query(ParcelModel).filter(
        (ParcelModel.address_normalized.ilike(f"%{clean_q}%")) |
        (ParcelModel.address.ilike(f"%{clean_q}%"))
    ).limit(limit).all()

    return {
        "count": len(results),
        "results": [
            {
                "id": p.id,
                "address": p.address,
                "house": p.house,
                "street": p.street,
                "streettype": p.streettype,
                "unit": p.unit,
                "zone_id": p.zone_id,
                "lat": p.centroid_lat,
                "lng": p.centroid_lng,
                "front_lat": p.front_lat or p.centroid_lat,
                "front_lng": p.front_lng or p.centroid_lng,
            }
            for p in results
        ]
    }


@router.get("/bbox")
def get_parcels_in_bbox(
    min_lat: float = Query(..., description="South bound latitude"),
    min_lng: float = Query(..., description="West bound longitude"),
    max_lat: float = Query(..., description="North bound latitude"),
    max_lng: float = Query(..., description="East bound longitude"),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Retrieves parcels situated within a geographic bounding box."""
    parcels = db.query(ParcelModel).filter(
        ParcelModel.centroid_lat >= min_lat,
        ParcelModel.centroid_lat <= max_lat,
        ParcelModel.centroid_lng >= min_lng,
        ParcelModel.centroid_lng <= max_lng
    ).limit(limit).all()

    return {
        "count": len(parcels),
        "parcels": [serialize_parcel(p) for p in parcels]
    }


@router.get("/{parcel_id}")
def get_parcel_by_id(parcel_id: str, db: Session = Depends(get_db)):
    """Retrieves a single parcel by internal integer ID or GIS ID."""
    p = None
    if parcel_id.isdigit():
        p = db.query(ParcelModel).filter(ParcelModel.id == int(parcel_id)).first()
    if not p:
        p = db.query(ParcelModel).filter(ParcelModel.gis_id == parcel_id).first()

    if not p:
        raise HTTPException(status_code=404, detail="Parcel not found")

    return {"found": True, "parcel": serialize_parcel(p)}


@router.post("/streetview")
def save_parcel_streetview(payload: ParcelCameraOverrideSchema, db: Session = Depends(get_db)):
    """Saves or updates Street View camera orientation parameters for a municipal parcel."""
    raw_target = (payload.address or payload.clean_address or payload.gis_id or "").strip()
    if not raw_target:
        raise HTTPException(status_code=400, detail="address or gis_id required")

    clean_addr = _clean_streetview_address(raw_target)
    if not clean_addr:
        raise HTTPException(status_code=400, detail="Address is empty or invalid")

    raw_upper = raw_target.upper()
    addr_norm = raw_target.lower()

    try:
        p = db.query(ParcelModel).filter(
            (ParcelModel.address == clean_addr) |
            (ParcelModel.address == raw_upper) |
            (ParcelModel.address_normalized == addr_norm) |
            (ParcelModel.gis_id == raw_target)
        ).first()

        if not p:
            p = ParcelModel(
                gis_id=payload.gis_id or clean_addr,
                address=clean_addr,
                address_normalized=clean_addr.lower(),
                front_lat=payload.front_lat,
                front_lng=payload.front_lng,
                # centroid_* is deliberately NOT set. This row is created for an address
                # the municipal parcel data does not contain, so there is no polygon and
                # therefore no centroid. It used to be filled from front_lat -- inventing
                # a "centre of the property" that is actually a point on the road. Same
                # class as punch-list #50, in the other direction: copying one of the
                # three positions into another.
                #
                # NULL is correct and costs nothing: the resolver order is
                # entrance -> front -> centroid, and front_lat is set here, so the
                # centroid is never reached (CLAUDE.md §6.1).
                streetview_heading=payload.heading,
                streetview_pitch=payload.pitch,
                streetview_fov=payload.fov,
                streetview_pano_id=payload.pano_id or None
            )
            db.add(p)
        else:
            p.streetview_heading = payload.heading
            p.streetview_pitch = payload.pitch
            p.streetview_fov = payload.fov
            p.streetview_pano_id = payload.pano_id or None
            if payload.front_lat is not None:
                p.front_lat = payload.front_lat
            if payload.front_lng is not None:
                p.front_lng = payload.front_lng

        db.commit()
        db.refresh(p)
    except IntegrityError:
        db.rollback()
        p = db.query(ParcelModel).filter(
            (ParcelModel.address == clean_addr) |
            (ParcelModel.address == raw_upper) |
            (ParcelModel.address_normalized == addr_norm) |
            (ParcelModel.gis_id == raw_target)
        ).first()

        if p:
            p.streetview_heading = payload.heading
            p.streetview_pitch = payload.pitch
            p.streetview_fov = payload.fov
            if payload.front_lat is not None:
                p.front_lat = payload.front_lat
            if payload.front_lng is not None:
                p.front_lng = payload.front_lng
        else:
            p = ParcelModel(
                gis_id=payload.gis_id or clean_addr,
                address=clean_addr,
                address_normalized=clean_addr.lower(),
                front_lat=payload.front_lat,
                front_lng=payload.front_lng,
                # centroid_* is deliberately NOT set. This row is created for an address
                # the municipal parcel data does not contain, so there is no polygon and
                # therefore no centroid. It used to be filled from front_lat -- inventing
                # a "centre of the property" that is actually a point on the road. Same
                # class as punch-list #50, in the other direction: copying one of the
                # three positions into another.
                #
                # NULL is correct and costs nothing: the resolver order is
                # entrance -> front -> centroid, and front_lat is set here, so the
                # centroid is never reached (CLAUDE.md §6.1).
                streetview_heading=payload.heading,
                streetview_pitch=payload.pitch,
                streetview_fov=payload.fov
            )
            db.add(p)

        db.commit()
        db.refresh(p)

    parcel_dict = serialize_parcel(p)
    return {
        "status": "success",
        "parcel": parcel_dict
    }


@router.post("/entrance")
def set_parcel_entrance(payload: ParcelEntranceSchema, db: Session = Depends(get_db)):
    """Sets, or clears, the operator-verified arrival point of one parcel (punch-list #49).

    One parcel per call, attributed, never bulk: these are per-site human judgements. With
    lat and lng both null the point is cleared and the note kept as the record of why. The
    resolver reads entrance -> front -> centroid, so the next dispatch to this address, and
    every unit behind a base site, arrives here.
    """
    from datetime import datetime, timezone

    set_by = (payload.set_by or "").strip()
    if not set_by:
        raise HTTPException(status_code=400, detail="set_by is required: every override is attributable")
    target = (payload.gis_id or payload.address or "").strip()
    if not target:
        raise HTTPException(status_code=400, detail="address or gis_id required")
    if (payload.lat is None) != (payload.lng is None):
        raise HTTPException(status_code=400, detail="lat and lng go together")

    clean_addr = _clean_streetview_address(target)
    p = db.query(ParcelModel).filter(
        (ParcelModel.gis_id == target) |
        (ParcelModel.address == clean_addr) |
        (ParcelModel.address == target.upper()) |
        (ParcelModel.address_normalized == target.lower())
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail=f"No parcel for {target!r}; an arrival point needs a parcel to belong to")

    p.entrance_lat = payload.lat
    p.entrance_lng = payload.lng
    p.entrance_note = (payload.note or "").strip() or None
    p.entrance_set_by = set_by
    p.entrance_set_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(p)
    logging.info("Arrival point %s for %s by %s: %s",
                 "cleared" if payload.lat is None else f"set to {payload.lat:.6f},{payload.lng:.6f}",
                 p.address, set_by, p.entrance_note or "(no note)")
    return {"status": "success", "parcel": serialize_parcel(p)}
