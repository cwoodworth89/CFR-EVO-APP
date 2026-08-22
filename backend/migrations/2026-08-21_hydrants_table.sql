-- public.hydrants: municipal hydrant inventory
--
-- Hydrants were the last authoritative GIS layer still living only as a JSON file
-- (frontend/public/data/hydrants.json), fetched directly by the browser. This brings
-- them in line with parcels, roads, zones and city_boundary.
--
-- flow_class and status are deliberately NULLABLE.
--
-- backend/scripts/sync_hydrants.py previously wrote:
--     "status":    attribs.get("status")     or "OPERATING",
--     "flowClass": attribs.get("flow_class") or "AA",
--
-- Verified against the City of Coquitlam ArcGIS source on 2026-08-21: private hydrants
-- return flow_class = null. Every "AA" on a private hydrant was fabricated by that
-- default. AA is the HIGHEST NFPA 291 class (light blue, 1500+ GPM), so an unrated
-- hydrant was being presented to crews as the best available water supply -- the most
-- dangerous possible direction for a substitution, and a CLAUDE.md §6.1 violation.
-- Defaulting status to OPERATING has the same shape: a hydrant of unknown condition
-- shown as in service.
--
-- Unknown values are stored NULL and MUST render as an explicit UNRATED / UNKNOWN
-- warning, never as one of the four NFPA colours and never as a blank badge.

BEGIN;

CREATE TABLE IF NOT EXISTS public.hydrants (
    id            BIGSERIAL PRIMARY KEY,
    object_id     INTEGER UNIQUE NOT NULL,
    gis_id        VARCHAR(32),
    -- NULL means the municipal source recorded no status. Do not default.
    status        VARCHAR(32),
    -- NFPA 291 class: AA (1500+ GPM), A (1000-1499), B (500-999), C (<500).
    -- NULL means unrated by the City. Do not default.
    flow_class    VARCHAR(4),
    lat           DOUBLE PRECISION NOT NULL,
    lng           DOUBLE PRECISION NOT NULL,
    geom          geometry(Point, 4326),
    zone_id       VARCHAR(16),
    source        VARCHAR(64) DEFAULT 'coquitlam_arcgis',
    synced_at     TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at    TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT hydrants_flow_class_valid
        CHECK (flow_class IS NULL OR flow_class IN ('AA', 'A', 'B', 'C'))
);

CREATE INDEX IF NOT EXISTS idx_hydrants_geom       ON public.hydrants USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_hydrants_gis_id     ON public.hydrants (gis_id);
CREATE INDEX IF NOT EXISTS idx_hydrants_status     ON public.hydrants (status);
CREATE INDEX IF NOT EXISTS idx_hydrants_flow_class ON public.hydrants (flow_class);
CREATE INDEX IF NOT EXISTS idx_hydrants_zone_id    ON public.hydrants (zone_id);

COMMENT ON COLUMN public.hydrants.flow_class IS
  'NFPA 291 flow classification. NULL = unrated by the City of Coquitlam (typical for '
  'private hydrants). Must render as UNRATED, never as a class colour.';
COMMENT ON COLUMN public.hydrants.status IS
  'Municipal service status (OPERATING, PRIVATE, NOT READY, METRO, ...). NULL = not '
  'recorded at source; must not be defaulted to OPERATING.';

COMMIT;
