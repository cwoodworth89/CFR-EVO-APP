#!/usr/bin/env python3
import urllib.request
import math

def deg2num(lat, lon, z):
    lat_r = math.radians(lat)
    n = 1 << z
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n)
    return x, y

for z in [12, 14, 16, 17, 18, 19, 20]:
    x, y = deg2num(49.2911, -122.7907, z)
    # Note: ArcGIS MapServer uses {z}/{y}/{x}
    url = f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "CFR-EVO/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = r.read()
            print(f"ArcGIS z={z} (x={x}, y={y}): HTTP {r.status}, {len(data)} bytes, type={r.headers.get('content-type')}")
    except Exception as e:
        print(f"ArcGIS z={z} (x={x}, y={y}): {e}")

# Also test Carto Voyager & Light
for layer, template in [
    ("street", "https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png"),
    ("street_nolabels", "https://a.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}.png")
]:
    for z in [12, 14, 16, 18]:
        x, y = deg2num(49.2911, -122.7907, z)
        url = template.format(z=z, x=x, y=y)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CFR-EVO/1.0"})
            with urllib.request.urlopen(req, timeout=5) as r:
                data = r.read()
                print(f"Carto {layer} z={z} (x={x}, y={y}): HTTP {r.status}, {len(data)} bytes, type={r.headers.get('content-type')}")
        except Exception as e:
            print(f"Carto {layer} z={z} (x={x}, y={y}): {e}")
