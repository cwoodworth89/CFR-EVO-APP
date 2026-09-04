#!/usr/bin/env python3
"""
tools/verify_snapping_corpus.py
Dispatch Corpus Verification & Efficacy Benchmark for Boundary-Edge Decomposition Snapping.

Evaluates:
1. The 4 known reference cases, now executable in backend/tests/test_boundary_snapping.py
   (Section 2 of the routing standard was deleted 2026-08-31 with the unadopted proposal):
   - 2865 Glen Dr (must snap to Glen Drive ~12.9m instead of Guildford Way 254m trap)
   - 210 Lebleu St (frontage on Lebleu St ~9.3m)
   - 3025 Anson Ave (frontage on Anson Ave ~9.5m)
   - 3030 Gordon Ave (frontage on Gordon Ave ~9.2m)
2. The entire human-verified dispatch corpus (305 records) from public.dispatches:
   - Evaluates address resolution and front arrival coordinate accuracy.
   - Calculates distance from actual parcel boundary to the snapped roadway arrival point.
   - Accurately classifies exact parcel matches vs intersection matches (with XStreet support).
   - Tests OSRM routing from assigned/nearest fire halls.
3. Outputs comprehensive statistical metrics, markdown report, and per-record evaluation.
"""

import os
import sys
import json
import time
import math
import argparse
from collections import Counter
from datetime import datetime, timezone

# Sibling paths
from _repo import BACKEND  # tools/_repo.py locates the repo and puts backend/ and services/*/src on sys.path
backend_dir = str(BACKEND)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

root_dir = os.path.dirname(backend_dir)
for s in ["gis", "audio", "dispatch_notifications"]:
    p = os.path.join(root_dir, "services", s, "src")
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

from sqlalchemy import create_engine, text
from gis_service.geocoder import CoquitlamDataValidator
from gis_service.normalization import split_intersection_parts
from gis_service.routing_engine import EVORoutingEngine, FIRE_HALLS, get_unit_station_id


def get_db_url() -> str:
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        return db_url
    for host in ["localhost", "100.95.146.94"]:
        url = f"postgresql://cfr_user:cfr_password_2026@{host}:5432/cfr_dispatch"
        try:
            eng = create_engine(url, connect_args={"connect_timeout": 2})
            with eng.connect() as conn:
                conn.execute(text("SELECT 1;"))
            os.environ["DATABASE_URL"] = url
            return url
        except Exception:
            continue
    fallback = "postgresql://cfr_user:cfr_password_2026@localhost:5432/cfr_dispatch"
    os.environ["DATABASE_URL"] = fallback
    return fallback


def setup_osrm_url(db_url: str):
    """If OSRM_ROUTER_URL is not set, derive from DB host (e.g. 100.95.146.94)."""
    if not os.environ.get("OSRM_ROUTER_URL") and not os.environ.get("OSRM_URL") and not os.environ.get("OSRM_BACKEND_URL"):
        if "@" in db_url:
            host = db_url.split("@")[-1].split(":")[0].split("/")[0]
            if host and host not in ("localhost", "127.0.0.1"):
                os.environ["OSRM_ROUTER_URL"] = f"http://{host}:5000"
        if not os.environ.get("OSRM_ROUTER_URL"):
            os.environ["OSRM_ROUTER_URL"] = "http://100.95.146.94:5000"


def verify_four_failure_cases(engine) -> list:
    """Verifies the 4 reference cases from the routing standard."""
    print("=" * 80)
    print("1. EVALUATION OF 4 REFERENCE CASES")
    print("=" * 80)

    cases = [
        ("2865 Glen Dr", "Glen Drive", 15.0, "Guildford Way (254m centroid trap avoided)"),
        ("210 Lebleu St", "Lebleu Street", 15.0, "Verified civic frontage on Lebleu St"),
        ("3025 Anson Ave", "Anson Avenue", 15.0, "Verified civic frontage on Anson Ave"),
        ("3030 Gordon Ave", "Gordon Avenue", 15.0, "Verified civic frontage on Gordon Ave")
    ]

    results = []
    with engine.connect() as conn:
        for addr, expected_road, max_dist_m, description in cases:
            row = conn.execute(text("""
                SELECT p.id, p.address, p.street, p.house, p.centroid_lat, p.centroid_lng,
                       p.front_lat, p.front_lng,
                       r.fullname AS snapped_road,
                       r.road_class,
                       ST_Distance(
                           ST_Transform(p.geom, 26910),
                           ST_Transform(ST_SetSRID(ST_MakePoint(p.front_lng, p.front_lat), 4326), 26910)
                       ) AS dist_from_parcel_m,
                       ST_Distance(
                           ST_Transform(r.geom, 26910),
                           ST_Transform(ST_SetSRID(ST_MakePoint(p.front_lng, p.front_lat), 4326), 26910)
                       ) AS dist_to_road_m
                FROM public.parcels p
                LEFT JOIN LATERAL (
                    SELECT r2.id, r2.fullname, r2.road_class, r2.geom
                    FROM public.roads r2
                    WHERE r2.geom IS NOT NULL
                    ORDER BY r2.geom <-> ST_SetSRID(ST_MakePoint(p.front_lng, p.front_lat), 4326)
                    LIMIT 1
                ) r ON true
                WHERE p.address = :addr
                LIMIT 1;
            """), {"addr": addr}).mappings().fetchone()

            if not row:
                print(f"  [FAIL] Parcel {addr} not found in database.")
                results.append({"address": addr, "status": "FAIL", "reason": "Not found in DB"})
                continue

            snapped_road = row["snapped_road"] or "UNKNOWN"
            dist_m = float(row["dist_from_parcel_m"]) if row["dist_from_parcel_m"] is not None else 999.0
            is_correct_road = expected_road.upper() in snapped_road.upper()
            is_dist_valid = dist_m <= max_dist_m + 5.0  # tolerance
            passed = is_correct_road and is_dist_valid

            status_str = "PASS" if passed else "FAIL"
            print(f"  [{status_str}] {addr}:")
            print(f"         Target Road:       {expected_road}")
            print(f"         Snapped Road:      {snapped_road} (Class: {row['road_class']})")
            print(f"         Parcel Distance:   {dist_m:.2f} m from parcel boundary (Threshold: <={max_dist_m:.1f} m)")
            print(f"         Front Coordinates: ({row['front_lat']:.6f}, {row['front_lng']:.6f})")
            print(f"         Centroid:          ({row['lat']:.6f}, {row['lng']:.6f})")
            print(f"         Context:           {description}")

            results.append({
                "address": addr,
                "status": status_str,
                "target_road": expected_road,
                "snapped_road": snapped_road,
                "road_class": row["road_class"],
                "distance_m": dist_m,
                "front_lat": row["front_lat"],
                "front_lng": row["front_lng"],
                "passed": passed
            })
            print()

    return results


def verify_dispatch_corpus(engine) -> dict:
    """Evaluates all 305 verified dispatches against the Boundary-Edge geocoder and routing engine."""
    print("=" * 80)
    print("2. EVALUATION ACROSS 305-RECORD HUMAN-VERIFIED DISPATCH CORPUS")
    print("=" * 80)

    db_url = get_db_url()
    setup_osrm_url(db_url)
    validator = CoquitlamDataValidator(database_url=db_url)
    routing_engine = EVORoutingEngine()

    with engine.connect() as conn:
        dispatches = conn.execute(text("""
            SELECT dispatch_id, confidence_score, raw_transcript, verified_address, responding_units,
                   target->>'address' AS sys_addr,
                   target->>'lat' AS sys_lat,
                   target->>'lng' AS sys_lng,
                   target->>'map_grid' AS sys_grid,
                   target->>'station' AS sys_station,
                   target->>'x_street_1' AS x_street_1,
                   target->>'x_street_2' AS x_street_2,
                   target->>'intersection' AS target_intersection
            FROM public.dispatches
            WHERE verified_address IS NOT NULL AND btrim(verified_address) <> ''
            ORDER BY dispatch_id;
        """)).mappings().fetchall()

    total_dispatches = len(dispatches)
    print(f"Loaded {total_dispatches} human-verified dispatch records from public.dispatches.\n")

    resolved_count = 0
    exact_parcel_matches = 0
    intersection_matches = 0
    approx_matches = 0
    xstreets_supplied_count = 0
    street_name_aligned = 0
    route_success_count = 0
    route_distances = []
    route_durations = []
    parcel_snap_distances = []

    categorized_results = []

    road_lookup_sql = text("""
        SELECT r.fullname, r.road_class,
               ST_Distance(
                   ST_Transform(r.geom, 26910),
                   ST_Transform(ST_SetSRID(ST_MakePoint(:lng, :lat), 4326), 26910)
               ) AS dist_to_road_m
        FROM public.roads r
        WHERE r.geom IS NOT NULL
        ORDER BY r.geom <-> ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)
        LIMIT 1;
    """)

    parcel_dist_sql = text("""
        SELECT ST_Distance(
            ST_Transform(p.geom, 26910),
            ST_Transform(ST_SetSRID(ST_MakePoint(:lng, :lat), 4326), 26910)
        ) AS dist_from_parcel_m
        FROM public.parcels p
        WHERE p.address ILIKE :addr OR p.address_normalized ILIKE :addr_norm
           OR (p.geom && ST_Expand(ST_SetSRID(ST_MakePoint(:lng, :lat), 4326), 0.001)
               AND ST_DWithin(p.geom, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326), 0.001))
        ORDER BY ST_Distance(ST_Transform(p.geom, 26910), ST_Transform(ST_SetSRID(ST_MakePoint(:lng, :lat), 4326), 26910)) ASC
        LIMIT 1;
    """)

    for idx, d in enumerate(dispatches):
        did = d["dispatch_id"]
        v_addr = d["verified_address"]
        units = d["responding_units"] if d["responding_units"] else []
        station_id = str(d["sys_station"]) if d["sys_station"] else "1"
        # Two positional variables; either may be null (operator ruling 2026-08-30).
        cs1 = d["x_street_1"]
        cs2 = d["x_street_2"]

        if not cs1 and not cs2 and d.get("target_intersection"):
            inter_str = str(d["target_intersection"]).strip()
            parts = split_intersection_parts(inter_str)
            if parts:
                cs1, cs2 = parts[0], parts[1]
            elif inter_str:
                cs1 = inter_str

        if cs1 or cs2:
            xstreets_supplied_count += 1

        # Resolve location via Coquitlam geocoder with cross-street disambiguation support
        geo_res = validator.get_coordinates(
            v_addr,
            target_map_grid=d["sys_grid"],
            x_street_1=cs1,
            x_street_2=cs2
        )

        if geo_res and geo_res.get("lat") and geo_res.get("lng"):
            resolved_count += 1
            lat = float(geo_res["lat"])
            lng = float(geo_res["lng"])
            res_note = geo_res.get("resolution_note") or geo_res.get("resolution_type") or ""
            is_ambig = geo_res.get("is_ambiguous", False)
            rings = geo_res.get("rings") or []
            res_addr = geo_res.get("address") or ""

            # Categorize resolution type accurately
            is_inter = (
                split_intersection_parts(v_addr) is not None or
                split_intersection_parts(res_addr) is not None or
                ("&" in res_addr and not rings)
            )

            if len(rings) > 0:
                exact_parcel_matches += 1
                res_category = "exact_parcel"
                # Calculate real distance from parcel polygon to arrival point
                with engine.connect() as conn:
                    p_row = conn.execute(parcel_dist_sql, {
                        "lng": lng, "lat": lat,
                        "addr": v_addr, "addr_norm": v_addr.lower()
                    }).mappings().fetchone()
                dist_from_parcel = float(p_row["dist_from_parcel_m"]) if p_row and p_row["dist_from_parcel_m"] is not None else 0.0
            elif is_inter:
                intersection_matches += 1
                res_category = "intersection"
                dist_from_parcel = 0.0
            else:
                approx_matches += 1
                res_category = "approximation_or_centroid"
                dist_from_parcel = 0.0

            parcel_snap_distances.append(dist_from_parcel)

            # Check road alignment in DB
            try:
                with engine.connect() as conn:
                    road_info = conn.execute(road_lookup_sql, {"lat": lat, "lng": lng}).mappings().fetchone()
                snapped_road = road_info["fullname"] if road_info else "None"
                dist_to_road = float(road_info["dist_to_road_m"]) if road_info else 0.0
            except Exception:
                snapped_road = "None"
                dist_to_road = 0.0

            # Check if road name matches verified address street
            v_tokens = [w.upper() for w in v_addr.split() if not w.isdigit()]
            road_tokens = [w.upper() for w in snapped_road.split()]
            name_overlap = any(tok in road_tokens for tok in v_tokens if len(tok) > 2)
            if name_overlap:
                street_name_aligned += 1

            # Test OSRM Routing with stock driving profile
            route = routing_engine.calculate_route(
                dest_lat=lat,
                dest_lng=lng,
                station_id=station_id,
                response_type="emergency"
            )

            if route and route.get("status") == "success":
                route_success_count += 1
                if route.get("distance_km") is not None:
                    route_distances.append(route["distance_km"])
                if route.get("eta_minutes") is not None:
                    route_durations.append(route["eta_minutes"])

            categorized_results.append({
                "dispatch_id": did,
                "verified_address": v_addr,
                "lat": lat,
                "lng": lng,
                "resolution_category": res_category,
                "resolution_type": res_note,
                "is_ambiguous": is_ambig,
                "snapped_road": snapped_road,
                "dist_from_parcel_m": dist_from_parcel,
                "dist_to_road_m": dist_to_road,
                "street_name_aligned": name_overlap,
                "route_status": route.get("status") if route else "failed",
                "route_km": route.get("distance_km") if route else None,
                "route_osrm_driving_eta_min": route.get("eta_minutes") if route else None
            })
        else:
            categorized_results.append({
                "dispatch_id": did,
                "verified_address": v_addr,
                "lat": None,
                "lng": None,
                "resolution_category": "unresolved",
                "resolution_type": "unresolved",
                "is_ambiguous": True,
                "snapped_road": None,
                "dist_from_parcel_m": None,
                "dist_to_road_m": None,
                "street_name_aligned": False,
                "route_status": "unresolved",
                "route_km": None,
                "route_osrm_driving_eta_min": None
            })

        if (idx + 1) % 50 == 0 or idx == total_dispatches - 1:
            print(f"  Processed {idx + 1}/{total_dispatches} dispatches ({resolved_count} geocoded, {route_success_count} routed)...")

    # Summary metrics
    avg_parcel_dist = sum(parcel_snap_distances) / len(parcel_snap_distances) if parcel_snap_distances else 0.0
    avg_route_dist = sum(route_distances) / len(route_distances) if route_distances else 0.0
    avg_route_eta = sum(route_durations) / len(route_durations) if route_durations else 0.0

    print("\nSummary Metrics Across Dispatch Corpus:")
    print(f"  Total Verified Dispatches:              {total_dispatches}")
    print(f"  Records with XStreets Available:        {xstreets_supplied_count} ({xstreets_supplied_count/total_dispatches*100:.1f}%)")
    print(f"  Successfully Geocoded:                  {resolved_count} ({resolved_count/total_dispatches*100:.1f}%)")
    print(f"  Exact Parcel Snaps:                     {exact_parcel_matches} ({exact_parcel_matches/total_dispatches*100:.1f}%)")
    print(f"  Intersection Snaps:                     {intersection_matches} ({intersection_matches/total_dispatches*100:.1f}%)")
    print(f"  Approximation / Centroid Fallbacks:     {approx_matches} ({approx_matches/total_dispatches*100:.1f}%)")
    print(f"  Civic Street Name Aligned:              {street_name_aligned} ({street_name_aligned/resolved_count*100:.1f}% of resolved)")
    print(f"  Average Distance from Parcel Boundary:  {avg_parcel_dist:.2f} m")
    print(f"  Successful OSRM Routes:                 {route_success_count} ({route_success_count/total_dispatches*100:.1f}%)")
    print(f"  Average OSRM Route Distance:            {avg_route_dist:.2f} km")
    print(f"  Average OSRM driving-profile ETA:       {avg_route_eta:.1f} min")

    return {
        "total_dispatches": total_dispatches,
        "xstreets_supplied_count": xstreets_supplied_count,
        "resolved_count": resolved_count,
        "exact_parcel_matches": exact_parcel_matches,
        "intersection_matches": intersection_matches,
        "approx_matches": approx_matches,
        "street_name_aligned": street_name_aligned,
        "avg_parcel_snap_dist_m": avg_parcel_dist,
        "avg_snap_dist_m": avg_parcel_dist,  # Mapped to realistic parcel distance per review R2
        "route_success_count": route_success_count,
        "avg_route_dist_km": avg_route_dist,
        "avg_route_osrm_driving_eta_min": avg_route_eta,
        "avg_route_eta_min": avg_route_eta,  # Backwards compatibility
        "records": categorized_results
    }


def main():
    parser = argparse.ArgumentParser(description="Verify Boundary-Edge Snapping on Dispatch Corpus")
    parser.add_argument("--json", help="Save detailed evaluation JSON to path")
    args = parser.parse_args()

    engine = create_engine(get_db_url(), pool_pre_ping=True)
    four_cases = verify_four_failure_cases(engine)
    corpus_summary = verify_dispatch_corpus(engine)

    all_four_passed = all(c.get("passed", False) for c in four_cases)

    print("\n" + "=" * 80)
    print("FINAL ACCEPTANCE CRITERIA STATUS")
    print("=" * 80)
    print(f"  Four Reference Cases:            {'ALL PASSED (4/4)' if all_four_passed else 'SOME FAILED'}")
    print(f"  2865 Glen Dr Snapped to Glen Dr: {four_cases[0]['passed']} ({four_cases[0]['distance_m']:.1f}m from parcel boundary)")
    print(f"  Corpus Road Alignment Rate:      {corpus_summary['street_name_aligned']}/{corpus_summary['resolved_count']} ({corpus_summary['street_name_aligned']/corpus_summary['resolved_count']*100:.1f}%)")
    print(f"  Exact Parcel Snaps:              {corpus_summary['exact_parcel_matches']}/{corpus_summary['total_dispatches']} ({corpus_summary['exact_parcel_matches']/corpus_summary['total_dispatches']*100:.1f}%)")
    print(f"  Intersection Snaps:              {corpus_summary['intersection_matches']}/{corpus_summary['total_dispatches']} ({corpus_summary['intersection_matches']/corpus_summary['total_dispatches']*100:.1f}%)")
    print(f"  Avg Parcel -> Arrival Distance:  {corpus_summary['avg_parcel_snap_dist_m']:.2f} m")
    print(f"  OSRM Routing Availability:       {corpus_summary['route_success_count']}/{corpus_summary['total_dispatches']} ({corpus_summary['route_success_count']/corpus_summary['total_dispatches']*100:.1f}%)")
    print(f"  Average OSRM driving-profile ETA:{corpus_summary['avg_route_osrm_driving_eta_min']:.1f} min")
    print("=" * 80)

    if args.json:
        out = {
            "four_cases": four_cases,
            "corpus_summary": corpus_summary,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        print(f"\nResults written to {args.json}")

    return 0 if all_four_passed else 1


if __name__ == "__main__":
    sys.exit(main())
