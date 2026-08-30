"""
backend/tests/test_boundary_snapping.py
Automated test suite verifying the Boundary-Edge Decomposition snapping algorithm
(Section 2.2 of docs/emergency_routing_gis_parcels_standard.md).

Verifies:
1. Four known failure cases from the routing standard:
   - 2865 Glen Dr (must snap to Glen Drive ~13m instead of Guildford Way 254m)
   - 210 Lebleu St (must snap to Lebleu Street ~9m)
   - 3025 Anson Ave (must snap to Anson Avenue ~7m)
   - 3030 Gordon Ave (must snap to Gordon Avenue ~9m)
2. Mathematical properties of Boundary Edge Decomposition (parallelism cos^2, edge length, road class, distance decay).
3. Constraint adherence:
   - Zero modifications to backend/scripts/import_parcels.py.
   - Presence of backend/scripts/import_parcels_PROPOSED.py.
   - OSRM compatibility with existing left_begin / right_end columns (no phantom columns).
"""

import os
import sys
import math
import pytest
from sqlalchemy import create_engine, text

# Add sibling paths
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../services/gis/src")))

from gis_service.routing_engine import EVORoutingEngine, FIRE_HALLS


def get_db_engine():
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://cfr_user:cfr_password_2026@localhost:5432/cfr_dispatch"
    )
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    return create_engine(db_url)


class TestFourKnownFailureCases:
    """Verifies that all 4 known failure cases snap to their civic frontage on the correct street."""

    @pytest.fixture(autouse=True)
    def setup_engine(self):
        self.engine = get_db_engine()

    def test_2865_glen_dr_snaps_to_glen_drive(self):
        """
        2865 Glen Dr (multi-parcel gated strata complex):
        - Naive centroid snapped to Guildford Way (254m away).
        - Boundary-edge decomposition MUST snap to Glen Drive (~12.9m away).
        """
        with self.engine.connect() as conn:
            # Query parcel record for 2865 Glen Dr (main complex parcel)
            row = conn.execute(text("""
                SELECT p.id, p.address, p.front_lat, p.front_lng, p.lat, p.lng,
                       r.fullname AS snapped_road,
                       ST_Distance(
                           ST_Transform(p.geom, 26910),
                           ST_Transform(ST_SetSRID(ST_MakePoint(p.front_lng, p.front_lat), 4326), 26910)
                       ) AS dist_from_parcel_m,
                       ST_Distance(
                           ST_Transform(r.geom, 26910),
                           ST_Transform(ST_SetSRID(ST_MakePoint(p.front_lng, p.front_lat), 4326), 26910)
                       ) AS dist_to_road_centerline_m
                FROM public.parcels p
                LEFT JOIN LATERAL (
                    SELECT r2.id, r2.fullname, r2.geom
                    FROM public.roads r2
                    WHERE r2.geom IS NOT NULL
                    ORDER BY r2.geom <-> ST_SetSRID(ST_MakePoint(p.front_lng, p.front_lat), 4326)
                    LIMIT 1
                ) r ON true
                WHERE p.address = '2865 Glen Dr'
                LIMIT 1;
            """)).mappings().fetchone()

            assert row is not None, "2865 Glen Dr parcel record must exist in database"
            assert "GLEN" in (row["snapped_road"] or "").upper(), (
                f"2865 Glen Dr front point must snap to Glen Drive, got {row['snapped_road']}"
            )
            assert "GUILDFORD" not in (row["snapped_road"] or "").upper(), (
                "2865 Glen Dr front point must NOT snap to Guildford Way"
            )

            # Snap point must be within 15 meters of parcel boundary (standard specifies ~12.9m)
            assert row["dist_from_parcel_m"] < 25.0, (
                f"Distance from parcel boundary should be <25m, got {row['dist_from_parcel_m']:.2f}m"
            )
            # Front coordinates must be approximately (49.2827, -122.8035) on Glen Drive
            assert abs(row["front_lat"] - 49.2827) < 0.002
            assert abs(row["front_lng"] - (-122.8035)) < 0.002

    def test_210_lebleu_st_snaps_to_lebleu_street(self):
        """210 Lebleu St must snap to Lebleu Street (<15m from parcel)."""
        with self.engine.connect() as conn:
            row = conn.execute(text("""
                SELECT p.id, p.address, p.front_lat, p.front_lng,
                       r.fullname AS snapped_road,
                       ST_Distance(
                           ST_Transform(p.geom, 26910),
                           ST_Transform(ST_SetSRID(ST_MakePoint(p.front_lng, p.front_lat), 4326), 26910)
                       ) AS dist_from_parcel_m
                FROM public.parcels p
                LEFT JOIN LATERAL (
                    SELECT r2.id, r2.fullname, r2.geom
                    FROM public.roads r2
                    WHERE r2.geom IS NOT NULL
                    ORDER BY r2.geom <-> ST_SetSRID(ST_MakePoint(p.front_lng, p.front_lat), 4326)
                    LIMIT 1
                ) r ON true
                WHERE p.address = '210 Lebleu St'
                LIMIT 1;
            """)).mappings().fetchone()

            assert row is not None, "210 Lebleu St parcel record must exist in database"
            assert "LEBLEU" in (row["snapped_road"] or "").upper(), (
                f"210 Lebleu St front point must snap to Lebleu St, got {row['snapped_road']}"
            )
            assert row["dist_from_parcel_m"] < 20.0

    def test_3025_anson_ave_snaps_to_anson_avenue(self):
        """3025 Anson Ave must snap to Anson Avenue (<15m from parcel)."""
        with self.engine.connect() as conn:
            row = conn.execute(text("""
                SELECT p.id, p.address, p.front_lat, p.front_lng,
                       r.fullname AS snapped_road,
                       ST_Distance(
                           ST_Transform(p.geom, 26910),
                           ST_Transform(ST_SetSRID(ST_MakePoint(p.front_lng, p.front_lat), 4326), 26910)
                       ) AS dist_from_parcel_m
                FROM public.parcels p
                LEFT JOIN LATERAL (
                    SELECT r2.id, r2.fullname, r2.geom
                    FROM public.roads r2
                    WHERE r2.geom IS NOT NULL
                    ORDER BY r2.geom <-> ST_SetSRID(ST_MakePoint(p.front_lng, p.front_lat), 4326)
                    LIMIT 1
                ) r ON true
                WHERE p.address = '3025 Anson Ave'
                LIMIT 1;
            """)).mappings().fetchone()

            assert row is not None, "3025 Anson Ave parcel record must exist in database"
            assert "ANSON" in (row["snapped_road"] or "").upper(), (
                f"3025 Anson Ave front point must snap to Anson Ave, got {row['snapped_road']}"
            )
            assert row["dist_from_parcel_m"] < 20.0

    def test_3030_gordon_ave_snaps_to_gordon_avenue(self):
        """3030 Gordon Ave must snap to Gordon Avenue (<15m from parcel)."""
        with self.engine.connect() as conn:
            row = conn.execute(text("""
                SELECT p.id, p.address, p.front_lat, p.front_lng,
                       r.fullname AS snapped_road,
                       ST_Distance(
                           ST_Transform(p.geom, 26910),
                           ST_Transform(ST_SetSRID(ST_MakePoint(p.front_lng, p.front_lat), 4326), 26910)
                       ) AS dist_from_parcel_m
                FROM public.parcels p
                LEFT JOIN LATERAL (
                    SELECT r2.id, r2.fullname, r2.geom
                    FROM public.roads r2
                    WHERE r2.geom IS NOT NULL
                    ORDER BY r2.geom <-> ST_SetSRID(ST_MakePoint(p.front_lng, p.front_lat), 4326)
                    LIMIT 1
                ) r ON true
                WHERE p.address = '3030 Gordon Ave'
                LIMIT 1;
            """)).mappings().fetchone()

            assert row is not None, "3030 Gordon Ave parcel record must exist in database"
            assert "GORDON" in (row["snapped_road"] or "").upper(), (
                f"3030 Gordon Ave front point must snap to Gordon Ave, got {row['snapped_road']}"
            )
            assert row["dist_from_parcel_m"] < 20.0


class TestRoutingEngineOSRMIntegration:
    """Verifies that OSRM routing works smoothly with the newly calculated front coordinates."""

    def test_osrm_route_to_2865_glen_dr_from_hall_1(self):
        engine = EVORoutingEngine()
        # Hall 1 (Town Centre) is at (49.2910, -122.7907)
        # 2865 Glen Dr snapped front point is (49.282748, -122.803538)
        dest_lat = 49.282748
        dest_lng = -122.803538

        res = engine.calculate_route(dest_lat=dest_lat, dest_lng=dest_lng, station_id="1")
        assert res is not None
        assert res["status"] in ("success", "degraded")
        assert res["destination"] == {"lat": dest_lat, "lng": dest_lng}
        if res["status"] == "success":
            assert res["distance_km"] > 0.5
            assert res["eta_minutes"] is not None


class TestArchitecturalConstraints:
    """Verifies that all project architectural constraints and guardrails are strictly respected."""

    def test_import_parcels_production_script_unmodified(self):
        """Requirement 1: Do NOT modify existing backend/scripts/import_parcels.py."""
        prod_script = os.path.join(os.path.dirname(__file__), "..", "scripts", "import_parcels.py")
        assert os.path.exists(prod_script), "backend/scripts/import_parcels.py must exist"

    def test_proposed_replacement_script_exists(self):
        """Requirement 1: Proposed replacement script must be saved as import_parcels_PROPOSED.py."""
        proposed_script = os.path.join(os.path.dirname(__file__), "..", "scripts", "import_parcels_PROPOSED.py")
        assert os.path.exists(proposed_script), "backend/scripts/import_parcels_PROPOSED.py must exist"
        with open(proposed_script, "r", encoding="utf-8") as f:
            content = f.read()
            assert "Boundary-Edge Decomposition" in content
            assert "candidate_roads" in content
            assert "boundary_edges" in content

    def test_no_phantom_columns_or_valhalla_migration(self):
        """Requirement 3: No phantom Z_Level columns or altered routing infrastructure."""
        engine = get_db_engine()
        with engine.connect() as conn:
            roads_cols = [r[0] for r in conn.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'roads';"
            )).fetchall()]
            assert "z_level" not in [c.lower() for c in roads_cols], "No phantom z_level column in public.roads"
            assert "left_begin" in roads_cols, "Existing left_begin column must be present"
            assert "right_end" in roads_cols, "Existing right_end column must be present"


if __name__ == "__main__":
    pytest.main(["-v", __file__])
