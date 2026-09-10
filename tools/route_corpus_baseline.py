#!/usr/bin/env python3
"""Route the verified dispatch corpus through the kiosk's OSRM and keep the answer, so that a
profile or graph change can be measured against it route by route before it is deployed.

What it does
------------
For every dispatch with a verified address, the arrival point is resolved the way production
resolves it (CoquitlamDataValidator.get_coordinates: operator entrance -> computed frontage ->
centroid for a parcel; the junction for an intersection; the nearer end for a street section),
and OSRM is asked for the route from each of the four hall aprons with the query production
sends (overview=full, geometries=geojson, steps=true). One row per hall per dispatch: distance,
duration, weight, the road sequence from the steps, how far each end snapped, a hash of the
geometry, and two things the geometry itself reports -- coordinates the route passes twice (an
out-and-back or a loop) and U-turn manoeuvres. The halls that actually responded
(verified_units, else responding_units, through get_unit_station_id) are marked dispatched.

Nothing is estimated: distance and duration are OSRM's own numbers (CLAUDE.md 6.2), an address
that does not resolve is a row with no route, and a route OSRM refuses is a row that says so.
Every dispatch replayed is a real historical record (6.5). Read-only except for --record.

Usage
-----
    # before a profile or graph change: the baseline, on the kiosk
    .venv/bin/python tools/route_corpus_baseline.py --csv /tmp/routes_before.csv \\
        --json /tmp/routes_before.json --record \\
        --label "stock car.lua, osrm v26.8.0, extract 2026-08-14" --notes "baseline"

    # after the change: every route that moved, by dispatch id and hall
    .venv/bin/python tools/route_corpus_baseline.py --baseline /tmp/routes_before.json \\
        --csv /tmp/routes_after.csv --json /tmp/routes_after.json

    # one call, every hall, the full road sequence
    .venv/bin/python tools/route_corpus_baseline.py --dispatch-id DISP-2026-549E0F

--label names the graph and profile under test. It becomes model_version on the recorded row
and is required with --record, because the tool cannot read the profile out of a running
router. What it can observe it records beside the label: OSRM's weight_name from the
responses, and the modification time of the edge-weight file backend/data/osrm/vancouver.osrm.enw
when that file is on this machine (it is on the kiosk; a laptop run records null).

From a laptop, point it at the kiosk: DATABASE_URL to the kiosk's Postgres and
--osrm http://100.95.146.94:5000.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime

import _repo  # noqa: F401  tools/_repo.py puts backend/ and services/*/src on sys.path
import harness_common as hc  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from gis_service.geocoder import CoquitlamDataValidator  # noqa: E402
from gis_service.routing_engine import (  # noqa: E402
    EVORoutingEngine, FIRE_HALLS, get_unit_station_id,
)

# The query production sends (routing_engine._get_osrm_endpoints). The baseline has to ask the
# router the same question, or a difference could be the question and not the graph.
OSRM_QUERY = "overview=full&geometries=geojson&steps=true"
HALLS = ("1", "2", "3", "4")
ENW = os.path.join(str(_repo.ROOT), "backend", "data", "osrm", "vancouver.osrm.enw")

# A route "moved" when its geometry hash differs, or distance or duration differ by more than
# this. OSRM reports distance to 0.1 m and duration to 0.1 s; anything above rounding noise.
MOVED_M = 0.5
MOVED_S = 0.5


# ------------------------------------------------------------------------------------ OSRM
def osrm_base(args) -> str:
    if args.osrm:
        return args.osrm.rstrip("/")
    for key in ("OSRM_BACKEND_URL", "OSRM_ROUTER_URL", "OSRM_URL"):
        v = os.environ.get(key, "").strip()
        if v:
            return v.rstrip("/")
    return "http://127.0.0.1:5000"


def fetch_route(base: str, o_lat: float, o_lng: float, d_lat: float, d_lng: float) -> dict:
    url = f"{base}/route/v1/driving/{o_lng},{o_lat};{d_lng},{d_lat}?{OSRM_QUERY}"
    req = urllib.request.Request(url, headers={"User-Agent": "CFREVOApp/1.0 (route_corpus_baseline)"})
    try:
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # OSRM answers NoRoute / NoSegment with a 400 and a JSON body that names the reason.
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            return {"code": f"HTTP {e.code}"}
    except Exception as e:  # unreachable router, timeout
        return {"code": f"unreachable: {type(e).__name__}"}


def describe(data: dict) -> dict:
    """The facts in one OSRM response. A response with no route is just its code."""
    code = data.get("code")
    if code != "Ok" or not data.get("routes"):
        return {"code": code or "no-response"}
    route = data["routes"][0]
    coords = (route.get("geometry") or {}).get("coordinates") or []
    steps = [s for leg in route.get("legs", []) for s in leg.get("steps", [])]

    roads, prev = [], None
    for s in steps:
        if s["maneuver"]["type"] in ("depart", "arrive"):
            continue
        name = s.get("name") or "(unnamed)"
        if name != prev:
            roads.append(name)
        prev = name
    uturns = sum(1 for s in steps if str(s["maneuver"].get("modifier", "")) == "uturn")

    # A coordinate that appears again later in the line is a node the route passes twice:
    # an out-and-back, a turnaround, a loop. The geometry says so; no threshold involved.
    seen, repeated, last = set(), 0, None
    rounded = []
    for c in coords:
        key = (round(c[0], 6), round(c[1], 6))
        rounded.append(list(key))
        if key in seen and key != last:
            repeated += 1
        seen.add(key)
        last = key

    wps = data.get("waypoints") or [{}, {}]
    return {
        "code": code,
        "distance_m": round(float(route["distance"]), 1),
        "duration_s": round(float(route["duration"]), 1),
        "weight": round(float(route.get("weight", 0.0)), 1),
        "weight_name": route.get("weight_name"),
        "n_steps": len(steps),
        "n_nodes": len(coords),
        "uturns": uturns,
        "repeated_nodes": repeated,
        "origin_snap_m": round(float(wps[0].get("distance", 0.0)), 1),
        "dest_snap_m": round(float(wps[-1].get("distance", 0.0)), 1),
        "dest_snap_name": wps[-1].get("name") or "",
        "roads": " > ".join(roads),
        "geometry_md5": hashlib.md5(json.dumps(rounded).encode("utf-8")).hexdigest()[:12],
    }


# ---------------------------------------------------------------------------------- corpus
def load_corpus(engine, args) -> list[dict]:
    where = ["verified_address IS NOT NULL", "btrim(verified_address) <> ''",
             # PA pages the listener captured and the operator tagged "[PA]" in the review
             # notes are not dispatches (punch-list #14). The same predicate as
             # harness_chain.py and backtest_parser_corpus.py, so the corpora agree.
             "position('[PA]' in coalesce(target->>'review_notes', '')) = 0"]
    dw, params = hc.date_where(args)
    where += dw
    if args.dispatch_id:
        where.append("dispatch_id = :did")
        params["did"] = args.dispatch_id
    sql = ("SELECT dispatch_id, timestamp, verified_address, verified_units, responding_units, "
           "verified_map_grid, verified_x_street_1, verified_x_street_2 "
           "FROM public.dispatches WHERE " + " AND ".join(where) + " ORDER BY timestamp")
    if args.limit:
        sql += " LIMIT :limit"
        params["limit"] = int(args.limit)
    with engine.connect() as conn:
        return [dict(r) for r in conn.execute(text(sql), params).mappings().all()]


# ------------------------------------------------------------------------------------ main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    hc.add_common_args(ap)
    ap.add_argument("--csv", help="one row per hall per dispatch")
    ap.add_argument("--osrm", help="router base URL (default: OSRM_* from the environment, else http://127.0.0.1:5000)")
    ap.add_argument("--label", help="the graph and profile under test, e.g. 'stock car.lua, osrm v26.8.0, extract 2026-08-14'; required with --record")
    ap.add_argument("--dispatch-id", help="one call only, printed in full")
    args = ap.parse_args()
    if args.record and not args.label:
        sys.exit("--record needs --label: name the graph and profile this run measured")

    db_url = hc.database_url()
    base = osrm_base(args)
    engine = create_engine(db_url, pool_pre_ping=True)
    validator = CoquitlamDataValidator(database_url=db_url)
    router = EVORoutingEngine()

    corpus = load_corpus(engine, args)
    print(f"{len(corpus)} verified dispatches; router {base}")

    rows: list[dict] = []
    routes: dict[str, dict] = {}
    cache: dict[tuple, dict | None] = {}
    unresolved, failed = [], []
    stamps = []

    for i, d in enumerate(corpus, 1):
        did = d["dispatch_id"]
        addr = d["verified_address"].strip()
        grid = (d["verified_map_grid"] or "").strip() or None
        xs1 = (d["verified_x_street_1"] or "").strip() or None
        xs2 = (d["verified_x_street_2"] or "").strip() or None
        units = [u for u in (d["verified_units"] or d["responding_units"] or []) if u]
        dispatched = {get_unit_station_id(u) for u in units}
        stamps.append(d["timestamp"])

        key = (addr.upper(), grid, xs1, xs2)
        if key not in cache:
            try:
                cache[key] = validator.get_coordinates(addr, target_map_grid=grid,
                                                       x_street_1=xs1, x_street_2=xs2)
            except Exception as e:
                print(f"  {did}: geocoder raised {type(e).__name__}: {e}", file=sys.stderr)
                cache[key] = None
        geo = cache[key]

        base_row = {
            "dispatch_id": did,
            "timestamp": d["timestamp"].isoformat() if d["timestamp"] else "",
            "verified_address": addr,
            "resolved_address": (geo or {}).get("address") or "",
            "resolution": ((geo or {}).get("arrival_point") or (geo or {}).get("location_type")
                           or (geo or {}).get("resolution_note") or ""),
            "is_ambiguous": bool((geo or {}).get("is_ambiguous")),
            "lat": (geo or {}).get("lat"),
            "lng": (geo or {}).get("lng"),
        }
        if not geo or geo.get("lat") is None or geo.get("lng") is None:
            unresolved.append(did)
            rows.append({**base_row, "hall": "", "dispatched": "", "units": " ".join(units),
                         "crow_m": None, "code": "unresolved"})
            continue

        lat, lng = float(geo["lat"]), float(geo["lng"])
        endpoints = geo.get("endpoints") or None
        for h in HALLS:
            hall = FIRE_HALLS[h]
            d_lat, d_lng = lat, lng
            if endpoints:
                # A street section: production routes each unit to the end nearer its own
                # hall (payload_builder -> calculate_units_routing -> _nearest_destination).
                picked = router._nearest_destination(f"E{h}", endpoints)
                if picked:
                    d_lng, d_lat = float(picked[0]), float(picked[1])
            desc = describe(fetch_route(base, hall["lat"], hall["lng"], d_lat, d_lng))
            row = {
                **base_row,
                "hall": h,
                "dispatched": h in dispatched,
                "units": " ".join(u for u in units if get_unit_station_id(u) == h),
                "crow_m": round(hc.haversine_m(hall["lat"], hall["lng"], d_lat, d_lng), 1),
                "dest_lat": d_lat, "dest_lng": d_lng,
                **desc,
            }
            rows.append(row)
            rk = f"{did}|{h}"
            # "p" is the destination actually routed to. --baseline needs it: the corpus is
            # re-geocoded every run, so a geocoder or parcel change moves the destination and
            # then the route, and that must not be read as a graph or profile change.
            dest_p = [round(d_lat, 6), round(d_lng, 6)]
            if desc["code"] == "Ok":
                routes[rk] = {"d": desc["distance_m"], "t": desc["duration_s"],
                              "g": desc["geometry_md5"], "r": desc["repeated_nodes"],
                              "u": desc["uturns"], "x": h in dispatched, "roads": desc["roads"],
                              "a": addr, "p": dest_p}
            else:
                routes[rk] = {"code": desc["code"], "x": h in dispatched, "a": addr, "p": dest_p}
                failed.append(rk)

        if args.dispatch_id:
            print(f"\n{did}  {addr} -> {base_row['resolved_address']} ({base_row['resolution']}) "
                  f"{lat:.6f},{lng:.6f}  units {units or '-'}")
            for r in rows:
                if r["dispatch_id"] == did and r.get("hall"):
                    flag = "*" if r["dispatched"] else " "
                    if r["code"] == "Ok":
                        print(f" {flag}hall {r['hall']}: {r['distance_m']/1000:.2f} km  {r['duration_s']/60:.1f} min  "
                              f"steps {r['n_steps']}  uturns {r['uturns']}  repeated nodes {r['repeated_nodes']}  "
                              f"snap {r['origin_snap_m']} m -> {r['dest_snap_m']} m ({r['dest_snap_name']})")
                        print(f"          {r['roads']}")
                    else:
                        print(f" {flag}hall {r['hall']}: {r['code']}")
        elif i % 50 == 0 or i == len(corpus):
            print(f"  {i}/{len(corpus)} calls, {len(routes)} routes, {len(unresolved)} unresolved, {len(failed)} failed")

    engine.dispose()

    # ------------------------------------------------------------------------- summary
    ok_rows = [r for r in rows if r.get("code") == "Ok"]
    disp = [r for r in ok_rows if r["dispatched"]]

    def stats(rs):
        km = [r["distance_m"] / 1000.0 for r in rs]
        mn = [r["duration_s"] / 60.0 for r in rs]
        return {
            "n": len(rs),
            "distance_km": {"median": round(hc.quantile(km, 0.5), 2) if km else None,
                            "p90": round(hc.quantile(km, 0.9), 2) if km else None},
            "duration_min": {"median": round(hc.quantile(mn, 0.5), 1) if mn else None,
                             "p90": round(hc.quantile(mn, 0.9), 1) if mn else None},
            "repeated_node_routes": sum(1 for r in rs if r["repeated_nodes"]),
            "uturn_routes": sum(1 for r in rs if r["uturns"]),
        }

    weight_names = sorted({r["weight_name"] for r in ok_rows if r.get("weight_name")})
    n_calls = len(corpus)
    summary = {
        "stage": "routing",
        "ran_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "osrm_url": base,
        "weight_name": weight_names,
        "graph_enw_mtime": (datetime.fromtimestamp(os.path.getmtime(ENW)).isoformat(timespec="seconds")
                            if os.path.exists(ENW) else None),
        "n_calls": n_calls,
        "n_resolved": n_calls - len(unresolved),
        "unresolved": unresolved,
        "n_routes": len(routes),
        "routes_ok": len(ok_rows),
        "routes_failed": failed,
        "dispatched": stats(disp),
        "all_halls": stats(ok_rows),
        "by_hall": {h: stats([r for r in ok_rows if r["hall"] == h]) for h in HALLS},
        "repeated_node_routes": sorted(f"{r['dispatch_id']}|{r['hall']}" for r in ok_rows if r["repeated_nodes"]),
        "uturn_routes": sorted(f"{r['dispatch_id']}|{r['hall']}" for r in ok_rows if r["uturns"]),
    }
    ds = summary["dispatched"]
    headline = (f"{n_calls} calls, {summary['n_resolved']} placed, {len(ok_rows)}/{len(routes)} routes; "
                f"dispatched median {ds['distance_km']['median']} km / {ds['duration_min']['median']} min; "
                f"{ds['repeated_node_routes']} revisit a node, {ds['uturn_routes']} U-turn")
    summary["headline"] = headline

    print("\nSUMMARY")
    print(f"  {headline}")
    print(f"  weight_name {weight_names}  graph .enw mtime {summary['graph_enw_mtime']}")
    for h in HALLS:
        s = summary["by_hall"][h]
        print(f"  hall {h}: {s['n']} routes, median {s['distance_km']['median']} km / {s['duration_min']['median']} min, "
              f"p90 {s['distance_km']['p90']} km / {s['duration_min']['p90']} min, "
              f"{s['repeated_node_routes']} revisit a node, {s['uturn_routes']} U-turn")
    if unresolved:
        print(f"  unresolved ({len(unresolved)}): {', '.join(unresolved[:20])}{' ...' if len(unresolved) > 20 else ''}")
    if failed:
        print(f"  failed routes ({len(failed)}): {', '.join(failed[:20])}{' ...' if len(failed) > 20 else ''}")
    if summary["repeated_node_routes"]:
        print(f"  routes that pass a node twice: {', '.join(summary['repeated_node_routes'][:30])}")
    if summary["uturn_routes"]:
        print(f"  routes with a U-turn step: {', '.join(summary['uturn_routes'][:30])}")

    # ----------------------------------------------------------------------------- output
    if args.csv:
        cols = ["dispatch_id", "timestamp", "verified_address", "resolved_address", "resolution",
                "is_ambiguous", "lat", "lng", "hall", "dispatched", "units", "dest_lat", "dest_lng",
                "crow_m", "code", "distance_m", "duration_s", "weight", "n_steps", "n_nodes", "uturns",
                "repeated_nodes", "origin_snap_m", "dest_snap_m", "dest_snap_name", "roads", "geometry_md5"]
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        print(f"\n{len(rows)} rows written to {args.csv}")

    if args.json:
        hc.save_summary(args.json, {**summary, "routes": routes})

    if args.baseline:
        compare(routes, summary, hc.load_summary(args.baseline))

    if args.record:
        compact = {k: {kk: v[kk] for kk in ("d", "t", "g", "r", "u", "x", "p", "code") if kk in v}
                   for k, v in routes.items()}
        period = (min(stamps).date(), max(stamps).date()) if stamps else None
        hc.record_run(stage="routing", n=n_calls, args=args, model_version=args.label,
                      metrics={**summary, "routes": compact}, period=period, headline=headline)
    return 0


# --------------------------------------------------------------------------------- compare
def compare(routes: dict, summary: dict, baseline: dict) -> None:
    """Every route that moved against a --json written earlier, by dispatch id and hall, the
    largest change in duration first. Direction is the operator's to judge: a route that got
    shorter is not better unless it is the road a crew would take."""
    before = baseline.get("routes") or {}
    both = sorted(set(routes) & set(before))
    only_now = sorted(set(routes) - set(before))
    only_then = sorted(set(before) - set(routes))
    moved, dest_moved, nodes_only = [], [], []
    for k in both:
        c, b = routes[k], before[k]
        if c.get("p") and b.get("p") and c["p"] != b["p"]:
            # The destination itself moved since the baseline (a geocoder, parcel or
            # arrival-point change). Whatever the route did is not the graph's doing.
            dest_moved.append((k, b, c))
            continue
        if ("d" in c) != ("d" in b):
            moved.append((k, b, c, "route appeared" if "d" in c else "route lost"))
        elif "d" in c and (c["g"] != b["g"] or abs(c["d"] - b["d"]) > MOVED_M or abs(c["t"] - b["t"]) > MOVED_S):
            if abs(c["d"] - b["d"]) <= MOVED_M and abs(c["t"] - b["t"]) <= MOVED_S:
                # Same distance and time to the tenth: a node coordinate moved (an OSM edit),
                # the route did not. Counted, not listed.
                nodes_only.append((k, b, c))
            else:
                moved.append((k, b, c, "geometry" if c["g"] != b["g"] else "metrics"))

    print(f"\nCHANGE VS BASELINE ({baseline.get('ran_at', '?')}, {baseline.get('osrm_url', '?')})")
    print(f"  routes compared {len(both)}, unchanged {len(both) - len(moved) - len(nodes_only) - len(dest_moved)}, "
          f"moved {len(moved)} (dispatched: {sum(1 for _, _, c, _ in moved if c.get('x'))}), "
          f"node coordinates only {len(nodes_only)}, destination itself moved {len(dest_moved)}")
    if only_now or only_then:
        print(f"  corpus drift: {len(only_now)} routes only in this run, {len(only_then)} only in the baseline")
    if dest_moved:
        print("  destinations that moved since the baseline (not the graph's doing):")
        seen = set()
        for k, b, c in dest_moved:
            did = k.split("|")[0]
            if did in seen:
                continue
            seen.add(did)
            print(f"    {did}  {c.get('a', '')}: {b['p'][0]:.5f},{b['p'][1]:.5f} -> {c['p'][0]:.5f},{c['p'][1]:.5f}")

    def dur(x):
        return x["t"] if "t" in x else None

    moved.sort(key=lambda m: -abs((dur(m[2]) or 0) - (dur(m[1]) or 0)))
    for k, b, c, why in moved:
        did, h = k.split("|")
        flag = "*" if c.get("x") else " "
        if "d" in b and "d" in c:
            # ASCII only: this line reaches a cp1252 console when run from the laptop.
            print(f" {flag}{did} hall {h}  {c.get('a', '')}: {b['d']/1000:.2f} -> {c['d']/1000:.2f} km  "
                  f"{b['t']/60:.1f} -> {c['t']/60:.1f} min  ({why}; {c['d']-b['d']:+.0f} m, {c['t']-b['t']:+.0f} s)")
            if why == "geometry":
                print(f"     was: {b.get('roads', '?')}")
                print(f"     now: {c.get('roads', '?')}")
        else:
            print(f" {flag}{did} hall {h}  {c.get('a', '')}: {why}  ({b.get('code', 'Ok')} -> {c.get('code', 'Ok')})")

    scalar_now = {k: v for k, v in summary.items() if k in ("dispatched", "all_halls", "by_hall", "n_resolved", "routes_ok")}
    scalar_then = {k: v for k, v in baseline.items() if k in ("dispatched", "all_halls", "by_hall", "n_resolved", "routes_ok")}
    hc.diff_summaries(scalar_now, scalar_then, title="SUMMARY NUMBERS THAT MOVED")


if __name__ == "__main__":
    sys.exit(main())
