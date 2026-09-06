#!/usr/bin/env python3
"""Level crossings in the OSM extract the kiosk routes on, against the hand-entered kiosk list (#21).

CLAUDE.md 6.2 names the source for rail crossings: `railway=level_crossing` nodes in OSM. The
kiosk hazard layer (`frontend/src/components/map/railroadCrossings.js`) carries four hand-placed
points instead. This reads every level_crossing node from the same extract OSRM was built from,
keeps the ones inside the City boundary (`public.city_boundary`, the City's polygon, not the
bounding box) that sit on a road (a `highway` way that is not a footway, path or cycleway),
groups the nodes of one multi-track crossing, and prints each against the nearest hand-entered
point, and each hand-entered point against the nearest OSM node.

Kiosk only (the extract is git-ignored, the boundary is in the kiosk's Postgres). Needs pyosmium
in the venv: `.venv/bin/pip install osmium`.

    .venv/bin/python tools/osm_level_crossings.py
    .venv/bin/python tools/osm_level_crossings.py --all      # every node in the bbox, roads or not
    .venv/bin/python tools/osm_level_crossings.py --json > crossings.json
"""
import argparse
import json
import math
import os
import re
import sys

import _repo  # noqa: F401  (repository root on sys.path)
from harness_common import database_url  # noqa: E402

# CLAUDE.md section 5, the authoritative City bounding box; kept in step with isWithinCoquitlam().
# A first cut only: the polygon in public.city_boundary decides, and the box reaches into Port
# Coquitlam, Port Moody, Burnaby, New Westminster and Surrey.
LAT_MIN, LAT_MAX = 49.20, 49.39
LNG_MIN, LNG_MAX = -122.92, -122.70

# Ways a crew cannot drive: a level crossing on one is a hazard for nobody in an apparatus.
NOT_A_ROAD = {"footway", "path", "cycleway", "steps", "pedestrian", "bridleway", "corridor", "platform"}

# Nodes of one crossing (one per track) group at this distance. Measured from the extract
# 2026-09-05: the tracks of the Westwood St crossing are 5 m apart, the Pitt River Rd ones 4 m;
# 80 m separates any two crossings that share a road name in the City.
CLUSTER_M = 80

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PBF = os.path.join(ROOT, "backend", "data", "osrm", "vancouver.osm.pbf")
KIOSK_LIST = os.path.join(ROOT, "frontend", "src", "components", "map", "railroadCrossings.js")


def haversine_m(lat1, lng1, lat2, lng2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def read_kiosk_list(path):
    """The four hand-entered points, straight out of the JS literal."""
    text = open(path, encoding="utf-8").read()
    rows = []
    for m in re.finditer(r"id: '([^']+)', name: '([^']+)', lat: ([-0-9.]+), lng: ([-0-9.]+)", text):
        rows.append({"id": m.group(1), "name": m.group(2), "lat": float(m.group(3)), "lng": float(m.group(4))})
    return rows


def read_osm(pbf):
    """Pass 1: the crossing nodes in the box. Pass 2: the highway and railway ways through them."""
    import osmium

    class Nodes(osmium.SimpleHandler):
        def __init__(self):
            super().__init__()
            self.rows = {}

        def node(self, n):
            if n.tags.get("railway") != "level_crossing" or not n.location.valid():
                return
            lat, lng = n.location.lat, n.location.lon
            if not (LAT_MIN <= lat <= LAT_MAX and LNG_MIN <= lng <= LNG_MAX):
                return
            self.rows[n.id] = {
                "osm_id": n.id, "lat": round(lat, 7), "lng": round(lng, 7),
                "barrier": n.tags.get("crossing:barrier"), "light": n.tags.get("crossing:light"),
                "roads": [], "rails": [],
            }

    class Ways(osmium.SimpleHandler):
        def __init__(self, rows):
            super().__init__()
            self.rows = rows

        def way(self, w):
            hw, rw = w.tags.get("highway"), w.tags.get("railway")
            if not hw and not rw:
                return
            hit = [r.ref for r in w.nodes if r.ref in self.rows]
            if not hit:
                return
            for ref in hit:
                if hw:
                    self.rows[ref]["roads"].append({"highway": hw, "name": w.tags.get("name"), "way": w.id})
                if rw:
                    self.rows[ref]["rails"].append({
                        "railway": rw, "usage": w.tags.get("usage"), "service": w.tags.get("service"),
                        "operator": w.tags.get("operator"), "name": w.tags.get("name"), "way": w.id})

    nodes = Nodes()
    nodes.apply_file(pbf)
    ways = Ways(nodes.rows)
    ways.apply_file(pbf)
    return sorted(nodes.rows.values(), key=lambda r: (r["lat"], r["lng"]))


def inside_city(rows):
    """Marks each node with public.city_boundary's answer; ST_Covers so the boundary line counts."""
    from sqlalchemy import create_engine, text
    engine = create_engine(database_url())
    with engine.connect() as conn:
        for r in rows:
            got = conn.execute(text("""
                SELECT ST_Covers(geom, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326))
                FROM public.city_boundary LIMIT 1
            """), {"lat": r["lat"], "lng": r["lng"]}).fetchone()
            r["in_city"] = bool(got[0]) if got and got[0] is not None else None


def on_a_road(r):
    return any(w["highway"] not in NOT_A_ROAD for w in r["roads"])


def road_label(r):
    names = sorted({(w["name"] or "unnamed " + w["highway"]) for w in r["roads"] if w["highway"] not in NOT_A_ROAD})
    return " / ".join(names) or "-"


def rail_label(r):
    parts = []
    for w in r["rails"]:
        bits = [w["railway"]]
        if w["usage"]:
            bits.append(w["usage"])
        if w["service"]:
            bits.append(w["service"])
        if w["operator"]:
            bits.append(w["operator"])
        parts.append(" ".join(bits))
    return " / ".join(sorted(set(parts))) or "-"


def cluster(rows):
    """Nodes of one crossing, one per track, become one row; the road name must agree."""
    groups = []
    for r in rows:
        for g in groups:
            if road_label(g["nodes"][0]) == road_label(r) and \
                    haversine_m(g["lat"], g["lng"], r["lat"], r["lng"]) <= CLUSTER_M:
                g["nodes"].append(r)
                g["lat"] = sum(n["lat"] for n in g["nodes"]) / len(g["nodes"])
                g["lng"] = sum(n["lng"] for n in g["nodes"]) / len(g["nodes"])
                break
        else:
            groups.append({"lat": r["lat"], "lng": r["lng"], "nodes": [r]})
    return groups


def nearest(point, rows):
    best, best_d = None, None
    for r in rows:
        d = haversine_m(point["lat"], point["lng"], r["lat"], r["lng"])
        if best_d is None or d < best_d:
            best, best_d = r, d
    return best, best_d


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pbf", default=DEFAULT_PBF)
    ap.add_argument("--all", action="store_true",
                    help="list every node in the bounding box, not only road crossings in the City")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()
    if not os.path.exists(args.pbf):
        print("no extract at " + args.pbf + "; this runs on the kiosk", file=sys.stderr)
        return 2

    kiosk = read_kiosk_list(KIOSK_LIST)
    osm = read_osm(args.pbf)
    inside_city(osm)
    for r in osm:
        k, d = nearest(r, kiosk)
        r["nearest_kiosk"] = k["id"] if k else None
        r["nearest_kiosk_m"] = round(d) if d is not None else None
    for k in kiosk:
        o, d = nearest(k, osm)
        k["nearest_osm"] = o["osm_id"] if o else None
        k["nearest_osm_m"] = round(d) if d is not None else None
        k["nearest_osm_road"] = road_label(o) if o else None
        k["nearest_osm_in_city"] = o["in_city"] if o else None

    city = [r for r in osm if r["in_city"]]
    city_roads = [r for r in city if on_a_road(r)]
    groups = cluster(osm if args.all else city_roads)

    if args.json:
        json.dump({"pbf": args.pbf, "pbf_mtime": os.path.getmtime(args.pbf), "osm": osm, "kiosk": kiosk,
                   "counts": {"bbox": len(osm), "in_city": len(city), "in_city_on_road": len(city_roads),
                              "crossings_grouped": len(groups)}},
                  sys.stdout, indent=1)
        return 0

    print("extract: " + args.pbf)
    print("railway=level_crossing nodes in the bounding box: %d" % len(osm))
    print("  inside public.city_boundary: %d" % len(city))
    print("  inside and on a road (highway way, not foot/path/cycle): %d" % len(city_roads))
    print("  grouped into crossings (nodes within %d m on the same road): %d" % (CLUSTER_M, len(groups)))
    print("hand-entered points in railroadCrossings.js: %d\n" % len(kiosk))
    title = "every node in the box" if args.all else "road crossings inside the City"
    print(title + ":")
    print("%11s %12s %3s %-5s %-12s %-34s %-38s %s" % ("lat", "lng", "trk", "city", "barrier", "road", "rail",
                                                       "nearest kiosk point"))
    for g in groups:
        n0 = g["nodes"][0]
        k, d = nearest(g, kiosk)
        barrier = " / ".join(sorted({str(n["barrier"] or "-") for n in g["nodes"]}))
        print("%11.6f %12.6f %3d %-5s %-12s %-34s %-38s %s at %s m" % (
            g["lat"], g["lng"], len(g["nodes"]), str(n0["in_city"]), barrier, road_label(n0)[:34],
            rail_label(n0)[:38], k["id"] if k else "-", round(d) if d is not None else "-"))
    print()
    print("hand-entered point -> nearest OSM node")
    for k in kiosk:
        print("  %s %-26s %.6f %.6f -> %s at %s m, road %s, in city %s" % (
            k["id"], k["name"], k["lat"], k["lng"], k["nearest_osm"], k["nearest_osm_m"],
            k["nearest_osm_road"], k["nearest_osm_in_city"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
