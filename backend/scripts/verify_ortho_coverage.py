#!/usr/bin/env python3
"""
verify_ortho_coverage.py
========================
Answers the question a crawl failure count cannot: WHICH tiles are missing from
ortho.mbtiles, and does their absence have a legitimate cause?

compile_mbtiles.py reports failures as a bare count -- download_tile() returns
None and the caller increments a counter, discarding the coordinates. That is
the same defect recorded as punch-list #43 one script over: a count with no
cause looks identical whether the failures are scattered network noise or a
systematic hole over one neighbourhood.

This diffs the archive against the expected tile grid and classifies every
missing tile as either OUTSIDE the City's published imagery extent (expected --
our coverage polygon carries a 1 km mutual-aid buffer that overhangs it) or
INSIDE it (a real gap worth re-running the resumable crawler for).

Usage:
    python3 backend/scripts/verify_ortho_coverage.py [--archive PATH]
"""

import argparse
import importlib.util
import os
import sqlite3
import sys

# City of Coquitlam Imagery_2025 fullExtent, EPSG:3857, read from the service
# metadata at .../CachedServices/Imagery_2025/MapServer?f=json on 2026-08-31.
IMAGERY_XMIN, IMAGERY_YMIN = -13681108.1, 6311679.7
IMAGERY_XMAX, IMAGERY_YMAX = -13648995.0, 6336654.3
R = 20037508.342789244


def tile_bounds_3857(z, x, y):
    n = 2 ** z
    size = 2 * R / n
    return (-R + x * size, R - (y + 1) * size, -R + (x + 1) * size, R - y * size)


def outside_imagery(z, x, y):
    a, b, c, d = tile_bounds_3857(z, x, y)
    return c < IMAGERY_XMIN or a > IMAGERY_XMAX or d < IMAGERY_YMIN or b > IMAGERY_YMAX


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--archive",
                    default=os.path.join(os.path.dirname(here), "data", "tiles", "ortho.mbtiles"))
    args = ap.parse_args()

    spec = importlib.util.spec_from_file_location("cm", os.path.join(here, "compile_mbtiles.py"))
    cm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cm)
    cfg = cm.LAYER_CONFIGS["ortho"]

    conn = sqlite3.connect(f"file:{args.archive}?mode=ro", uri=True)
    have = {(z, x, (1 << z) - 1 - r)                       # MBTiles rows are TMS
            for z, x, r in conn.execute("SELECT zoom_level, tile_column, tile_row FROM tiles")}
    conn.close()
    print(f"Archive : {args.archive}\nHolds   : {len(have):,} tiles\n")

    print(f"{'zoom':<6}{'expected':>10}{'present':>10}{'missing':>10}"
          f"{'  outside':>12}{'  INSIDE':>10}")
    tot_missing = tot_inside = 0
    for z in range(cfg["min_zoom"], cfg["max_zoom"] + 1):
        expect = cm.filter_tiles_to_city(
            cm.calculate_tiles(cm.CITY_MIN_LAT, cm.CITY_MIN_LON,
                               cm.CITY_MAX_LAT, cm.CITY_MAX_LON, z))
        missing = [t for t in expect if t not in have]
        outside = [t for t in missing if outside_imagery(*t)]
        inside = len(missing) - len(outside)
        tot_missing += len(missing)
        tot_inside += inside
        print(f"z{z:<5}{len(expect):>10,}{len(expect)-len(missing):>10,}"
              f"{len(missing):>10,}{len(outside):>12,}{inside:>10,}")

    print(f"\nmissing total : {tot_missing:,}")
    print(f"  of which outside the City's imagery extent (expected): {tot_missing - tot_inside:,}")
    print(f"  of which INSIDE it (real gaps): {tot_inside:,}")
    if tot_inside:
        print("\nRe-run the crawler -- it is resumable and will retry exactly these:")
        print("  python3 backend/scripts/compile_mbtiles.py --layer ortho --workers 8")
        return 1
    print("\nPASS: every missing tile lies outside the published imagery extent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
