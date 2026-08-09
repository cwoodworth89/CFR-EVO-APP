# GIS Service Domain Rules & Vector Geocoding Standards

Rules and constraints for GIS shapefile processing, geocoding, and spatial services in `services/gis/`.

---

## 1. Vector Shapefile Indexing Performance
* **10x Ingestion Vectorization**: Always use `to_dict('records')` rather than Pandas `iterrows()` loops when loading ESRI shapefiles in `shapefile_loader.py` to keep boot-up memory $<150\text{ MB}$.
* **Compact JSON Serialization**: When updating `hydrants.json` and `addresses.json`, serialize with compact formatting `separators=(',', ':')` to keep payload sizes $<1.0\text{ MB}$.

---

## 2. Address Normalization & Geocoding Overrides
* **Subaddress & Business Name Isolation**: Unit numbers (`Unit 105`, `Apt 204`) and business names (`Save-on-Foods`) must be isolated under `target.subaddress` and stripped from the query string before performing shapefile matching.
* **Riverview Hospital Overrides**: Station 15/37 cottages (`Brookside`, `Centrale`, `Hillside`) must resolve to Riverview grounds coordinate override (`49.245830, -122.805330`).
* **CAD Boundary Slicing**: When recognizing `"map grid [N]"` in preliminary audio, enforce strict boundary validation `1 <= N <= 134` (Coquitlam Emergency Response Zones).
