#!/usr/bin/env python3
"""
finalize_mbtiles.py
Checkpoints WAL and sets journal_mode to DELETE on all MBTiles databases
so they are cleanly readable by mbtileserver in read-only volume mounts.
"""
import sqlite3
import glob
import os
from pathlib import Path

def finalize_all(tiles_dir):
    pattern = os.path.join(tiles_dir, "*.mbtiles")
    files = glob.glob(pattern)
    print(f"Found {len(files)} MBTiles archives to finalize in {tiles_dir}")
    
    for f in sorted(files):
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
        
        # Set file permissions
        os.chmod(f, 0o644)
        
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
    finalize_all(str(tiles_path))
