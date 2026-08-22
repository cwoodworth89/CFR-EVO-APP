-- Road closure PostGIS integration
--
-- Two gaps this closes:
--
-- 1. public.zones carried only (map_name, geom). The zone -> responding unit -> hall
--    mapping lived exclusively in frontend/public/data/zones.json, so the kiosk had to
--    fetch that file to group closures by hall. unit_id and station now live in the
--    database alongside the geometry they belong to.
--
-- 2. public.road_closures stored geometry as jsonb with a separate varchar[] coordinate
--    pair, so zone assignment could not use PostGIS and was done with a hand-rolled
--    ray-casting point_in_polygon over zones.json. A real geometry column plus a GiST
--    index lets ST_Intersects do that work against the authoritative polygons.
--
-- Idempotent: safe to re-run.

BEGIN;

-- 1. Zone unit/hall assignment ------------------------------------------------
ALTER TABLE public.zones ADD COLUMN IF NOT EXISTS unit_id  VARCHAR(8);
ALTER TABLE public.zones ADD COLUMN IF NOT EXISTS station  VARCHAR(64);
ALTER TABLE public.zones ADD COLUMN IF NOT EXISTS hall_id  VARCHAR(4);

COMMENT ON COLUMN public.zones.unit_id IS
  'First-due apparatus for this zone (E1/E2/E3/E4/Q5). Source: City of Coquitlam '
  'emergency response zone assignment, imported from zones.json.';
COMMENT ON COLUMN public.zones.station IS
  'Human-readable hall name, e.g. "Hall 4 (Burke Mountain)".';
COMMENT ON COLUMN public.zones.hall_id IS
  'Numeric hall this zone reports to, derived from unit_id. Q5 is quartered at Hall 3.';

CREATE INDEX IF NOT EXISTS idx_zones_hall_id ON public.zones (hall_id);

-- 2. Road closure geometry ----------------------------------------------------
ALTER TABLE public.road_closures
  ADD COLUMN IF NOT EXISTS geom geometry(Geometry, 4326);

CREATE INDEX IF NOT EXISTS idx_road_closures_geom
  ON public.road_closures USING GIST (geom);

COMMENT ON COLUMN public.road_closures.geom IS
  'PostGIS geometry for the closure (Point or LineString, EPSG:4326). Authoritative '
  'for spatial queries; the jsonb geometry column is retained for the frontend payload.';

-- Resolved hall for display grouping, so the kiosk does not need zones.json.
ALTER TABLE public.road_closures ADD COLUMN IF NOT EXISTS hall_id VARCHAR(4);
CREATE INDEX IF NOT EXISTS idx_road_closures_hall_id ON public.road_closures (hall_id);

COMMIT;
