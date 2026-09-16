"""Punch list #92: City-published road closures on boundary roads were dropped at ingestion.

Seven Municipal 511 records in the 2026-09-16 pull failed the closure spatial tests: four fell
0.1-4.2 m outside public.city_boundary on roads whose centreline is the boundary line (North Rd,
Westwood St, Victoria Dr), and three were inside the city in the strip between the boundary and
the zone layer's outer edge (Balmoral Dr, North Rd, the Mary Hill Bypass). The fix buffers both
tests by CLOSURE_BOUNDARY_BUFFER_M (100 m, the operator's routing figure, reused).

The coordinates below are the feed's own geometry for those seven, as pulled. The tests run
read-only against the database in DATABASE_URL, like test_within_city_polygon.py, so a boundary
or zone refresh is tested against the real layers. The "before" assertions pin the cause: if a
refresh moves the boundary onto these points, they fail and say so rather than pass silently.
"""
import importlib.util
import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "closure_spatial", os.path.join(HERE, "..", "api", "closure_spatial.py"))
closure_spatial = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(closure_spatial)

DATABASE_URL = os.environ.get(
    'DATABASE_URL', 'postgresql://cfr_user:cfr_password_2026@localhost:5432/cfr_dispatch')

# (feed id, what the unbuffered tests said, lat, lng, nearest zone measured 2026-09-16)
SEVEN = [
    ("78131841", "outside", 49.24522, -122.89275, "3"),    # North Rd 64 m N of Rochester St
    ("78323174", "outside", 49.26991, -122.79061, "68"),   # Westwood St at Gordon Ave
    ("78341457", "outside", 49.28575, -122.74016, "111"),  # Victoria Dr 37 m E of Mitchell St
    ("78395658", "outside", 49.25601, -122.89295, "4"),    # North Rd 88 m S of Foster Ave
    ("78132259", "no zone", 49.27964, -122.82379, "69"),   # Balmoral Dr 96 m S of Guildford Dr
    ("78427933", "no zone", 49.25611, -122.89295, "4"),    # North Rd 77 m S of Foster Ave
    ("77458316", "no zone", 49.22695, -122.80628, "52"),   # Mary Hill Bypass at the onramp
]


def _point(lat, lng):
    return {"type": "Point", "coordinates": [lng, lat]}


@pytest.fixture(scope="module")
def db():
    engine = create_engine(DATABASE_URL, connect_args={"connect_timeout": 15})
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.mark.parametrize("feed_id,before,lat,lng,zone", SEVEN, ids=[s[0] for s in SEVEN])
def test_the_unbuffered_tests_did_drop_it(db, feed_id, before, lat, lng, zone):
    row = db.execute(text("""
        SELECT EXISTS (SELECT 1 FROM public.city_boundary cb
                       WHERE ST_Intersects(cb.geom, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326))) AS inside,
               EXISTS (SELECT 1 FROM public.zones z
                       WHERE ST_Intersects(z.geom, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326))) AS zoned
    """), {"lat": lat, "lng": lng}).mappings().one()
    if before == "outside":
        assert row["inside"] is False
    else:
        assert (row["inside"], row["zoned"]) == (True, False)


@pytest.mark.parametrize("feed_id,before,lat,lng,zone", SEVEN, ids=[s[0] for s in SEVEN])
def test_the_buffered_tests_keep_it_in_its_nearest_zone(db, feed_id, before, lat, lng, zone):
    geo = _point(lat, lng)
    assert closure_spatial.is_within_city(db, geo) is True
    affected, primary, _hall = closure_spatial.resolve_zones_and_hall(db, geo)
    assert primary == zone
    assert zone in affected


def test_a_point_150_m_outside_the_boundary_is_still_out(db):
    # Derived from the boundary, not hardcoded: 150 m due west of the boundary point nearest
    # the North Rd closure, which is outside because North Rd is the city's western edge here.
    row = db.execute(text("""
        WITH cb AS (SELECT ST_Union(geom) g FROM public.city_boundary),
             p AS (SELECT ST_ClosestPoint(ST_Boundary(cb.g), ST_SetSRID(ST_MakePoint(-122.89275, 49.24522), 4326)) b FROM cb),
             q AS (SELECT ST_Project(p.b::geography, 150, radians(270))::geometry g FROM p)
        SELECT ST_Y(q.g) lat, ST_X(q.g) lng,
               ST_Intersects(cb.g, q.g) AS inside,
               ST_Distance(cb.g::geography, q.g::geography) AS m
        FROM q, cb
    """)).mappings().one()
    assert row["inside"] is False and row["m"] > closure_spatial.CLOSURE_BOUNDARY_BUFFER_M
    assert closure_spatial.is_within_city(db, _point(row["lat"], row["lng"])) is False


def test_a_closure_well_outside_the_city_is_out(db):
    # Metrotown, Burnaby -- kilometres from the boundary.
    assert closure_spatial.is_within_city(db, _point(49.2276, -123.0076)) is False
