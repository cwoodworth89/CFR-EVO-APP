# Fire Hydrant Caching, NFPA 291 Rendering, and Maintenance Walkthrough

We have successfully resolved the issue where fire hydrants had disappeared from the map and routing overlays. By transitioning from the city's broken spatial REST server to a fast local JSON cache, we restored all hydrant visuals and nearest-hydrant routing calculations.

---

## 1. Root Cause Analysis
During diagnostics, we discovered that:
*   The City of Coquitlam's public ArcGIS Water MapServer REST API (Layer 2) has a **corrupted/restricted spatial search index**. While large bounding boxes (which force full table scans) work, small bounding boxes (viewport queries) and point-distance queries (routing) return `0` features.
*   The MapServer's image export endpoint (which dynamic map layers use to request raster icons) is returning blank transparent PNGs (297 bytes).
*   The client-side Leaflet layers were drawing standard operating hydrants as **completely transparent clickable overlays**, assuming the underlying MapServer raster overlay would draw the physical yellow/red icons. When the raster overlay went blank and spatial queries failed, all hydrants disappeared.

---

## 2. Local Hydrant Cache Database
*   Created a paginated script [download_hydrants.py](file:///C:/Users/curti/Documents/GitHub/CFR-EVO-APP/scratch/download_hydrants.py) that successfully queries the server via `where=1=1` non-spatial queries.
*   Downloaded all 3,381 Coquitlam fire hydrants and saved them to a compact, local database file: [hydrants.json](file:///C:/Users/curti/Documents/GitHub/CFR-EVO-APP/client/public/data/hydrants.json) (544.75 KB).

---

## 3. Client-Side Rendering & NFPA 291 Styles
*   Refactored the `HydrantsLayer` component in [MapLayers.jsx](file:///C:/Users/curti/Documents/GitHub/CFR-EVO-APP/client/src/components/MapLayers.jsx):
    *   Removed the broken `dynamicMapLayer` raster overlay.
    *   Loads `/data/hydrants.json` on component mount if visible.
    *   Filters the 3,381 points in memory against the map viewport bounds when the map moves (taking less than 1ms).
    *   Updated `getHydrantIcon` to render operating hydrants as high-contrast **dots with an outer ring**, color-coded by the **NFPA 291 flow rate rating standard**:
        *   **Class AA** (>= 1500 GPM): Sky Blue (`#38bdf8`)
        *   **Class A** (1000–1499 GPM): Green (`#4ade80`)
        *   **Class B** (500–999 GPM): Orange (`#fb923c`)
        *   **Class C** (< 500 GPM): Red (`#f87171`)
        *   **Class Unknown**: Yellow (`#facc15`)
    *   Maintained specialized icons for **Private** hydrants (`🔒` emoji with amber ring) and **Out of Service** hydrants (`⚠️` emoji with red ring).

---

## 4. Nearest-Hydrant Routing
*   Refactored the target address query in [MapBoard.jsx](file:///C:/Users/curti/Documents/GitHub/CFR-EVO-APP/client/src/components/MapBoard.jsx):
    *   Loads `/data/hydrants.json` once on component mount.
    *   When the incident target address changes, it calculates the distance to all local hydrants using Turf.js and filters those within a 300-meter radius in-memory.
    *   This instantly restores the closest hydrant listing in the HUD and routing overlays without making network requests.

---

## 5. Maintenance & Change Tracking
*   Updated the monthly maintenance script [update_gis_data.py](file:///C:/Users/curti/Documents/GitHub/CFR-EVO-APP/agent/update_gis_data.py):
    *   Added `update_hydrant_data()` which paginates through the MapServer and checks for differences against the local cached JSON file.
    *   Detects **Added** hydrants, **Deleted** hydrants, and **Modified** attributes (such as status updates or flow class corrections) and logs a detailed summary:
        ```text
        === Hydrants Change Summary ===
        Additions: 0
        Deletions: 0
        Status/Metadata Changes: 0
        ================================
        ```
    *   Isolated the shapefile downloads (addresses/zones) and hydrant updates into separate `try-except` blocks. If the city's address zip link returns a transient 500 internal server error, the hydrant database update will still execute and refresh successfully.

---

## 6. Verification Results
1.  **Manual Script Run**: Executed `update_gis_data.py` inside the virtual environment. It successfully isolated the address download failure, fetched all 3,381 hydrants, confirmed 0 differences, and safely updated `client/public/data/hydrants.json`.
2.  **Production Build**: Ran `npm run build` in the `client/` directory. Vite completed the production build successfully in 4.39s with no errors.
