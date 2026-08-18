#!/usr/bin/env python3
"""
inspect_loose_tiles.py
Inspects existing loose tile directories in backend/data/tiles/.
"""
import os
import sys

def inspect_tiles(base_dir):
    print(f"Inspecting base dir: {base_dir}")
    if not os.path.exists(base_dir):
        print("Directory does not exist!")
        return

    for layer in sorted(os.listdir(base_dir)):
        layer_path = os.path.join(base_dir, layer)
        if not os.path.isdir(layer_path) or layer.endswith('.mbtiles'):
            continue
        
        print(f"\nLayer: {layer}")
        total_tiles = 0
        total_bytes = 0
        for z in sorted(os.listdir(layer_path), key=lambda x: int(x) if x.isdigit() else 999):
            z_path = os.path.join(layer_path, z)
            if not os.path.isdir(z_path):
                continue
            z_count = 0
            z_bytes = 0
            x_vals = []
            y_vals = []
            for root, dirs, files in os.walk(z_path):
                for f in files:
                    if f.endswith(('.png', '.jpg', '.jpeg')):
                        z_count += 1
                        fp = os.path.join(root, f)
                        sz = os.path.getsize(fp)
                        z_bytes += sz
                        parts = fp.replace('\\', '/').split('/')
                        # ... / {layer} / {z} / {x} / {y}.ext
                        try:
                            x_val = int(parts[-2])
                            y_val = int(parts[-1].split('.')[0])
                            x_vals.append(x_val)
                            y_vals.append(y_val)
                        except Exception:
                            pass
            total_tiles += z_count
            total_bytes += z_bytes
            min_x, max_x = (min(x_vals), max(x_vals)) if x_vals else (0, 0)
            min_y, max_y = (min(y_vals), max(y_vals)) if y_vals else (0, 0)
            print(f"  Zoom {z:>2}: {z_count:>6} tiles | {z_bytes / (1024*1024):>6.2f} MB | X: {min_x}..{max_x}, Y: {min_y}..{max_y}")
        print(f"  TOTAL : {total_tiles:>6} tiles | {total_bytes / (1024*1024):>6.2f} MB")

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    tiles_dir = os.path.join(repo_root, "data", "tiles")
    inspect_tiles(tiles_dir)
