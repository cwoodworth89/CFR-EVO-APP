"""
Emergency Vehicle Routing Endpoints for CFR EVO API Gateway.
Provides dual-mode turn-by-turn routing with apparatus road-bias and station origin calculation.
"""
import os
import sys
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/route", tags=["routing"])

# Sibling service path injection for gis_service
BASE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CANDIDATE_GIS_PATHS = [
    os.path.join(BASE_ROOT, "services", "gis", "src"),
    "/app/services/gis/src",
    "/home/tcfire/CFR-EVO-APP/services/gis/src"
]
for p in CANDIDATE_GIS_PATHS:
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)


@router.get("")
def get_calculated_route(
    dest_lat: float,
    dest_lng: float,
    start_lat: Optional[float] = None,
    start_lng: Optional[float] = None,
    station_id: Optional[str] = "1",
    response_type: str = "emergency"
):
    """Calculates turn-by-turn emergency routing via stock OSRM.

    Returns OSRM's own distance and duration. Apparatus speed profiles are NOT applied
    (see APPARATUS_TIERS, staged for PROJECT_IDEAS #6) and road closures are NOT avoided
    (public.road_closures is display-only today; see docs/road_closure_integration.md).
    The previous docstring claimed both.
    """
    try:
        from gis_service.routing_engine import EVORoutingEngine
        router_instance = EVORoutingEngine(default_station_id=station_id or "1")
        route_data = router_instance.calculate_route(
            dest_lat=dest_lat,
            dest_lng=dest_lng,
            start_lat=start_lat,
            start_lng=start_lng,
            station_id=station_id,
            response_type=response_type
        )
        return route_data
    except Exception as e:
        logging.error(f"Error computing local route: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
