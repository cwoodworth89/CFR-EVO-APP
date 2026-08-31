#!/usr/bin/env python3
"""
verify_mbtiles_endpoints.py
Verifies sample tile requests against cfr_tiles (mbtileserver) on port 8081.
"""
import urllib.request
import math
import sys

def deg2num(lat_deg: float, lon_deg: float, zoom: int):
    lat_rad = math.radians(lat_deg)
    n = 1 << zoom
    x = int((lon_deg + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (x, y)

# Sample locations:
# Hall 1 (Pinetree Way): 49.2911, -122.7907
# Coquitlam Town Centre Park: 49.2878, -122.7905
# Hall 2 (Mariner Way): 49.2622, -122.8175
# Hall 3 (Austin Heights): 49.2480, -122.8655
# Hall 4 (Burke Mountain): 49.2951, -122.7425

BASE_URL = "http://localhost:8081"

test_requests = [
    # Services endpoint
    ("Services Directory", f"{BASE_URL}/services"),
    
    # Street Basemap (Carto Voyager)
    ("Street Zoom 12", f"{BASE_URL}/services/street/tiles/12/{deg2num(49.2911, -122.7907, 12)[0]}/{deg2num(49.2911, -122.7907, 12)[1]}.png"),
    ("Street Zoom 14", f"{BASE_URL}/services/street/tiles/14/{deg2num(49.2911, -122.7907, 14)[0]}/{deg2num(49.2911, -122.7907, 14)[1]}.png"),
    ("Street Zoom 16", f"{BASE_URL}/services/street/tiles/16/{deg2num(49.2911, -122.7907, 16)[0]}/{deg2num(49.2911, -122.7907, 16)[1]}.png"),
    ("Street Zoom 18", f"{BASE_URL}/services/street/tiles/18/{deg2num(49.2911, -122.7907, 18)[0]}/{deg2num(49.2911, -122.7907, 18)[1]}.png"),
    
    # Street No Labels (Tactical grey)
    ("Street NoLabels Zoom 12", f"{BASE_URL}/services/street_nolabels/tiles/12/{deg2num(49.2911, -122.7907, 12)[0]}/{deg2num(49.2911, -122.7907, 12)[1]}.png"),
    ("Street NoLabels Zoom 14", f"{BASE_URL}/services/street_nolabels/tiles/14/{deg2num(49.2911, -122.7907, 14)[0]}/{deg2num(49.2911, -122.7907, 14)[1]}.png"),
    ("Street NoLabels Zoom 16", f"{BASE_URL}/services/street_nolabels/tiles/16/{deg2num(49.2911, -122.7907, 16)[0]}/{deg2num(49.2911, -122.7907, 16)[1]}.png"),
    ("Street NoLabels Zoom 18", f"{BASE_URL}/services/street_nolabels/tiles/18/{deg2num(49.2911, -122.7907, 18)[0]}/{deg2num(49.2911, -122.7907, 18)[1]}.png"),
    
    # Ortho Imagery (7.5cm Ortho + High-Res Base)
    ("Ortho Zoom 12", f"{BASE_URL}/services/ortho/tiles/12/{deg2num(49.2911, -122.7907, 12)[0]}/{deg2num(49.2911, -122.7907, 12)[1]}.jpg"),
    ("Ortho Zoom 14", f"{BASE_URL}/services/ortho/tiles/14/{deg2num(49.2911, -122.7907, 14)[0]}/{deg2num(49.2911, -122.7907, 14)[1]}.jpg"),
    ("Ortho Zoom 16", f"{BASE_URL}/services/ortho/tiles/16/{deg2num(49.2911, -122.7907, 16)[0]}/{deg2num(49.2911, -122.7907, 16)[1]}.jpg"),
    ("Ortho Zoom 17", f"{BASE_URL}/services/ortho/tiles/17/{deg2num(49.2911, -122.7907, 17)[0]}/{deg2num(49.2911, -122.7907, 17)[1]}.jpg"),
    ("Ortho Zoom 18 (Hall 1)", f"{BASE_URL}/services/ortho/tiles/18/{deg2num(49.2911, -122.7907, 18)[0]}/{deg2num(49.2911, -122.7907, 18)[1]}.jpg"),
    ("Ortho Zoom 19 (Hall 1)", f"{BASE_URL}/services/ortho/tiles/19/{deg2num(49.2911, -122.7907, 19)[0]}/{deg2num(49.2911, -122.7907, 19)[1]}.jpg"),
    ("Ortho Zoom 20 (Hall 1)", f"{BASE_URL}/services/ortho/tiles/20/{deg2num(49.2911, -122.7907, 20)[0]}/{deg2num(49.2911, -122.7907, 20)[1]}.jpg"),
    ("Ortho Zoom 18 (Hall 2)", f"{BASE_URL}/services/ortho/tiles/18/{deg2num(49.2622, -122.8175, 18)[0]}/{deg2num(49.2622, -122.8175, 18)[1]}.jpg"),
    ("Ortho Zoom 19 (Hall 2)", f"{BASE_URL}/services/ortho/tiles/19/{deg2num(49.2622, -122.8175, 19)[0]}/{deg2num(49.2622, -122.8175, 19)[1]}.jpg"),
    ("Ortho Zoom 20 (Hall 2)", f"{BASE_URL}/services/ortho/tiles/20/{deg2num(49.2622, -122.8175, 20)[0]}/{deg2num(49.2622, -122.8175, 20)[1]}.jpg"),
    ("Ortho Zoom 18 (Hall 3)", f"{BASE_URL}/services/ortho/tiles/18/{deg2num(49.2480, -122.8655, 18)[0]}/{deg2num(49.2480, -122.8655, 18)[1]}.jpg"),
    ("Ortho Zoom 19 (Hall 3)", f"{BASE_URL}/services/ortho/tiles/19/{deg2num(49.2480, -122.8655, 19)[0]}/{deg2num(49.2480, -122.8655, 19)[1]}.jpg"),
    ("Ortho Zoom 20 (Hall 3)", f"{BASE_URL}/services/ortho/tiles/20/{deg2num(49.2480, -122.8655, 20)[0]}/{deg2num(49.2480, -122.8655, 20)[1]}.jpg"),
    ("Ortho Zoom 18 (Hall 4)", f"{BASE_URL}/services/ortho/tiles/18/{deg2num(49.2951, -122.7425, 18)[0]}/{deg2num(49.2951, -122.7425, 18)[1]}.jpg"),
    ("Ortho Zoom 19 (Hall 4)", f"{BASE_URL}/services/ortho/tiles/19/{deg2num(49.2951, -122.7425, 19)[0]}/{deg2num(49.2951, -122.7425, 19)[1]}.jpg"),
    ("Ortho Zoom 20 (Hall 4)", f"{BASE_URL}/services/ortho/tiles/20/{deg2num(49.2951, -122.7425, 20)[0]}/{deg2num(49.2951, -122.7425, 20)[1]}.jpg"),
]

def main():
    print("=" * 80)
    print(" CFR EVO MBTILES SERVER (mbtileserver:8081) VERIFICATION TEST SUITE")
    print("=" * 80)
    all_ok = True
    
    for label, url in test_requests:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CFR-EVO/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                status = resp.status
                content_type = resp.headers.get("Content-Type", "")
                data = resp.read()
                size_kb = len(data) / 1024
                
                if status == 200 and len(data) > 0:
                    print(f" [PASS] {label:<30} -> HTTP {status} | {content_type:<25} | {size_kb:>6.1f} KB | {url}")
                else:
                    print(f" [FAIL] {label:<30} -> HTTP {status} | {content_type:<25} | {size_kb:>6.1f} KB | {url}")
                    all_ok = False
        except Exception as e:
            print(f" [ERROR] {label:<30} -> {e} | {url}")
            all_ok = False
            
    print("=" * 80)
    if all_ok:
        print(" ALL MBTILES ENDPOINT VERIFICATIONS PASSED SUCCESSFULLY (HTTP 200 OK)!")
    else:
        print(" SOME MBTILES ENDPOINT VERIFICATIONS FAILED!")
        sys.exit(1)
    print("=" * 80)

if __name__ == "__main__":
    main()
