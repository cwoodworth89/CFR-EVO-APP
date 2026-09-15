"""Punch-list #87: "inside the City" is public.city_boundary, with no bounding-box fallback.

The box it replaces ended at lng -122.70; the City polygon reaches -122.621, and 158 parcel
centroids lie east of the box (kiosk database, 2026-09-15). These run against the database in
DATABASE_URL, like test_postgis_migration.py, and pick their points from it rather than
hardcoding them, so a boundary refresh cannot leave them testing a stale geometry.
"""
import os
import sys
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, text

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for p in (ROOT, os.path.join(ROOT, "services", "gis", "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from gis_service.spatial_queries import SpatialQueryEngine  # noqa: E402

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://cfr_user:cfr_password_2026@localhost:5432/cfr_dispatch')


@pytest.fixture(scope='module')
def engine():
    return create_engine(DATABASE_URL, connect_args={"connect_timeout": 15})


@pytest.fixture(scope='module')
def spatial(engine):
    return SpatialQueryEngine(engine)


def test_parcel_east_of_the_old_box_is_inside(engine, spatial):
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT ST_Y(c) lat, ST_X(c) lng FROM (
                SELECT ST_PointOnSurface(p.geom) c FROM public.parcels p
                WHERE ST_X(ST_Centroid(p.geom)) > -122.70
                ORDER BY ST_X(ST_Centroid(p.geom)) DESC LIMIT 1) s
        """)).fetchone()
    assert row is not None, "expected a City parcel east of lng -122.70 (158 on 2026-09-15)"
    assert row.lng > -122.70
    assert spatial.is_within_city(row.lat, row.lng) is True


def test_point_in_the_old_box_but_outside_the_city_is_outside(spatial):
    # 49.2626, -122.7811: Port Coquitlam, inside the old box (lat 49.20-49.39, lng
    # -122.92..-122.70); ST_Covers on public.city_boundary false, checked on the kiosk 2026-09-15.
    assert spatial.is_within_city(49.2626, -122.7811) is False


def test_point_on_the_city_line_is_inside(engine, spatial):
    # A vertex of the boundary lies on it: ST_Contains says false, ST_Covers true.
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT ST_Y(v) lat, ST_X(v) lng FROM (
                SELECT ST_PointN(ST_ExteriorRing(ST_GeometryN(geom, 1)), 1) v
                FROM public.city_boundary LIMIT 1) s
        """)).fetchone()
    assert spatial.is_within_city(row.lat, row.lng) is True


def test_unknown_is_none_not_a_guess():
    broken = MagicMock()
    broken.connect.side_effect = RuntimeError("database down")
    assert SpatialQueryEngine(broken).is_within_city(49.28, -122.79) is None
    assert SpatialQueryEngine(broken).is_within_city(None, -122.79) is None


def test_endpoint_carries_the_polygon_answer():
    from backend.api.routers.parcels import within_city
    assert within_city(49.2626, -122.7811) == {"within_city": False}
    assert within_city(49.2838, -122.7932) == {"within_city": True}
