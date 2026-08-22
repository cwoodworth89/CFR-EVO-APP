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
    # public.intersections is DERIVED from public.roads geometry by
    # backend/scripts/derive_intersections.py, so the count is reproducible rather than
    # arbitrary: 1,784 rows on the 2026-08-22 road graph. The band lets the municipal
    # centreline layer grow without failing, while catching a failed or empty rebuild.
    # The real guarantee is test_every_intersection_is_geometrically_real below -- a
    # count cannot tell you whether the rows are true.
    count = conn.execute(text('SELECT COUNT(*) FROM public.intersections')).scalar()
    assert 1200 <= count <= 3000, f'Expected 1200-3000 derived intersections, got {count}'


CANONICAL_STREET_CTE = """
    WITH sfx AS (
        SELECT upper(btrim(term)) f, upper(btrim(term_normalized)) a
        FROM public.vocabulary
        WHERE category = 'street_suffix' AND is_active
    ),
    street AS (
        SELECT btrim(regexp_replace(upper(btrim(r.roadname)), '[,.]', '', 'g') || ' ' ||
                     COALESCE(s.a, upper(btrim(COALESCE(r.roadtype,''))))) AS canon,
               ST_Union(r.geom) AS geom
        FROM public.roads r LEFT JOIN sfx s ON s.f = upper(btrim(r.roadtype))
        WHERE r.roadname IS NOT NULL AND btrim(r.roadname) <> ''
        GROUP BY 1
    )
"""


def test_every_intersection_is_geometrically_real(conn):
    """The structural invariant: every stored intersection's two named streets must
    actually meet in public.roads.

    This is what makes punch-list #9 impossible to reintroduce. The old table was built
    from parcel proximity -- pairs of houses within 40 m on differently-named streets --
    so it held 3,086 rows whose streets never meet, 1,777 of those pairs more than 60 m
    apart. No count or spot-check catches that; this does.

    Tolerance matches ENDPOINT_SNAP_M in derive_intersections.py: municipal centrelines
    do not always share an exact vertex at a T-junction.
    """
    bad = conn.execute(text(CANONICAL_STREET_CTE + """
        SELECT i.intersection_key,
               round(ST_Distance(a.geom::geography, b.geom::geography)::numeric, 1) AS gap_m
        FROM public.intersections i
        JOIN street a ON a.canon = upper(btrim(i.street_a))
        JOIN street b ON b.canon = upper(btrim(i.street_b))
        WHERE i.source = 'derived'
          AND NOT ST_DWithin(a.geom::geography, b.geom::geography, 2.0)
        ORDER BY gap_m DESC
        LIMIT 10
    """)).fetchall()
    assert not bad, (
        'Intersections stored whose streets do not meet in public.roads: '
        + ', '.join(f'{k} ({g} m apart)' for k, g in bad))


def test_intersection_streets_all_exist_in_roads(conn):
    """Both named streets of every derived intersection must exist in public.roads.

    Catches the 'NAN' class of defect: the old table held 113 rows whose street was
    literally the string 'NAN', a pandas NaN stringified on export.
    """
    orphans = conn.execute(text(CANONICAL_STREET_CTE + """
        SELECT DISTINCT t.s FROM (
            SELECT upper(btrim(street_a)) s FROM public.intersections WHERE source='derived'
            UNION ALL
            SELECT upper(btrim(street_b)) FROM public.intersections WHERE source='derived'
        ) t WHERE NOT EXISTS (SELECT 1 FROM street WHERE street.canon = t.s)
        LIMIT 10
    """)).fetchall()
    assert not orphans, f'Intersection streets absent from public.roads: {[o[0] for o in orphans]}'


def test_no_false_intersections(conn):
    # Was xfail while public.intersections came from parcel proximity: DAVID AVE and
    # PANORAMA DR are parallel streets whose back yards abut, so the old 40 m
    # house-pairing heuristic invented a junction 243 m from either road. Deriving from
    # centreline geometry removed it structurally, so this asserts outright again.
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
    result = conn.execute(text(
        'SELECT public.zone_for_point(ST_SetSRID(ST_MakePoint(-122.7932, 49.2838), 4326))'
    )).scalar()
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


def test_zone_for_point_resolves_points_on_zone_boundaries(conn):
    """public.zone_for_point must resolve a point lying ON a zone boundary.

    Zone polygons are bounded BY the road network, so every road intersection sits on a
    boundary. The previous ST_Contains implementation tested the strict interior and
    returned NULL for those: measured 2026-08-22, 155 of 1,784 real intersections got no
    map grid for that reason alone.
    """
    total, with_grid = conn.execute(text(
        'SELECT count(*), count(public.zone_for_point(geom)) FROM public.intersections'
    )).fetchone()
    assert total > 0
    inside_without_grid = conn.execute(text("""
        SELECT count(*) FROM public.intersections i
        WHERE public.zone_for_point(i.geom) IS NULL
          AND ST_Contains((SELECT ST_Union(geom) FROM public.city_boundary), i.geom)
    """)).scalar()
    assert inside_without_grid == 0, (
        f'{inside_without_grid} intersections inside the city have no map grid; '
        f'zone_for_point is rejecting boundary points again ({with_grid}/{total} resolved)')


def test_zone_for_point_returns_null_outside_the_city(conn):
    # Metrotown, Burnaby. An unknown grid must read as unknown, never a nearest guess.
    assert conn.execute(text(
        'SELECT public.zone_for_point(ST_SetSRID(ST_MakePoint(-122.9988, 49.2256), 4326))'
    )).scalar() is None


def test_intersections_zone_id_column_is_gone(conn):
    """zone_id was a denormalized copy of zone_for_point()'s result, free to drift from
    the geometry it came from. The grid is derived at read time now."""
    assert conn.execute(text("""
        SELECT count(*) FROM information_schema.columns
        WHERE table_schema='public' AND table_name='intersections' AND column_name='zone_id'
    """)).scalar() == 0, 'public.intersections.zone_id is back; the grid must be derived'
