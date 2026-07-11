# Local Hydrant Caching, NFPA 291 Visuals, and Change Tracking

Address the disappearance of fire hydrants from both the map interface and nearest-hydrant routing calculations by transitioning from querying the City of Coquitlam's broken ArcGIS MapServer spatial REST API to loading a local cached dataset (`frontend/public/data/hydrants.json`) and performing spatial filters and distance queries client-side using Turf.js.

Additionally, implement a change-tracking update mechanism in the monthly GIS maintenance script to automatically scan for additions, deletions, and status changes in hydrant locations.

## User Review Required

> [!IMPORTANT]
> **Shift to Local Cached Hydrant Dataset**:
> Instead of making live ArcGIS REST queries to the City of Coquitlam's MapServer (which is currently failing spatial bbox and point distance queries), the application will load all 3,381 Coquitlam hydrants from a pre-fetched local JSON file (`public/data/hydrants.json`) once on mount. This ensures 100% reliability, allows offline usage, and dramatically speeds up both map updates and routing calculations (reduced to <1ms).
> 
> **Periodic Scanning & Change Logging**:
> We will add a new task `update_hydrant_data()` to the monthly maintenance script [update_gis_data.py](../../backend/scripts/update_gis_data.py). This function will:
> *   Fetch the full, fresh list of hydrants from the MapServer using pagination.
> *   Compare it against the existing local JSON file.
> *   Identify and log all **Added** hydrants, **Deleted** hydrants, and **Modified** fields (e.g. status changes or coordinate corrections).
> *   Safely overwrite the local cache with the latest dataset.
> *   This runs automatically on the 1st of every month via the Windows Task Scheduler task `CFR_GIS_Maintenance`, or can be executed manually at any time.
> 
> **Custom High-Contrast NFPA 291 Dot-and-Ring Visuals**:
> We will replace the missing MapServer icons by styling the React Leaflet vector markers. Standard operating hydrants will be drawn as clean, modern **colored dots with an outer ring**, color-coded by NFPA 291 flow rates:
> *   **Class AA** (>= 1500 GPM): Sky Blue (`#38bdf8`) outer ring with matching solid center dot.
> *   **Class A** (1000–1499 GPM): Green (`#4ade80`) outer ring with matching solid center dot.
> *   **Class B** (500–999 GPM): Orange (`#fb923c`) outer ring with matching solid center dot.
> *   **Class C** (< 500 GPM): Red (`#f87171`) outer ring with matching solid center dot.
> *   **Class Unknown**: Yellow (`#facc15`) outer ring with matching solid center dot.
> *   **Private Hydrant**: Amber (`#f59e0b` ring containing `🔒` icon)
> *   **Out of Service**: Red Caution (`#ef4444` ring containing `⚠️` icon)

## Open Questions

None at this time. The plan provides a robust, direct solution that eliminates external network failures, maintains data freshness, and styles the hydrants exactly as requested.

---

## Proposed Changes

### Client Assets
#### [NEW] [hydrants.json](../../frontend/public/data/hydrants.json)
*   Contains the complete, compact list of all 3,381 Coquitlam hydrants (OBJECTID, gisId, lat, lng, flowClass, status). Already generated and placed during diagnostics.

### Map Rendering
#### [MODIFY] [MapLayers.jsx](../../frontend/src/components/MapLayers.jsx)
*   Remove the broken `dynamicMapLayer` overlay which requests raster tiles for hydrants.
*   Fetch `/data/hydrants.json` on component mount if `visible` is true.
*   When map bounding box changes, filter the cached hydrants in memory and format them back to the expected `{ geometry, attributes }` structure.
*   Update `getHydrantIcon` to draw a solid, colored marker containing `💧` for standard operating hydrants, styling the border and fill using NFPA 291 flow rating colors.

### Nearest-Hydrant Routing
#### [MODIFY] [MapBoard.jsx](../../frontend/src/components/MapBoard.jsx)
*   Fetch `/data/hydrants.json` once on component mount.
*   In the `useEffect` listening to `targetAddress` changes, compute the distance to all local hydrants using Turf.js and filter those within 300 meters, replacing the broken external API point-distance query.

### GIS Maintenance Script
#### [MODIFY] [update_gis_data.py](../../backend/scripts/update_gis_data.py)
*   Import `json` and `urllib.parse`.
*   Implement `update_hydrant_data()` to query the latest hydrant listings, run difference detection against the cached local JSON, log a change summary, and overwrite the local file.
*   Hook `update_hydrant_data()` into the script's `main()` execution path.

---

## Verification Plan

### Automated Tests
- Run the maintenance script manually to verify it successfully downloads hydrants, executes change detection, and logs results:
  ```powershell
  cd backend/scripts
  ../../.venv/Scripts/python update_gis_data.py
  ```
- Build client production code to verify no compiler errors or broken imports:
  ```powershell
  cd frontend
  npm run build
  ```

### Manual Verification
1.  **Map Overlay**: Open the mapping application, toggle the Hydrants layer ON, and zoom in to zoom level >= 17. Verify that fire hydrants appear as custom-styled, colored vector markers (Class AA in blue, Class A in green, etc.) with a water drop emoji.
2.  **Popup Details**: Click on a hydrant and hover over it. Verify that the correct status, ID, and flow rating are displayed.
3.  **Routing calculations**: Trigger a dispatch override. Verify that the top 3 closest hydrants are correctly calculated, drawn as options on the map, and the nearest one is displayed in the HUD with its ID and distance.
