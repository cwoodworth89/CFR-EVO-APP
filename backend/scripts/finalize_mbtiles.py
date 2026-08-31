#!/usr/bin/env python3
"""
finalize_mbtiles.py
Checkpoints WAL and sets journal_mode to DELETE on all MBTiles databases
so they are cleanly readable by mbtileserver in read-only volume mounts.
"""
import sqlite3
import glob
import os
import sys
from pathlib import Path

def finalize_all(tiles_dir):
    pattern = os.path.join(tiles_dir, "*.mbtiles")
    files = glob.glob(pattern)
    print(f"Found {len(files)} MBTiles archives to finalize in {tiles_dir}")

    failures = []
    for f in sorted(files):
        try:
            _finalize_one(f)
        except Exception as exc:                  # noqa: BLE001 - reported, not raised
            # One unfinalizable archive must not skip the rest. On 2026-08-31 a
            # chmod PermissionError on ortho.mbtiles (written as root by the GDAL
            # container) aborted this run after the FIRST archive, leaving three
            # untouched. They happened to already be in DELETE mode so it looked
            # survivable -- the same near-miss as 2026-08-27. A WAL-mode archive
            # fails only later, under the read-only mount, so this has to be both
            # loud and complete.
            print(f"  !! FAILED: {exc}")
            failures.append((f, exc))

    if failures:
        print(f"\n{len(failures)} of {len(files)} archive(s) FAILED to finalize:")
        for f, exc in failures:
            print(f"  {os.path.basename(f)}: {exc}")
        return False
    print(f"\nAll {len(files)} archive(s) finalized.")
    return True


def _finalize_one(f):
        print(f"\nFinalizing {f}...")
        conn = sqlite3.connect(f)
        cur = conn.cursor()
        
        # Checkpoint WAL
        cur.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        # Change journal mode back to DELETE (standard single file mode)
        cur.execute("PRAGMA journal_mode = DELETE;")
        mode = cur.fetchone()[0]
        
        # Integrity check
        cur.execute("PRAGMA integrity_check;")
        integrity = cur.fetchone()[0]
        
        # Tile count check
        cur.execute("SELECT count(*) FROM tiles;")
        tile_count = cur.fetchone()[0]
        
        # Metadata check
        cur.execute("SELECT name, value FROM metadata;")
        meta = dict(cur.fetchall())
        
        conn.commit()
        conn.close()
        
        # Best-effort only. An archive written by the GDAL container is owned by
        # root, so chmod raises EPERM for the tcfire user even though the file is
        # already mode 644 and readable by mbtileserver. The journal-mode change
        # above is the part that matters, and it has already committed.
        try:
            os.chmod(f, 0o644)
        except PermissionError as exc:
            print(f"  (chmod skipped: {exc.strerror}; mode left as-is)")
        
        size_mb = os.path.getsize(f) / (1024 * 1024)
        print(f"  Journal Mode   : {mode}")
        print(f"  Integrity      : {integrity}")
        print(f"  Total Tiles    : {tile_count:,}")
        print(f"  Size           : {size_mb:.2f} MB")
        print(f"  Metadata Name  : {meta.get('name')}")
        print(f"  Metadata Format: {meta.get('format')}")
        print(f"  Metadata Zooms : {meta.get('minzoom')} -> {meta.get('maxzoom')}")

if __name__ == "__main__":
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    tiles_path = repo_root / "data" / "tiles"
    sys.exit(0 if finalize_all(str(tiles_path)) else 1)
