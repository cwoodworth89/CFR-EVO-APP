"""
FastAPI Router Sub-modules for CFR EVO API Gateway.
"""
from .auth import router as auth_router
from .dispatches import router as dispatches_router
from .parcels import router as parcels_router
from .streetview import router as streetview_router
from .routing import router as routing_router
from .road_closures import router as road_closures_router
from .evaluations import router as evaluations_router
from .audio import router as audio_router
from .tiles import router as tiles_router

__all__ = [
    "auth_router",
    "dispatches_router",
    "parcels_router",
    "streetview_router",
    "routing_router",
    "road_closures_router",
    "evaluations_router",
    "audio_router",
    "tiles_router",
]
