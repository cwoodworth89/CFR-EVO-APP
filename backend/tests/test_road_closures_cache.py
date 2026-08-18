import os
import sys
import time
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.server import get_road_closures, invalidate_road_closures_cache, _ROAD_CLOSURES_CACHE, trigger_road_closure_sync
from api.models import RoadClosureModel

def test_road_closures_caching_and_invalidation():
    # 1. Invalidate cache initially
    invalidate_road_closures_cache()
    assert _ROAD_CLOSURES_CACHE["data"] is None
    assert _ROAD_CLOSURES_CACHE["expires_at"] == 0.0

    # 2. Mock DB session with a test road closure
    mock_db = MagicMock()
    mock_record = MagicMock(spec=RoadClosureModel)
    mock_record.closure_id = "test-closure-1"
    mock_record.headline = "Pinetree Way Watermain Work"
    mock_record.street_name = "Pinetree Way"
    mock_record.closure_type = "FULL_CLOSURE"
    mock_record.emergency_access = True
    mock_record.description = "Full road closure for emergency repairs."
    mock_record.coordinates = [49.2910, -122.7907]
    mock_record.geometry = {"type": "LineString", "coordinates": [[-122.7907, 49.2910], [-122.7915, 49.2920]]}
    mock_record.source = "City of Coquitlam"
    mock_record.zone_id = "1"
    mock_record.affected_zones = ["1"]
    mock_record.start_time = None
    mock_record.end_time = None

    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_record]

    # First call should query the database and populate cache
    start_t = time.perf_counter()
    res1 = get_road_closures(db=mock_db)
    elapsed_1 = time.perf_counter() - start_t

    assert len(res1) == 1
    assert res1[0]["id"] == "test-closure-1"
    assert _ROAD_CLOSURES_CACHE["data"] is not None
    assert _ROAD_CLOSURES_CACHE["expires_at"] > time.time()
    assert mock_db.query.call_count == 1

    # Second call within 60s TTL should return immediately (< 5ms) without calling DB
    start_t = time.perf_counter()
    res2 = get_road_closures(db=mock_db)
    elapsed_2_ms = (time.perf_counter() - start_t) * 1000

    assert res2 == res1
    assert mock_db.query.call_count == 1  # No additional DB query
    assert elapsed_2_ms < 5.0  # Must return in < 5ms

    # Test cache invalidation
    invalidate_road_closures_cache()
    assert _ROAD_CLOSURES_CACHE["data"] is None

    # Next call after invalidation will query the DB again
    res3 = get_road_closures(db=mock_db)
    assert len(res3) == 1
    assert mock_db.query.call_count == 2
