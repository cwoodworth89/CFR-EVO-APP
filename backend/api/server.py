"""
CFR EVO Local API Gateway Application Root.
Coordinates modular APIRouters, CORS middleware, MQTT event broadcasting, and background sync daemons.
"""
import os
import sys
import logging
import threading
from contextlib import asynccontextmanager

# Dynamically inject sibling microservices (/services/*/src) into sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SERVICES_DIR = os.path.join(BASE_DIR, "services")
for s in ["gis", "audio", "dispatch_notifications"]:
    p = os.path.join(SERVICES_DIR, s, "src")
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)
    p_container = f"/app/services/{s}/src"
    if os.path.exists(p_container) and p_container not in sys.path:
        sys.path.insert(0, p_container)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

try:
    from backend.api.database import engine, Base
    from backend.api.mqtt import init_mqtt, publish_mqtt_event
    from backend.api.routers.road_closures import run_periodic_road_closure_sync
    from backend.api.routers import (
        auth_router,
        dispatches_router,
        parcels_router,
        streetview_router,
        routing_router,
        road_closures_router,
        evaluations_router,
        audio_router,
        tiles_router,
    )
    # Backward compatibility re-exports
    from backend.api.schemas import (
        LoginRequest,
        DispatchCreateSchema,
        DispatchUpdateSchema,
        FeedbackSchema,
        StreetViewOverrideSchema,
        ParcelCameraOverrideSchema,
        ParcelMetadataSchema,
        RoadClosureSchema,
    )
    from backend.api.routers.parcels import (
        _clean_streetview_address,
        lookup_parcel,
        save_parcel_streetview,
    )
    from backend.api.routers.streetview import (
        get_all_streetview_overrides,
        get_streetview_override,
        save_streetview_override,
    )
    from backend.api.routers.road_closures import (
        get_road_closures,
        invalidate_road_closures_cache,
        _ROAD_CLOSURES_CACHE,
        trigger_road_closure_sync,
    )
    from backend.api.routers.dispatches import serialize_call
    from backend.api.routers.audio import RECORDINGS_DIR
except ModuleNotFoundError:
    from api.database import engine, Base
    from api.mqtt import init_mqtt, publish_mqtt_event
    from api.routers.road_closures import run_periodic_road_closure_sync
    from api.routers import (
        auth_router,
        dispatches_router,
        parcels_router,
        streetview_router,
        routing_router,
        road_closures_router,
        evaluations_router,
        audio_router,
        tiles_router,
    )
    # Backward compatibility re-exports
    from api.schemas import (
        LoginRequest,
        DispatchCreateSchema,
        DispatchUpdateSchema,
        FeedbackSchema,
        StreetViewOverrideSchema,
        ParcelCameraOverrideSchema,
        ParcelMetadataSchema,
        RoadClosureSchema,
    )
    from api.routers.parcels import (
        _clean_streetview_address,
        lookup_parcel,
        save_parcel_streetview,
    )
    from api.routers.streetview import (
        get_all_streetview_overrides,
        get_streetview_override,
        save_streetview_override,
    )
    from api.routers.road_closures import (
        get_road_closures,
        invalidate_road_closures_cache,
        _ROAD_CLOSURES_CACHE,
        trigger_road_closure_sync,
    )
    from api.routers.dispatches import serialize_call
    from api.routers.audio import RECORDINGS_DIR

# Ensure database tables exist
Base.metadata.create_all(bind=engine)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager to handle application startup and background tasks."""
    init_mqtt()
    sync_thread = threading.Thread(target=run_periodic_road_closure_sync, daemon=True)
    sync_thread.start()
    logging.info("Started background daemon thread for 24h road closure differential synchronization.")
    yield


app = FastAPI(title="CFR EVO Local API Gateway", version="1.0.0", lifespan=lifespan)

# CORS middleware for all station kiosks (Halls 1, 2, 3, 4)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static file mount for recordings
app.mount("/api/audio", StaticFiles(directory=RECORDINGS_DIR), name="audio")

# Mount modular routers
app.include_router(auth_router)
app.include_router(dispatches_router)
app.include_router(parcels_router)
app.include_router(streetview_router)
app.include_router(routing_router)
app.include_router(road_closures_router)
app.include_router(evaluations_router)
app.include_router(audio_router)
app.include_router(tiles_router)


@app.get("/")
@app.get("/api/health")
def health_check():
    """Root health check endpoint."""
    return {"status": "online", "service": "CFR EVO Local API Gateway", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("backend.api.server:app", host="0.0.0.0", port=port, reload=False)
