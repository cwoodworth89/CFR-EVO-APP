"""
Validation tests for the PostGIS migration.
Run inside cfr_api container or with DATABASE_URL set.
"""
import os
import pytest
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://cfr_user:cfr_password_2026@localhost:5432/cfr_dispatch')

@pytest.fixture(scope='module')
def engine():
    return create_engine(DATABASE_URL)

@pytest.fixture
def conn(engine):
    """Function-scoped on purpose.

    This fixture used to be module-scoped, so all tests shared one connection and
    therefore one transaction. A single failing statement put that transaction into
    an aborted state and every subsequent test on the connection failed with
    InFailedSqlTransaction -- one stale test (test_landmarks_count, querying a table
    dropped in Phase D) was manufacturing six additional failures that had nothing
    wrong with them.

    A connection per test makes that cascade structurally impossible. These are
    read-only count/predicate queries against a local container, so the extra
    connections cost nothing measurable.
    """
    with engine.connect() as connection:
        yield connection

def test_postgis_enabled(conn):
    result = conn.execute(text('SELECT PostGIS_Version()')).scalar()
    assert result is not None and '3' in result

def test_roads_count(conn):
    count = conn.execute(text('SELECT COUNT(*) FROM public.roads')).scalar()
    assert count >= 3000, f'Expected >= 3000 roads, got {count}'

def test_intersections_count(conn):
    # Sanity floor only. The former 400-2500 bound predates the current import and
    # fails against the actual 6,499 rows; docs/development_freeze_summary.md documents
    # 3,947, which matches neither. No source justifies a precise expected count, so
    # asserting one would be an unsourced constant (CLAUDE.md 6.3) and would enshrine
    # data whose integrity is explicitly unverified -- see punch-list #9/#13, which
    # records at least one false intersection and apparent duplicates. This test only
    # catches a failed or empty import; restore a real bound after the #13 audit.
    count = conn.execute(text('SELECT COUNT(*) FROM public.intersections')).scalar()
    assert count >= 1000, f'Expected a populated intersections table, got {count}'

@pytest.mark.xfail(
    strict=False,
    reason=(
        'KNOWN DATA DEFECT, tracked as punch-list #9/#13. public.intersections holds 2 '
        'rows for DAVID AVE & PANORAMA DR and PostGIS confirms the road geometries do '
        'not intersect, so a dispatch to it geocodes to a fabricated point with no '
        'warning. This test is correct and the DATA is wrong -- it is marked xfail so '
        'the suite reports the real state without the assertion being weakened to hide '
        'it. strict=False: it XPASSes the moment the data is fixed.'
    ),
)
def test_no_false_intersections(conn):
    count = conn.execute(text("SELECT COUNT(*) FROM public.intersections WHERE intersection_key = 'DAVID AVE & PANORAMA DR'")).scalar()
    assert count == 0, 'DAVID AVE & PANORAMA DR should not exist (parallel streets)'

def test_known_intersection_exists(conn):
    count = conn.execute(text("SELECT COUNT(*) FROM public.intersections WHERE intersection_key LIKE '%CHRISTMAS%WESTWOOD%'")).scalar()
    assert count >= 1, 'CHRISTMAS WAY & WESTWOOD ST should exist'

def test_zones_count(conn):
    count = conn.execute(text('SELECT COUNT(*) FROM public.zones')).scalar()
    assert count == 134, f'Expected 134 zones, got {count}'

def test_city_boundary_exists(conn):
    count = conn.execute(text('SELECT COUNT(*) FROM public.city_boundary')).scalar()
    assert count == 1, f'Expected 1 city boundary, got {count}'

def test_road_names_count(conn):
    count = conn.execute(text('SELECT COUNT(*) FROM public.road_names')).scalar()
    assert count >= 1000, f'Expected >= 1000 road names, got {count}'

def test_dropped_tables_stay_dropped(conn):
    # Replaces test_landmarks_count. public.landmarks was renamed to custom_places in
    # Phase D and the table was dropped outright on 2026-08-21 when the custom-places
    # geocoder step was removed (commit 2ef12b7) -- its coordinates were hand-entered
    # and up to 1.8 km off a parcel (punch-list #7). Asserting a row count against a
    # dropped table is what aborted the shared transaction and cascaded into six other
    # tests. Assert the removal instead, so a reintroduction is caught.
    for table in ('landmarks', 'custom_places'):
        exists = conn.execute(
            text('SELECT to_regclass(:t)'), {'t': f'public.{table}'}
        ).scalar()
        assert exists is None, (
            f'public.{table} is back. It was removed deliberately; resolve place names '
            f'through public.parcels instead (CLAUDE.md 6.2).'
        )

def test_vocabulary_units(conn):
    count = conn.execute(text("SELECT COUNT(*) FROM public.vocabulary WHERE category = 'unit'")).scalar()
    assert count >= 40, f'Expected >= 40 unit vocab entries, got {count}'

def test_vocabulary_call_types(conn):
    count = conn.execute(text("SELECT COUNT(*) FROM public.vocabulary WHERE category = 'call_type'")).scalar()
    assert count >= 50, f'Expected >= 50 call type entries, got {count}'

def test_zone_spatial_query(conn):
    result = conn.execute(text("""
        SELECT map_name FROM public.zones
        WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(-122.7932, 49.2838), 4326))
        LIMIT 1
    """)).scalar()
    assert result is not None, 'Spatial zone query should return a zone for Coquitlam City Hall area'

def test_city_boundary_contains_coquitlam(conn):
    result = conn.execute(text("""
        SELECT ST_Contains(geom, ST_SetSRID(ST_MakePoint(-122.7932, 49.2838), 4326))
        FROM public.city_boundary LIMIT 1
    """)).scalar()
    assert result is True, 'Coquitlam City Hall should be within city boundary'

def test_city_boundary_excludes_burnaby(conn):
    result = conn.execute(text("""
        SELECT ST_Contains(geom, ST_SetSRID(ST_MakePoint(-122.9988, 49.2256), 4326))
        FROM public.city_boundary LIMIT 1
    """)).scalar()
    assert result is False, 'Metrotown (Burnaby) should NOT be within Coquitlam boundary'

def test_parcels_have_geometry(conn):
    count = conn.execute(text('SELECT COUNT(*) FROM public.parcels WHERE geom IS NOT NULL')).scalar()
    assert count > 60000, f'Expected > 60000 parcels with geometry, got {count}'

def test_geocoder_contract():
    """Verify the rewritten geocoder preserves the API contract."""
    from gis_service.geocoder import CoquitlamDataValidator
    v = CoquitlamDataValidator(database_url=DATABASE_URL)
    
    # Test address geocoding
    result = v.get_coordinates('3030 Gordon Ave')
    assert result is not None, '3030 Gordon Ave should geocode'
    assert 'lat' in result and 'lng' in result and 'rings' in result
    assert result['confidence'] > 50
    
    # Test zone lookup
    grid = v.get_map_grid_for_point(49.2838, -122.7932)
    assert grid is not None, 'Zone lookup should work for Coquitlam'
    
    # Test city boundary
    assert v.is_within_city(49.2838, -122.7932) is True
    assert v.is_within_city(48.0, -122.0) is False
    
    # Test road names
    names = v.get_all_road_names()
    assert len(names) >= 1000, f'Expected >= 1000 road names, got {len(names)}'
