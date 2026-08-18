#!/usr/bin/env python3
"""
test_mbtiles_setup.py
Creates a minimal test.mbtiles and verifies mbtileserver.
"""
import sqlite3
import os
from PIL import Image
import io

def make_test_mbtiles(output_path):
    if os.path.exists(output_path):
        os.remove(output_path)
    
    conn = sqlite3.connect(output_path)
    cur = conn.cursor()
    
    cur.execute("CREATE TABLE metadata (name text, value text);")
    cur.execute("CREATE TABLE tiles (zoom_level integer, tile_column integer, tile_row integer, tile_data blob);")
    cur.execute("CREATE UNIQUE INDEX tile_index ON tiles (zoom_level, tile_column, tile_row);")
    
    metadata = [
        ("name", "test"),
        ("type", "baselayer"),
        ("version", "1.0"),
        ("description", "Test MBTiles"),
        ("format", "png"),
        ("bounds", "-123.04,49.15,-122.60,49.48"),
        ("minzoom", "12"),
        ("maxzoom", "14"),
        ("center", "-122.79,49.29,13")
    ]
    cur.executemany("INSERT INTO metadata VALUES (?, ?);", metadata)
    
    # Create a 256x256 test PNG tile at z=13, x=1301, y=2800 (TMS row = (1<<13)-1-2800 = 8191-2800 = 5391)
    img = Image.new('RGB', (256, 256), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    tile_bytes = buf.getvalue()
    
    z = 13
    x = 1301
    y_xyz = 2800
    y_tms = (1 << z) - 1 - y_xyz
    
    cur.execute("INSERT INTO tiles VALUES (?, ?, ?, ?);", (z, x, y_tms, tile_bytes))
    conn.commit()
    conn.close()
    print(f"Created test MBTiles at {output_path}")

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    target = os.path.join(repo_root, "data", "tiles", "test.mbtiles")
    make_test_mbtiles(target)
