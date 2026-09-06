#!/usr/bin/env python3
"""Level crossings in the OSM extract the kiosk routes on, against the hand-entered kiosk list (#21).

CLAUDE.md 6.2 names the source for rail crossings: `railway=level_crossing` nodes in OSM. The
kiosk hazard layer (`frontend/src/components/map/railroadCrossings.js`) carries four hand-placed
points instead. This reads every level_crossing node inside the City bounding box from the same
extract OSRM was built from, and prints each against the nearest hand-entered point, and each
hand-entered point against the nearest OSM node, so the two lists can be reconciled by eye.

Kiosk only (the extract is git-ignored). Needs pyosmium in the venv: `.venv/bin/pip install osmium`.

    .venv/bin/python tools/osm_level_crossings.py
    .venv/bin/python tools/osm_level_crossings.py --json > crossings.json
"""
import argparse
import json
import math
import os
import re
import sys

import _repo  # noqa: F401  (repository root on sys.path)

# CLAUDE.md section 5, the authoritative City bounding box; kept in step with isWithinCoquitlam().
LAT_MIN, LAT_MAX = 49.20, 49.39
LNG_MIN, LNG_MAX = -122.92, -122.70

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


def read_osm_crossings(pbf):
    import osmium

    class Handler(osmium.SimpleHandler):
        def __init__(self):
            super().__init__()
            self.rows = []

        def node(self, n):
            if n.tags.get("railway") != "level_crossing" or not n.location.valid():
                return
            lat, lng = n.location.lat, n.location.lon
            if not (LAT_MIN <= lat <= LAT_MAX and LNG_MIN <= lng <= LNG_MAX):
                return
            self.rows.append({
                "osm_id": n.id, "lat": round(lat, 7), "lng": round(lng, 7),
                "name": n.tags.get("name"),
                "crossing": n.tags.get("crossing"),
                "barrier": n.tags.get("crossing:barrier"),
                "light": n.tags.get("crossing:light"),
                "bell": n.tags.get("crossing:bell"),
            })

    h = Handler()
    h.apply_file(pbf)
    return sorted(h.rows, key=lambda r: (r["lat"], r["lng"]))


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
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()
    if not os.path.exists(args.pbf):
        print(f"no extract at {args.pbf}; this runs on the kiosk", file=sys.stderr)
        return 2

    kiosk = read_kiosk_list(KIOSK_LIST)
    osm = read_osm_crossings(args.pbf)
    for r in osm:
        k, d = nearest(r, kiosk)
        r["nearest_kiosk"] = k["id"] if k else None
        r["nearest_kiosk_m"] = round(d) if d is not None else None
    for k in kiosk:
        o, d = nearest(k, osm)
        k["nearest_osm"] = o["osm_id"] if o else None
        k["nearest_osm_m"] = round(d) if d is not None else None

    if args.json:
        json.dump({"pbf": args.pbf, "pbf_mtime": os.path.getmtime(args.pbf), "osm": osm, "kiosk": kiosk},
                  sys.stdout, indent=1)
        return 0

    print(f"extract: {args.pbf}")
    print(f"railway=level_crossing nodes inside the City bounding box: {len(osm)}")
    print(f"hand-entered points in railroadCrossings.js: {len(kiosk)}\n")
    print(f"{'osm id':>12} {'lat':>11} {'lng':>12} {'barrier':<10} {'light':<6} {'name':<28} nearest kiosk point")
    for r in osm:
        print(f"{r['osm_id']:>12} {r['lat']:>11.6f} {r['lng']:>12.6f} {str(r['barrier'] or '-'):<10} "
              f"{str(r['light'] or '-'):<6} {str(r['name'] or '-')[:28]:<28} {r['nearest_kiosk']} at {r['nearest_kiosk_m']} m")
    print()
    print("hand-entered point -> nearest OSM node")
    for k in kiosk:
        print(f"  {k['id']} {k['name']:<26} {k['lat']:.6f} {k['lng']:.6f} -> {k['nearest_osm']} at {k['nearest_osm_m']} m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
