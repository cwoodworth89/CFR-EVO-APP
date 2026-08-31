#!/usr/bin/env python3
"""
verify_ortho_provenance.py
==========================
Confirms that `ortho.mbtiles` actually holds City of Coquitlam 7.5cm orthophotography
and not Esri World Imagery.

Why this exists
---------------
Between the original build and 2026-08-30 the kiosk served a layer labelled "City of
Coquitlam 7.5cm Orthophotos & Maxar" that was Esri World Imagery end to end -- the orthos
had never been ingested. Nothing detected it, because imagery from the wrong source still
looks like imagery. The only reliable check is to compare against the other source
directly: an archive tile that is byte-identical to what Esri serves today IS an Esri tile.

Requires WAN access to server.arcgisonline.com, so run it on the kiosk, not the sandboxed
dev machine.

Usage:
    python3 backend/scripts/verify_ortho_provenance.py [--archive PATH] [--samples N]
"""

import argparse
import hashlib
import math
import sqlite3
import sys
import urllib.request

# Spread across the city so a partial ingest cannot pass by luck.
SAMPLE_POINTS = {
    "Town Centre":     (49.2790, -122.7990),
    "Austin Heights":  (49.2545, -122.8760),
    "Burke Mountain":  (49.3200, -122.7750),
    "Maillardville":   (49.2420, -122.8620),
    "Waddington Pl":   (49.29773, -122.78781),
    "Como Lake":       (49.2610, -122.8480),
}

ESRI_URL = ("https://server.arcgisonline.com/ArcGIS/rest/services/"
            "World_Imagery/MapServer/tile/{z}/{y}/{x}")
USER_AGENT = "CFR-EVO/1.0 (ortho provenance verification)"


def deg2num(lat_deg: float, lon_deg: float, zoom: int):
    """WGS84 -> Slippy XYZ tile coordinates."""
    n = 1 << zoom
    x = int((lon_deg + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(math.radians(lat_deg))) / math.pi) / 2.0 * n)
    return x, y


def fetch_esri(z: int, x: int, y: int):
    url = ESRI_URL.format(z=z, x=x, y=y)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        return urllib.request.urlopen(req, timeout=25).read()
    except Exception as exc:                      # noqa: BLE001 - reported, not raised
        print(f"    ! Esri fetch failed ({exc}); cannot compare this tile")
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--archive",
                    default="/home/tcfire/CFR-EVO-APP/backend/data/tiles/ortho.mbtiles")
    ap.add_argument("--zoom", type=int, default=20, help="zoom to sample (default: 20)")
    args = ap.parse_args()

    conn = sqlite3.connect(f"file:{args.archive}?mode=ro", uri=True)

    zooms = conn.execute(
        "SELECT zoom_level, COUNT(*) FROM tiles GROUP BY zoom_level ORDER BY zoom_level"
    ).fetchall()
    print(f"Archive : {args.archive}")
    print("Zooms   : " + ", ".join(f"z{z}={n:,}" for z, n in zooms))
    print()

    matches_esri = 0
    missing = 0
    genuine = 0

    print(f"{'location':<16} {'archive':>10} {'esri_live':>10}  verdict")
    for name, (lat, lng) in SAMPLE_POINTS.items():
        z = args.zoom
        x, y = deg2num(lat, lng, z)
        n = 1 << z
        row = conn.execute(
            "SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
            (z, x, n - 1 - y),          # MBTiles rows are TMS
        ).fetchone()

        if row is None:
            print(f"{name:<16} {'MISSING':>10} {'-':>10}  no tile at this location")
            missing += 1
            continue

        arch = row[0]
        live = fetch_esri(z, x, y)
        if live is None:
            continue

        same = hashlib.md5(arch).hexdigest() == hashlib.md5(live).hexdigest()
        if same:
            matches_esri += 1
            verdict = "*** ESRI, NOT CITY ORTHO ***"
        else:
            genuine += 1
            verdict = "ok - differs from Esri"
        print(f"{name:<16} {len(arch):>10,} {len(live):>10,}  {verdict}")

    print()
    if matches_esri:
        print(f"FAIL: {matches_esri} sampled tile(s) are byte-identical to Esri World "
              f"Imagery. This archive is not the City orthophotography.")
        return 1
    if missing == len(SAMPLE_POINTS):
        print("FAIL: no tiles found at any sample point. Check the archive and zoom.")
        return 1
    print(f"PASS: {genuine} tile(s) verified distinct from Esri"
          + (f"; {missing} sample point(s) had no tile (check ortho footprint)." if missing else "."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
