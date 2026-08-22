#!/usr/bin/env python3
"""
derive_intersections.py

Rebuild public.intersections from public.roads centreline geometry.

WHY THIS REPLACES THE OLD EXTRACTOR
-----------------------------------
public.intersections used to be loaded from backend/data/gis/intersections.json,
produced by extract_all_intersections_from_gis.py. That script never looked at a road
centreline. It took PARCEL address points from Addresses.shp, paired parcels within 40 m
of each other that carried different street names, took the midpoint of the shortest
line between the two parcels, and clustered those midpoints with a 45 m epsilon.

Its operative definition of "intersection" was therefore "two houses on different
streets happen to be within 40 m of each other". Measured against road geometry on
2026-08-22, out of 6,499 rows:

  * 3,086 rows whose two named streets never meet at all -- 1,777 of those pairs are
    more than 60 m apart. DAVID AVE & PANORAMA DR (punch-list #9) is one of them:
    parallel streets whose back yards abut.
  * 2,863 rows where the streets do genuinely meet, but the stored coordinate was an
    average of parcel-pair midpoints -- median error 63 m from the actual crossing,
    with only 129 of 2,863 within 10 m.
  * 3,413 rows whose stored point was not within 20 m of ANY road.
  * 113 rows with a street literally named "NAN" (a pandas NaN stringified on export).

An intersection is a topological property of the road network: the point where two
named centrelines meet. That is what this script computes, and it is why deriving from
geometry makes a false intersection structurally impossible (punch-list #13).

METHOD
------
1. Group public.roads segments by canonical street name and ST_Union them.
2. Pair streets whose merged geometries intersect and take the intersection points.
   Where two streets share a stretch of centreline the intersection is a line, so the
   midpoint of that line is used.
3. Cluster the points of each street pair, so one junction split across several
   centreline nodes becomes one row, while a street genuinely crossing another twice
   stays as two candidates (candidate_index).
4. Replace only source='derived' rows. source='manual' rows are never touched.

No zone / map grid is stored on the row. It is derived from the geometry at read time by
public.zone_for_point(), so there is one definition of which zone a point falls in and no
stored copy free to drift from the geometry it came from.

Street name canonicalisation uses gis_service.normalization, which reads the suffix
vocabulary from public.vocabulary -- the same code path that normalizes an incoming
dispatch. Storage and lookup therefore cannot diverge, which is the defect that made
'SUNSET SQ' in the table unreachable from 'SUNSET SQUARE' in a dispatch.
"""
import os
import sys
import logging
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "services", "gis", "src"))

from sqlalchemy import create_engine, text  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Two centreline nodes of the same street pair closer together than this are treated as
# one junction. MEASURED on the kiosk road graph 2026-08-22: of 247 nodes that have a
# same-pair neighbour, 117 lie within 15 m (segment splits, and the two carriageways of
# a divided arterial -- one junction), while 46 lie more than 150 m apart (a street
# genuinely crossing another twice -- separate junctions). The region between is sparse
# but continuous, so this is a judgement inside a measured range rather than a natural
# break: 25 m spans a divided-arterial crossing without merging any observed pair of
# distinct junctions.
JUNCTION_CLUSTER_EPS_M = 25.0

# Municipal centreline endpoints do not always share an exact vertex at a T-junction.
# MEASURED 2026-08-22: of the 2,021 street pairs the old table claimed that strict
# ST_Intersects rejects, only 5 are within 1 m and 17 within 15 m, while 1,777 are more
# than 60 m apart. A 2 m tolerance recovers 10 real junctions lost to dangling endpoints
# and admits nothing else -- the next non-empty band does not begin until 10 m.
ENDPOINT_SNAP_M = 2.0

REBUILD_SQL = """
CREATE TEMP TABLE _sfx(f text PRIMARY KEY, a text) ON COMMIT DROP;
INSERT INTO _sfx
SELECT upper(btrim(term)), upper(btrim(term_normalized))
FROM public.vocabulary
WHERE category = 'street_suffix' AND is_active = TRUE
  AND term IS NOT NULL AND term_normalized IS NOT NULL;

-- Canonical street name, matching gis_service.normalization.normalize_street_name:
-- uppercase, strip , and . , abbreviate the final word only if the suffix vocabulary
-- knows it.
CREATE TEMP TABLE _street ON COMMIT DROP AS
SELECT btrim(regexp_replace(upper(btrim(r.roadname)), '[,.]', '', 'g') || ' ' ||
             COALESCE(s.a, upper(btrim(COALESCE(r.roadtype, ''))))) AS canon,
       ST_Union(r.geom) AS geom
FROM public.roads r
LEFT JOIN _sfx s ON s.f = upper(btrim(r.roadtype))
WHERE r.roadname IS NOT NULL AND btrim(r.roadname) <> ''
GROUP BY 1;
CREATE INDEX ON _street USING gist(geom);
ANALYZE _street;

CREATE TEMP TABLE _node ON COMMIT DROP AS
SELECT ca, cb, ST_Transform(pt, 26910) AS pt26
FROM (
  SELECT a.canon AS ca, b.canon AS cb,
    CASE
      WHEN ST_GeometryType(d.geom) = 'ST_Point' THEN d.geom
      WHEN ST_GeometryType(ST_LineMerge(d.geom)) = 'ST_LineString'
           THEN ST_LineInterpolatePoint(ST_LineMerge(d.geom), 0.5)
      ELSE ST_PointOnSurface(d.geom)
    END AS pt
  FROM _street a
  JOIN _street b ON a.canon < b.canon AND ST_Intersects(a.geom, b.geom)
  CROSS JOIN LATERAL ST_Dump(ST_Intersection(a.geom, b.geom)) d
  UNION ALL
  -- Endpoint snap: streets that come within ENDPOINT_SNAP_M without sharing a vertex.
  SELECT a.canon, b.canon,
         ST_LineInterpolatePoint(ST_ShortestLine(a.geom, b.geom), 0.5)
  FROM _street a
  JOIN _street b ON a.canon < b.canon
   AND NOT ST_Intersects(a.geom, b.geom)
   AND ST_DWithin(a.geom::geography, b.geom::geography, :snap_m)
) t
WHERE pt IS NOT NULL;

CREATE TEMP TABLE _clustered ON COMMIT DROP AS
SELECT ca, cb,
       ST_ClusterDBSCAN(pt26, eps := :eps_m, minpoints := 1)
         OVER (PARTITION BY ca, cb) AS cid,
       pt26
FROM _node;

CREATE TEMP TABLE _junction ON COMMIT DROP AS
SELECT ca, cb, cid,
       ST_Transform(ST_Centroid(ST_Collect(pt26)), 4326) AS geom
FROM _clustered
GROUP BY ca, cb, cid;

CREATE TEMP TABLE _indexed ON COMMIT DROP AS
SELECT ca, cb, geom,
       (row_number() OVER (PARTITION BY ca, cb
                           ORDER BY ST_X(geom), ST_Y(geom)) - 1)::int AS candidate_index
FROM _junction;

DELETE FROM public.intersections WHERE source = 'derived';

-- No zone is stored. The map grid is derived from the geometry by
-- public.zone_for_point() at read time, so there is exactly one definition of which
-- zone a point is in and no stored copy that can drift from it.
INSERT INTO public.intersections
  (street_a, street_b, intersection_key, lat, lng, geom, candidate_index,
   source, updated_at)
SELECT j.ca, j.cb, j.ca || ' & ' || j.cb,
       ST_Y(j.geom), ST_X(j.geom),
       j.geom, j.candidate_index,
       'derived', now()
FROM _indexed j
WHERE NOT EXISTS (
  SELECT 1 FROM public.intersections m
  WHERE m.source = 'manual'
    AND m.intersection_key = j.ca || ' & ' || j.cb
    AND m.candidate_index = j.candidate_index
);
"""


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Rebuild public.intersections from public.roads geometry.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Report what would change, then roll back without writing.")
    args = ap.parse_args()

    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://cfr_user:cfr_password_2026@localhost:5432/cfr_dispatch")
    os.environ.setdefault("DATABASE_URL", db_url)
    engine = create_engine(db_url)

    # Fail loudly if the suffix vocabulary is missing, rather than deriving names
    # against an unknown suffix set and writing keys nothing can look up.
    from gis_service.normalization import get_suffix_mappings
    mappings = get_suffix_mappings()
    logging.info("Street suffix vocabulary: %d active mappings in public.vocabulary.",
                 len(mappings))

    conn = engine.connect()
    trans = conn.begin()
    try:
        before = conn.execute(text("SELECT count(*) FROM public.intersections")).scalar()
        manual = conn.execute(text(
            "SELECT count(*) FROM public.intersections WHERE source='manual'")).scalar()

        conn.execute(text(REBUILD_SQL),
                     {"snap_m": ENDPOINT_SNAP_M, "eps_m": JUNCTION_CLUSTER_EPS_M})

        after = conn.execute(text("SELECT count(*) FROM public.intersections")).scalar()
        derived = conn.execute(text(
            "SELECT count(*) FROM public.intersections WHERE source='derived'")).scalar()
        no_zone = conn.execute(text(
            "SELECT count(*) FROM public.intersections "
            "WHERE source='derived' AND public.zone_for_point(geom) IS NULL")).scalar()

        logging.info("rows before=%d  after=%d  (derived=%d, manual preserved=%d)",
                     before, after, derived, manual)
        if no_zone:
            logging.warning("%d derived junctions fall outside every zone polygon "
                            "and carry zone_id NULL.", no_zone)

        if args.dry_run:
            trans.rollback()
            logging.info("--dry-run: rolled back, nothing written.")
        else:
            trans.commit()
            logging.info("public.intersections rebuilt from public.roads geometry.")
        return 0
    except Exception:
        trans.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
