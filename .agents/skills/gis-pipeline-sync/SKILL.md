---
name: gis-pipeline-sync
description: Procedures for updating Coquitlam ESRI shapefiles, caching NFPA 291 fire hydrants, compacting GIS JSON datasets, and verifying 1..134 emergency zone spatial boundaries.
---

# GIS Pipeline & Spatial Sync

This skill guides updating Coquitlam municipal spatial datasets, caching fire hydrants, and generating optimized vector assets for the frontend HUD.

---

## 1. Execute Monthly GIS Data Sync

Run the shapefile updater to download and diff municipal parcel and street layers:
```powershell
python backend/scripts/update_gis_data.py
```
* **Inputs**: ESRI shapefiles located in `backend/data/Property_Information/`.
* **Outputs**: Updated `addresses.json` and `blocks.json` in `frontend/public/data/`.

---

## 2. Sync & Compact NFPA 291 Hydrant Cache

Download and serialize Coquitlam's 3,381 fire hydrants into compact JSON:
```powershell
python backend/scripts/sync_hydrants.py
```
* **Serialization Constraint**: Enforce `separators=(',', ':')` in JSON dumping to keep payload under $1.0\text{ MB}$.
* **Color Ratings**: Verify Class AA Blue ($\ge 1500\text{ GPM}$), Class A Green ($1000\text{--}1499$), Class B Orange ($500\text{--}999$), Class C Red ($<500$).

---

## 3. Spatial Boundary Checks

Verify that CAD boundary slicing matches Coquitlam Emergency Response Zones ($1 \le N \le 134$) and ensure `coquitlam_boundary_opt.json` vector points remain within bounds:
* **Lat range**: `49.20` to `49.38`
* **Lng range**: `-122.88` to `-122.70`
