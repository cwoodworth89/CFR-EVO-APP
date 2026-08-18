#!/usr/bin/env python3
import math

def deg2num(lat_deg: float, lon_deg: float, zoom: int):
    lat_rad = math.radians(lat_deg)
    n = 1 << zoom
    x = int((lon_deg + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (x, y)

def count_tiles(min_lat, min_lon, max_lat, max_lon, min_z, max_z):
    total = 0
    for z in range(min_z, max_z + 1):
        x_nw, y_nw = deg2num(max_lat, min_lon, z)
        x_se, y_se = deg2num(min_lat, max_lon, z)
        x_min, x_max = min(x_nw, x_se), max(x_nw, x_se)
        y_min, y_max = min(y_nw, y_se), max(y_nw, y_se)
        cnt = (x_max - x_min + 1) * (y_max - y_min + 1)
        total += cnt
        print(f"  Zoom {z:>2}: {cnt:>6} tiles | X: {x_min}..{x_max} ({x_max-x_min+1}), Y: {y_min}..{y_max} ({y_max-y_min+1})")
    print(f"Total: {total:>7} tiles")
    return total

print("Regional Bounds (49.15, -123.04 -> 49.48, -122.60):")
count_tiles(49.15, -123.04, 49.48, -122.60, 12, 18)

print("\nCoquitlam Municipal Extent (49.208, -122.865 -> 49.385, -122.685):")
count_tiles(49.208, -122.865, 49.385, -122.685, 12, 20)
