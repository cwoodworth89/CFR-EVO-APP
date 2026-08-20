# CFR EVO: Final Phase Debug & QA Punch List

This document tracks identified bugs, routing anomalies, edge cases, and feature refinements to investigate and resolve during the final bug squashing and testing phase.

---

## 🧭 Routing Engine & Pathfinding Anomalies

### 1. Erratic Routing Loops & Intra-Municipal Path Preference
* **Incident / Path**: `1300 Pinetree Way` (Town Centre Fire Hall / Hall 1) $\rightarrow$ `428 Nelson St`.
* **Reported Behavior**:
  * The calculated apparatus route exhibits erratic pathing with unnatural loops, parking lot / back-alley cut-throughs, and unnecessary detours (see visual trace below).
  * The route leaves optimal arterial corridors and may exit municipal bounds unnecessarily.
* **Root Cause Investigation Needed**:
  * Inspect OSRM Lua emergency profile weighting (`osrm/profiles/emergency.lua` or local OSRM graph).
  * Check OSM road classification weights (e.g. `service`, `parking_aisle`, `residential` vs `primary`/`secondary`/`tertiary`).
  * Check snap distance / nearest-road snapping logic for origins and destinations near complex driveways or hall aprons.
  * Evaluate weighting penalty for crossing municipal boundaries: prioritize staying inside Coquitlam city limits on intra-city calls where possible.
* **Visual Reference Trace**:
  ```
  Origin: 1300 Pinetree Way (Hall 1 Apron)
  Target: 428 Nelson St
  Issue: Bizarre loops, erratic turns, sub-optimal road class snapping
  ```

---

## 📋 General QA & Verification Notes

*(Additional items will be logged here as testing proceeds.)*
