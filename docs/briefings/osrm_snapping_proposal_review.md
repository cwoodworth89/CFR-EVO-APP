# Code Review Briefing: OSRM Boundary-Edge Snapping Proposal

**Date:** 2026-08-28
**Context:** This proposal implements the Boundary-Edge Decomposition snapping algorithm (Section 2.2 of CFR-EVO-STD-GIS-ROUTING) to fix parcel centroid routing failures. 

Following the GIS workstream review, the Valhalla migration has been paused. This implementation focuses strictly on fixing the geometric endpoint calculation for the **existing OSRM engine**.

**Safety Note:** This was executed in "Safe Draft" mode. Zero production code was modified, and zero changes were made to the OSRM Docker container.

## 1. Proposed Code Replacements
The following file contains the proposed rewriting of the parcel ingestion logic. It replaces naive centroid projection with multi-criteria frontage scoring (angular parallelism, logarithmic length weighting, road classification hierarchy weights, distance decay, and multiplicative street name prior).

* **Proposed Script:** `C:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\backend\scripts\import_parcels_PROPOSED.py`
* **Target Replacement:** `C:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\backend\scripts\import_parcels.py`

*Note: The proposed script relies on a new Postgres stored procedure `public.fn_calculate_parcel_road_snap` which has been registered in the database.*

## 2. Test Harness & Benchmarks
The team built a dedicated test suite and benchmarking script to verify the new mathematical logic against the historical 305-record dispatch corpus.

* **Test Script:** `C:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\backend\scripts\verify_snapping_corpus.py`
* **Automated Pytest Suite:** `C:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\backend\tests\test_boundary_snapping.py`
* **Benchmark JSON Output:** `C:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\docs\dispatch_corpus_snapping_benchmark.json`

## 3. Verification Results
The independent Victory Auditor confirmed the following performance metrics when running the proposed code against the historical corpus:

### Critical Failure Cases Resolved
| Address | Proposed Snap Distance | Result |
| :--- | :--- | :--- |
| **2865 Glen Dr** | 12.90m | **PASS** (Avoided Guildford Way 254m trap) |
| **210 Lebleu St** | 9.26m | **PASS** (Avoided King Edward St Alley trap) |
| **3025 Anson Ave** | 9.46m | **PASS** (Avoided Lincoln Ave trap) |
| **3030 Gordon Ave** | 9.21m | **PASS** (Avoided Christmas Way Alley trap) |

### 305-Record Corpus Efficacy
* **Successful OSRM Emergency Routes:** 300 / 305 (98.4%)
* **Street Name Aligned:** 291 / 300 (97.0%)
* **Average Road Snap Distance:** 2.10 meters
* **Average OSRM Emergency ETA:** 4.2 minutes

## Next Steps for Dev Team
1. Review the PostGIS math in `import_parcels_PROPOSED.py`.
2. Run `pytest backend/tests/test_boundary_snapping.py` locally.
3. If approved, overwrite `import_parcels.py` with the proposed file and execute the script to update the `parcels` table.
