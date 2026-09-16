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
    # Since #89 the endpoint also reads the sync status row, which has never been written
    # in this fixture. read_sync_status treats an absent row as NOT_ATTEMPTED.
    mock_db.query.return_value.filter.return_value.first.return_value = None

    # Two DB queries per uncached call now: the closure list, then the sync status row.
    QUERIES_PER_UNCACHED_CALL = 2

    # First call should query the database and populate cache
    start_t = time.perf_counter()
    res1 = get_road_closures(db=mock_db)
    elapsed_1 = time.perf_counter() - start_t

    # Shape changed 2026-09-16 (punch list #89): the last sync's outcome travels beside
    # the list so the kiosk can tell "the City has no closures" from "we never got
    # through". Both come from the same cached payload, so the flag can never be served
    # from a different attempt than the list beside it.
    assert len(res1["closures"]) == 1
    assert res1["closures"][0]["id"] == "test-closure-1"
    assert res1["sync"]["outcome"] == "NOT_ATTEMPTED"
    assert _ROAD_CLOSURES_CACHE["data"] is not None
    assert _ROAD_CLOSURES_CACHE["expires_at"] > time.time()
    assert mock_db.query.call_count == QUERIES_PER_UNCACHED_CALL

    # Second call within 60s TTL should return immediately (< 5ms) without calling DB
    start_t = time.perf_counter()
    res2 = get_road_closures(db=mock_db)
    elapsed_2_ms = (time.perf_counter() - start_t) * 1000

    assert res2 == res1
    assert mock_db.query.call_count == QUERIES_PER_UNCACHED_CALL  # No additional DB query
    assert elapsed_2_ms < 5.0  # Must return in < 5ms

    # Test cache invalidation
    invalidate_road_closures_cache()
    assert _ROAD_CLOSURES_CACHE["data"] is None

    # Next call after invalidation will query the DB again
    res3 = get_road_closures(db=mock_db)
    assert len(res3["closures"]) == 1
    assert mock_db.query.call_count == 2 * QUERIES_PER_UNCACHED_CALL


def test_closure_without_usable_coordinates_is_null_and_logged_not_defaulted(caplog):
    """Punch list #90: no hardcoded fallback point. A bad record goes out as null, loudly."""
    import logging

    invalidate_road_closures_cache()
    bad_values = [None, [], ["49.28"], ["abc", "-122.8"], ["nan", "-122.8"], [0, 0]]
    records = []
    for i, coords in enumerate(bad_values):
        rec = MagicMock(spec=RoadClosureModel)
        rec.closure_id = f"bad-{i}"
        rec.headline = "x"
        rec.street_name = "x"
        rec.closure_type = "FULL_CLOSURE"
        rec.emergency_access = "CAUTION"
        rec.description = "x"
        rec.coordinates = coords
        rec.geometry = {}
        rec.source = "test"
        rec.zone_id = "1"
        rec.affected_zones = ["1"]
        rec.start_time = None
        rec.end_time = None
        records.append(rec)

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = records
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with caplog.at_level(logging.ERROR):
        payload = get_road_closures(db=mock_db)

    assert [c["coordinates"] for c in payload["closures"]] == [None] * len(bad_values)
    for c in payload["closures"]:
        assert c["coordinates"] != [49.28, -122.80]
    logged = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    for i in range(len(bad_values)):
        assert any(f"bad-{i}" in m for m in logged)
    invalidate_road_closures_cache()


def test_unknown_severity_and_missing_text_are_served_as_null(caplog):
    """Punch list #91: the contract the kiosk builds N/A and "--" on."""
    import logging

    invalidate_road_closures_cache()
    rec = MagicMock(spec=RoadClosureModel)
    rec.id = 42
    rec.closure_id = "muni_7_0"
    rec.headline = None
    rec.street_name = None
    rec.closure_type = None
    rec.emergency_access = None
    rec.description = None
    rec.coordinates = [49.28, -122.80]
    rec.geometry = {}
    rec.source = "City of Coquitlam"
    rec.zone_id = "1"
    rec.affected_zones = ["1"]
    rec.start_time = None
    rec.end_time = None

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [rec]
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with caplog.at_level(logging.ERROR):
        payload = get_road_closures(db=mock_db)
    (served,) = payload["closures"]

    assert served["severity"] is None
    assert served["emergencyAccess"] is None
    assert served["street"] is None
    assert served["headline"] is None
    assert served["description"] is None
    assert served["id"] == "muni_7_0"
    assert served["rowId"] == 42
    assert "idMissing" not in served
    assert payload["sync"]["skipped"] is None  # no attempt recorded yet
    assert any("muni_7_0" in r.getMessage() and "severity" in r.getMessage()
               for r in caplog.records if r.levelno == logging.ERROR)
    invalidate_road_closures_cache()
