"""Each address-resolver fallback's SQL, run once against the live schema.

Why this exists
---------------
`test_geocoder_orchestrator.py` mocks every resolver, which is how `resolve_street_centroid`
could name `parcels.lat` for six days after the column became `centroid_lat` (2026-08-30,
`be0e7bf`) while the suite stayed green and step 5 of the geocoder returned None on every
call that reached it (punch-list #62). Nothing ran the statement.

These tests run each fallback's statement against the real database. They prove the SQL is
valid and returns a point inside the city; they do not assert the point, which moves with
every parcel import. Operator ruling 2026-09-04: the production database is the test
database, so this is read-only against it, and skipped where DATABASE_URL is not set.
"""
import os
import sys

import pytest
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "services", "gis", "src"))
from gis_service.address_resolver import AddressResolver  # noqa: E402

DATABASE_URL = os.environ.get("DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not DATABASE_URL.startswith("postgres"),
                                reason="needs the kiosk database: set DATABASE_URL")

# CLAUDE.md §5: the authoritative City of Coquitlam bounding box.
LAT = (49.20, 49.39)
LNG = (-122.92, -122.70)


def _inside_city(point: dict) -> bool:
    return LAT[0] < point["lat"] < LAT[1] and LNG[0] < point["lng"] < LNG[1]


@pytest.fixture(scope="module")
def engine():
    e = create_engine(DATABASE_URL)
    yield e
    e.dispose()


@pytest.fixture(scope="module")
def resolver(engine):
    return AddressResolver(engine)


def test_street_centroid_statement_is_valid_against_the_live_schema(engine, resolver, caplog):
    """Punch-list #62. The street with the most parcels, whatever it is today."""
    with engine.connect() as conn:
        street, stype = conn.execute(text(
            "SELECT street, streettype FROM public.parcels "
            "WHERE street IS NOT NULL GROUP BY 1, 2 ORDER BY count(*) DESC LIMIT 1")).fetchone()
    with caplog.at_level("ERROR"):
        point = resolver.resolve_street_centroid(street, stype or "")
    assert "street centroid fallback" not in caplog.text, caplog.text
    assert point is not None and point.get("is_street_centroid"), (street, stype, point)
    assert _inside_city(point), point


def test_road_centroid_statement_is_valid_against_the_live_schema(engine, resolver, caplog):
    """Step 6, the fallback below the one that broke. Same treatment."""
    with engine.connect() as conn:
        roadname = conn.execute(text(
            "SELECT roadname FROM public.roads WHERE roadname IS NOT NULL "
            "GROUP BY 1 ORDER BY count(*) DESC LIMIT 1")).scalar()
    with caplog.at_level("ERROR"):
        point = resolver.resolve_road_centroid(roadname, "")
    assert "road centroid fallback" not in caplog.text, caplog.text
    assert point is not None, roadname
    assert _inside_city(point), point


def test_nearest_civic_statement_is_valid_against_the_live_schema(engine, resolver, caplog):
    """Punch-list #67. A house number the City does not have, one above a parcel in the same
    100-block, on whatever street has one today (3304 Abbey Lane on 2026-09-05)."""
    with engine.connect() as conn:
        street, stype, house = conn.execute(text(
            "SELECT p.street, p.streettype, p.house::int + 1 FROM public.parcels p "
            "WHERE p.house::text ~ '^[0-9]+$' AND p.centroid_lat IS NOT NULL "
            "  AND NOT EXISTS (SELECT 1 FROM public.parcels q WHERE q.street = p.street "
            "      AND coalesce(q.streettype, '') = coalesce(p.streettype, '') "
            "      AND q.house::text = (p.house::int + 1)::text) "
            "  AND (p.house::int + 1) / 100 = p.house::int / 100 "
            "ORDER BY p.street, p.house::int LIMIT 1")).fetchone()
    with caplog.at_level("ERROR"):
        point = resolver.resolve_nearest_civic(str(house), street, stype or "")
    assert "nearest civic address fallback" not in caplog.text, caplog.text
    assert point is not None and point.get("is_nearest_civic"), (street, stype, house, point)
    assert _inside_city(point), point
