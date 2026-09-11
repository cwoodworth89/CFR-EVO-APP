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
from sqlalchemy import text, and_, func, or_
from sqlalchemy.orm import Session, aliased
from sqlalchemy.exc import IntegrityError

try:
    from backend.api.database import get_db
    from backend.api.models import ParcelModel
    from backend.api.schemas import ParcelCameraOverrideSchema, ParcelEntranceSchema
    from backend.api.routers.auth import require_admin
except ModuleNotFoundError:
    from api.database import get_db
    from api.models import ParcelModel
    from api.schemas import ParcelCameraOverrideSchema
    from api.routers.auth import require_admin

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


# The canonical row order for "which row does this address mean".
#
# public.parcels is one row per ADDRESS, not per parcel, so an address match can return many
# rows and neither key picks between them: 43,842 rows (62 %) share a gis_id with a different
# address, and 2,170 addresses are themselves duplicated (measured on the kiosk 2026-09-10).
#
# The base_site row is the answer wherever one exists -- one per multi-parcel property, unique
# per address via the partial index parcels_base_site_address_uniq, carrying the operator's
# entrance point, lockbox and hazard notes, and speaking for every City row at that address
# (docs/briefings/base_site_rows_decision.md). Falling through to `id` keeps the choice
# deterministic for the 26,531 single-parcel addresses, which have no base_site row and are
# therefore unaffected.
_BASE_SITE_FIRST = (ParcelModel.is_base_site.desc(), ParcelModel.id)


def _address_row(db: Session, raw: str, *, fuzzy: bool = True) -> Optional[ParcelModel]:
    """The one row an address means: the property's base_site row where it has one.

    Every address -> row lookup in this API goes through here, so the entrance card, the
    Street View override and the console lookup cannot drift apart again. They did: each
    built the same four-condition OR and took `.first()` with no ordering, so the same
    address resolved to a different row depending on which endpoint asked. The operator's
    Coquitlam Centre arrival point was answered 200 OK and written to a suite row, while the
    dispatched address "2929 Barnet Hwy" kept none -- saved, and never read (punch-list #77,
    operator 2026-09-10: "still didn't save").

    `fuzzy=False` on write paths: a partial address match must not decide which row gets
    written, only which row gets shown.
    """
    raw_target = (raw or "").strip()
    if not raw_target:
        return None

    clean_addr = _clean_streetview_address(raw_target)
    p = db.query(ParcelModel).filter(
        (ParcelModel.address == clean_addr) |
        (ParcelModel.address == raw_target.upper()) |
        (ParcelModel.address_normalized == raw_target.lower()) |
        (ParcelModel.gis_id == raw_target)
    ).order_by(*_BASE_SITE_FIRST).first()

    if not p and fuzzy and clean_addr:
        p = db.query(ParcelModel).filter(
            ParcelModel.address.ilike(f"%{clean_addr}%")
        ).order_by(*_BASE_SITE_FIRST).first()

    return p


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
        # Whether this row is the one that speaks for the property (#77). The entrance card
        # writes to whatever `id` it was handed, so the UI can say which row it is about.
        "is_base_site": p.is_base_site,
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

    # The row this lookup returns is the row the entrance card will name in its save
    # (`parcel_id`), so it has to be the same row the resolver routes to (#77).
    p = _address_row(db, query)

    if p:
        return {
            "found": True,
            "parcel": serialize_parcel(p, rings=_rings_from_geojson(_parcel_geojson(db, p.id)))
        }

    return {"found": False, "parcel": None}


@router.get("/search")
def search_parcels(q: str = Query(..., min_length=2), limit: int = 25, db: Session = Depends(get_db)):
    """Autocomplete over one row per PROPERTY: 29,420 of the 71,212 rows.

    Operator ruling, 2026-09-10: *"I only want the base building showing in the search bar.
    No suites or other rows."*

    Filtering to `is_base_site` alone would have been wrong and badly so -- those rows exist
    only for multi-parcel properties, so it would have hidden **27,749 single-parcel
    addresses**, which is most of the city's housing. A property is therefore its base_site
    row where it has one, and its single City row where it does not:

        1,671  base_site rows          (multi-parcel properties)
      + 27,749 lone City rows          (single-parcel; no base row exists for them)
      = 29,420 searchable              41,792 suites and duplicate rows hidden

    Measured 2026-09-10: 2929 Barnet Hwy collapses 236 rows to 1, 3000 Riverbend Dr 258 to 1,
    and 1176/1180/1190 Lansdowne Dr 109 rows to 3 -- one per building, because base rows are
    grouped on (house, street, streettype). Appian St, entirely single-family, keeps all 49.
    The 8 lone rows that do carry a unit are kept: they are the only row for their address,
    and dropping them would make those addresses unfindable (§6.1).

    Written as a LEFT JOIN anti-join rather than `NOT EXISTS`. Both are correct; the
    correlated form inflated the planner's cost estimate enough to turn on JIT and ran in
    632 ms against a 105 ms baseline, where this runs in 124 ms (EXPLAIN ANALYZE, kiosk,
    2026-09-10).
    """
    clean_q = q.strip().lower()
    # base_site FIRST, the same rule as _address_row and the resolver (#77). This list had no
    # ORDER BY at all, so "1176 Lansdowne" returned City row 131890 at the top and the
    # property's base row 200859 not at all inside the limit. The operator set an arrival
    # point on the base row, came back through this search, landed on the City row and saw an
    # empty field -- "1176 got set, and then it lost it" (2026-09-10). The ruling was never
    # lost; the search handed back a different row than the one it had written to.
    base = aliased(ParcelModel)
    results = (
        db.query(ParcelModel)
        .outerjoin(base, and_(
            base.is_base_site.is_(True),
            base.house == ParcelModel.house,
            base.street == ParcelModel.street,
            # streettype is nullable on both sides, so `=` would drop the NULL pairs.
            func.coalesce(base.streettype, "") == func.coalesce(ParcelModel.streettype, ""),
        ))
        .filter(
            or_(ParcelModel.address_normalized.ilike(f"%{clean_q}%"),
                ParcelModel.address.ilike(f"%{clean_q}%")),
            # the property's own row: the base row, or a row no base row speaks for
            or_(ParcelModel.is_base_site.is_(True), base.id.is_(None)),
        )
        .order_by(*_BASE_SITE_FIRST)
        .limit(limit)
        .all()
    )

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
                # The base row and a City row can carry the IDENTICAL address text with both
                # units null -- "1176 Lansdowne Dr" is two rows, 200859 and 131890 -- so the
                # list cannot distinguish them without this. Returned so the UI can mark which
                # one speaks for the property; ordering already puts it first.
                "is_base_site": p.is_base_site,
                "has_arrival_point": p.entrance_lat is not None,
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
def save_parcel_streetview(payload: ParcelCameraOverrideSchema, db: Session = Depends(get_db),
                           _admin: dict = Depends(require_admin)):
    """Saves or updates Street View camera orientation parameters for a municipal parcel.

    Admin-gated over HTTP (require_admin): an operator ruling, not a crew control."""
    raw_target = (payload.address or payload.clean_address or payload.gis_id or "").strip()
    if not raw_target:
        raise HTTPException(status_code=400, detail="address or gis_id required")

    clean_addr = _clean_streetview_address(raw_target)
    if not clean_addr:
        raise HTTPException(status_code=400, detail="Address is empty or invalid")

    try:
        # Same row rule as the entrance save and the console lookup: a site's Street View
        # belongs on its base_site row, not on whichever suite the query happened to hit.
        p = _address_row(db, raw_target, fuzzy=False)

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
        p = _address_row(db, raw_target, fuzzy=False)

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


def _entrance_target(db: Session, payload) -> ParcelModel:
    """The one parcel row an arrival point belongs to, or an error saying why it is unclear.

    **public.parcels is one row per ADDRESS, not per parcel.** Measured on the kiosk database
    2026-09-10: 71,212 rows over 27,855 gis_ids; 43,842 rows (62 %) share a gis_id with a
    different address, and 2,170 addresses are themselves duplicated. So neither key
    identifies a row.

    Coquitlam Centre's gis_id covers **235** suites, not 1,671. The 1,671 figure this
    docstring used to carry is the number of rows with **no** gis_id, and those are not an
    accident: they are the CFR-owned base_site rows, one per multi-parcel property. The
    base row for `2929 Barnet Hwy` is one of them, which is why a gis_id-keyed search could
    never reach it.

    This endpoint used to build `target = gis_id or address` and OR four conditions together
    with `.first()`. With a gis_id supplied that searched by gis_id alone and returned an
    arbitrary member of the group: the operator's Coquitlam Centre arrival point was answered
    200 OK and written to "2929 Barnet Hwy 1202" while the dispatched address, "2929 Barnet
    Hwy", kept none -- so the ruling was saved and never used (operator, 2026-09-10: "still
    didn't save").

    Order now: the row id if the caller has one (the lookup returns it), then an exact address,
    then a gis_id that names exactly one row. An ambiguous match is refused rather than
    guessed, because writing a ruling to an arbitrary suite is worse than not writing it
    (CLAUDE.md s6.1).
    """
    if payload.parcel_id is not None:
        p = db.query(ParcelModel).filter(ParcelModel.id == payload.parcel_id).first()
        if not p:
            raise HTTPException(status_code=404, detail=f"No parcel row with id {payload.parcel_id}")
        return p

    address = (payload.address or "").strip()
    if address:
        clean_addr = _clean_streetview_address(address)
        rows = db.query(ParcelModel).filter(
            (ParcelModel.address == clean_addr) |
            (ParcelModel.address == address.upper()) |
            (ParcelModel.address_normalized == address.lower())
        ).all()
        if len(rows) == 1:
            return rows[0]
        if len(rows) > 1:
            # Not ambiguous if one of them is the property's base_site row: that row exists
            # precisely to be the address's master, is unique per address, and is what the
            # resolver now reads. Two rows are addressed exactly "2929 Barnet Hwy" and this
            # is what tells them apart (#77).
            base = [r for r in rows if r.is_base_site]
            if len(base) == 1:
                return base[0]

            # Duplicated address: the gis_id the caller also sent picks between them.
            gid = (payload.gis_id or "").strip()
            narrowed = [r for r in rows if gid and r.gis_id == gid]
            if len(narrowed) == 1:
                return narrowed[0]
            raise HTTPException(
                status_code=409,
                detail=f"{len(rows)} parcel rows are addressed {address!r}; send parcel_id to say which",
            )

    gis_id = (payload.gis_id or "").strip()
    if gis_id:
        rows = db.query(ParcelModel).filter(ParcelModel.gis_id == gis_id).all()
        if len(rows) == 1:
            return rows[0]
        if len(rows) > 1:
            raise HTTPException(
                status_code=409,
                detail=(f"gis_id {gis_id!r} covers {len(rows)} addresses (a multi-unit site); "
                        "send parcel_id, or the address, to say which one"),
            )

    target = payload.address or payload.gis_id
    raise HTTPException(status_code=404,
                        detail=f"No parcel for {target!r}; an arrival point needs a parcel to belong to")


@router.post("/entrance")
def set_parcel_entrance(payload: ParcelEntranceSchema, db: Session = Depends(get_db),
                        _admin: dict = Depends(require_admin)):
    """Sets, or clears, the operator-verified arrival point of one parcel (punch-list #49).
    Admin-gated over HTTP (require_admin): an operator ruling, not a crew control.

    One parcel per call, attributed, never bulk: these are per-site human judgements. With
    lat and lng both null the point is cleared and the note kept as the record of why. The
    resolver reads entrance -> front -> centroid, so the next dispatch to this address, and
    every unit behind a base site, arrives here.
    """
    from datetime import datetime, timezone

    set_by = (payload.set_by or "").strip()
    if not set_by:
        raise HTTPException(status_code=400, detail="set_by is required: every override is attributable")
    if payload.parcel_id is None and not (payload.address or payload.gis_id or "").strip():
        raise HTTPException(status_code=400, detail="parcel_id, address or gis_id required")
    if (payload.lat is None) != (payload.lng is None):
        raise HTTPException(status_code=400, detail="lat and lng go together")

    p = _entrance_target(db, payload)

    p.entrance_lat = payload.lat
    p.entrance_lng = payload.lng
    p.entrance_note = (payload.note or "").strip() or None
    p.entrance_set_by = set_by
    p.entrance_set_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(p)
    logging.info("Arrival point %s for %s (id %s, gis %s) by %s: %s",
                 "cleared" if payload.lat is None else f"set to {payload.lat:.6f},{payload.lng:.6f}",
                 p.address, p.id, p.gis_id, set_by, p.entrance_note or "(no note)")
    return {"status": "success", "parcel": serialize_parcel(p)}
