"""
Street View Camera Overrides Endpoints for CFR EVO API Gateway.
Provides endpoints for retrieving and setting Street View camera headings, pitch, and FOV parameters.
"""
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

try:
    from backend.api.database import get_db
    from backend.api.models import ParcelModel
    from backend.api.schemas import StreetViewOverrideSchema, ParcelCameraOverrideSchema
    from backend.api.routers.parcels import _clean_streetview_address, save_parcel_streetview
except ModuleNotFoundError:
    from api.database import get_db
    from api.models import ParcelModel
    from api.schemas import StreetViewOverrideSchema, ParcelCameraOverrideSchema
    from api.routers.parcels import _clean_streetview_address, save_parcel_streetview

router = APIRouter(tags=["streetview"])


@router.get("/api/streetview-overrides")
def get_all_streetview_overrides(db: Session = Depends(get_db)):
    """Retrieves all Street View camera orientation overrides as an uppercase-address-indexed dictionary."""
    records = db.query(ParcelModel).filter(ParcelModel.streetview_heading.isnot(None)).all()
    out = {}
    for r in records:
        if r.address:
            out[r.address.upper()] = {
                "lat": r.front_lat or r.lat,
                "lng": r.front_lng or r.lng,
                "heading": r.streetview_heading,
                "pitch": r.streetview_pitch,
                "fov": r.streetview_fov
            }
    return out


@router.get("/api/streetview-overrides/{address}")
def get_streetview_override(address: str, db: Session = Depends(get_db)):
    """Retrieves the Street View camera override for a specific address."""
    clean_addr = _clean_streetview_address(address)
    raw_upper = address.strip().upper()
    addr_norm = address.strip().lower()

    p = db.query(ParcelModel).filter(
        (ParcelModel.address == clean_addr) |
        (ParcelModel.address == raw_upper) |
        (ParcelModel.address_normalized == addr_norm) |
        (ParcelModel.gis_id == address.strip())
    ).first()

    if not p and clean_addr:
        p = db.query(ParcelModel).filter(ParcelModel.address.ilike(f"%{clean_addr}%")).first()

    if not p or p.streetview_heading is None:
        raise HTTPException(status_code=404, detail="Streetview override not found")

    return {
        "address": p.address or address,
        "clean_address": p.address or address,
        "front_lat": p.front_lat or 0.0,
        "front_lng": p.front_lng or 0.0,
        "heading": p.streetview_heading,
        "pitch": p.streetview_pitch,
        "fov": p.streetview_fov,
        "lat": p.front_lat or p.lat or 0.0,
        "lng": p.front_lng or p.lng or 0.0
    }


@router.post("/api/streetview-overrides")
def save_streetview_override(payload: StreetViewOverrideSchema, db: Session = Depends(get_db)):
    """Saves a Street View camera override for an address."""
    target_address = payload.address or payload.clean_address
    res = save_parcel_streetview(
        ParcelCameraOverrideSchema(
            address=target_address,
            clean_address=target_address,
            front_lat=payload.front_lat,
            front_lng=payload.front_lng,
            heading=payload.heading,
            pitch=payload.pitch,
            fov=payload.fov
        ),
        db=db
    )
    return {
        "status": "success",
        "address": target_address,
        "clean_address": target_address,
        "front_lat": payload.front_lat,
        "front_lng": payload.front_lng,
        "heading": payload.heading,
        "pitch": payload.pitch,
        "fov": payload.fov,
        "parcel": res.get("parcel")
    }


# Aliases for /api/streetview/override endpoints
@router.get("/api/streetview/override")
def get_all_streetview_overrides_alias(db: Session = Depends(get_db)):
    return get_all_streetview_overrides(db)


@router.get("/api/streetview/override/{address}")
def get_streetview_override_alias(address: str, db: Session = Depends(get_db)):
    return get_streetview_override(address, db)


@router.post("/api/streetview/override")
def save_streetview_override_alias(payload: StreetViewOverrideSchema, db: Session = Depends(get_db)):
    return save_streetview_override(payload, db)
