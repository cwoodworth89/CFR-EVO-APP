#!/usr/bin/env python3
"""
verify_ortho_provenance.py
==========================
Confirms `ortho.mbtiles` holds exactly what the City of Coquitlam publishes, by
comparing sampled tiles byte-for-byte against the live `Imagery_2025` service.

Why this test and not the previous one
--------------------------------------
The first version of this script asked the wrong question. It compared archive
tiles against **Esri World Imagery** and passed when they differed, on the theory
that "different from Esri" meant "genuinely City orthophotography."

That premise was disproved on 2026-08-31. Esri's World Imagery over Coquitlam IS
the City's own 2025 capture, contributed through Esri's community programme --
differenced at a car park, every vehicle cancelled out (mean absolute difference
12.5/255, and not one car-shaped ghost). So "differs from Esri" only ever meant
"processed differently", never "from a different source", and the script returned
a confident PASS on a question it could not answer. That is the exact failure mode
CLAUDE.md 6.1 exists to prevent, so it is recorded here rather than quietly fixed.

The archive is now crawled directly from the City's cache, which makes a much
stronger test available: the tiles should be **byte-identical** to what the City
serves. That is a positive identity check rather than an exclusion, and it fails
loudly if anything re-encodes, resamples or substitutes a tile in the pipeline.

Requires WAN access to geodata.coquitlam.ca, so run it on the kiosk.

Usage:
    python3 backend/scripts/verify_ortho_provenance.py [--archive PATH] [--zoom Z]
"""

import argparse
import hashlib
import math
import sqlite3
import sys
import urllib.request

CITY_TILE = ("https://geodata.coquitlam.ca/arcgis/rest/services/"
             "CachedServices/Imagery_2025/MapServer/tile/{z}/{row}/{col}")
USER_AGENT = "CFR-EVO/1.0 (ortho provenance verification)"

# Spread across the city so a partial crawl cannot pass by luck.
SAMPLE_POINTS = {
    "Town Centre":    (49.2790, -122.7990),
    "Austin Heights": (49.2545, -122.8760),
    "Burke Mountain": (49.3200, -122.7750),
    "Maillardville":  (49.2420, -122.8620),
    "Waddington Pl":  (49.29773, -122.78781),
    "Como Lake":      (49.2610, -122.8480),
}


def deg2num(lat_deg, lon_deg, zoom):
    n = 1 << zoom
    x = int((lon_deg + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(math.radians(lat_deg))) / math.pi) / 2.0 * n)
    return x, y


def fetch_city(z, x, y):
    url = CITY_TILE.format(z=z, row=y, col=x)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        return urllib.request.urlopen(req, timeout=25).read()
    except Exception as exc:                       # noqa: BLE001 - reported, not raised
        print(f"    ! City fetch failed ({exc})")
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--archive",
                    default="/home/tcfire/CFR-EVO-APP/backend/data/tiles/ortho.mbtiles")
    ap.add_argument("--zoom", type=int, default=20,
                    help="zoom to sample (default 20 -- the City's deepest cached level)")
    args = ap.parse_args()

    conn = sqlite3.connect(f"file:{args.archive}?mode=ro", uri=True)
    zooms = conn.execute(
        "SELECT zoom_level, COUNT(*) FROM tiles GROUP BY zoom_level ORDER BY zoom_level"
    ).fetchall()
    print(f"Archive : {args.archive}")
    print("Zooms   : " + ", ".join(f"z{z}={n:,}" for z, n in zooms) + "\n")

    identical = differing = missing = 0
    print(f"{'location':<16}{'archive':>10}{'city_live':>11}  verdict")
    for name, (lat, lng) in SAMPLE_POINTS.items():
        z = args.zoom
        x, y = deg2num(lat, lng, z)
        row = conn.execute(
            "SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
            (z, x, (1 << z) - 1 - y),              # MBTiles rows are TMS
        ).fetchone()
        if row is None:
            print(f"{name:<16}{'MISSING':>10}{'-':>11}  no tile in the archive")
            missing += 1
            continue

        live = fetch_city(z, x, y)
        if live is None:
            continue

        if hashlib.md5(row[0]).hexdigest() == hashlib.md5(live).hexdigest():
            identical += 1
            verdict = "identical to the City's tile"
        else:
            differing += 1
            verdict = "*** DIFFERS from the City's tile ***"
        print(f"{name:<16}{len(row[0]):>10,}{len(live):>11,}  {verdict}")

    conn.close()
    print()
    if differing:
        print(f"FAIL: {differing} tile(s) differ from what the City serves. The crawl should "
              f"store tiles verbatim -- something re-encoded or substituted them.")
        return 1
    if missing == len(SAMPLE_POINTS):
        print("FAIL: no tiles found at any sample point. Check the archive and zoom.")
        return 1
    print(f"PASS: {identical} tile(s) byte-identical to the City's published imagery"
          + (f"; {missing} sample point(s) had no tile." if missing else "."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
