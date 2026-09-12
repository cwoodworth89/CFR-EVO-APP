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
    from backend.api.routers.parcels import _address_row, save_parcel_streetview
    from backend.api.routers.auth import require_admin
except ModuleNotFoundError:
    from api.database import get_db
    from api.models import ParcelModel
    from api.schemas import StreetViewOverrideSchema, ParcelCameraOverrideSchema
    from api.routers.parcels import _address_row, save_parcel_streetview
    from api.routers.auth import require_admin

router = APIRouter(tags=["streetview"])


@router.get("/api/streetview-overrides")
def get_all_streetview_overrides(db: Session = Depends(get_db)):
    """Retrieves all Street View camera orientation overrides as an uppercase-address-indexed dictionary."""
    records = db.query(ParcelModel).filter(ParcelModel.streetview_heading.isnot(None)).all()
    out = {}
    for r in records:
        if r.address:
            out[r.address.upper()] = {
                # front point first, centroid as the fallback. `r.lat` / `r.lng` here until
                # 2026-08-31: the columns were renamed to centroid_lat/centroid_lng and this
                # call site was missed, so every request to this endpoint raised
                # AttributeError and returned 500.
                "lat": r.front_lat or r.centroid_lat,
                "lng": r.front_lng or r.centroid_lng,
                "heading": r.streetview_heading,
                "pitch": r.streetview_pitch,
                "fov": r.streetview_fov,
                "pano_id": r.streetview_pano_id
            }
    return out


@router.get("/api/streetview-overrides/{address}")
def get_streetview_override(address: str, db: Session = Depends(get_db)):
    """Retrieves the Street View camera override for a specific address."""
    # Same row rule as the entrance card and the console lookup, so a site's saved camera
    # is read back from the row it was written to (#77).
    p = _address_row(db, address)

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
        "pano_id": p.streetview_pano_id,
        "lat": p.front_lat or p.centroid_lat or 0.0,
        "lng": p.front_lng or p.centroid_lng or 0.0
    }


@router.post("/api/streetview-overrides")
def save_streetview_override(payload: StreetViewOverrideSchema, db: Session = Depends(get_db),
                             _admin: dict = Depends(require_admin)):
    """Saves a Street View camera override for an address. Admin-gated over HTTP, the same
    gate as /api/parcels/streetview: an ungated alias would be a way around it."""
    target_address = payload.address or payload.clean_address
    res = save_parcel_streetview(
        ParcelCameraOverrideSchema(
            address=target_address,
            clean_address=target_address,
            # The legacy field name for the camera position. It no longer writes the
            # parcel's frontage (punch list #78); passing it as view_* says so.
            view_lat=payload.front_lat,
            view_lng=payload.front_lng,
            heading=payload.heading,
            pitch=payload.pitch,
            fov=payload.fov,
            pano_id=payload.pano_id
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
def save_streetview_override_alias(payload: StreetViewOverrideSchema, db: Session = Depends(get_db),
                                   _admin: dict = Depends(require_admin)):
    return save_streetview_override(payload, db, _admin)
