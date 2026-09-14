# Data sources: where every layer comes from, and what it is the authority for

**Started 2026-09-13**, after the operator found the kiosk's own map labelling `2973 Glen Dr` while
the geocoder had never heard of it (DISP-2026-E301A3, punch-list #64). The cause was not a bug.
The map and the geocoder were built from **two different City products**, and nothing written
down said so. This file is that record.

One row per layer. Everything below was read from the import scripts and checked against the
files and tables on the kiosk on 2026-09-13, unless it is marked **unconfirmed**.

**Rules**

* **A layer is the authority only for what its row says.** A parcel table that holds addresses
  is not thereby the authority for addresses.
* **A new source, or a new copy of an existing one, updates its row in the same commit.** The
  copy date is part of the provenance: a correct source three months stale is a stale answer.
* **Two layers that can disagree say so here**, with the check that compares them and its last
  result.
* Where the source is reached over the network, the call itself is registered in
  [`../external_calls.md`](../external_calls.md). This file records the data, that one the
  request.

---

## 1. The register

City services are under `https://geodata.coquitlam.ca/arcgis/rest/services/`; the prefix is left
off below. Hub datasets are on the City's Open Data portal (`data.coquitlam.ca`), downloaded
through `opendata.arcgis.com`.

| Layer | Authority for | Source | Copy we hold | Loaded into | Refresh |
|:--|:--|:--|:--|:--|:--|
| **Lots and their addresses** | Lot outlines, the civic numbers and units the City's property records carry, folio, legal description | Open Data **Property Information** (the Cadastral set, portal layer 16), shapefile. Hub dataset `3df0090289aa4503bd8d234d7ee0c182_0` in `update_gis_data.py` — that this ID *is* Property Information is **unconfirmed**; the fields match (`GIS_ID, ADDRESS, HOUSE, UNIT, LEGALDESC, FOLIO, ZONETYPE…`) and so does the 2963-not-2973 lot | `backend/data/Property_Information/Addresses.shp`, 69,708 rows, `EXTRACT_DT` **2025-06-22**, on disk since 2026-06-19 | `public.parcels` (71,213 rows: 69,542 City rows + 1,671 base sites) by `backend/scripts/import_parcels.py` | `update_gis_data.py` (never run on the kiosk: no `last_gis_update.timestamp`) |
| **Address label points** | Nothing yet — **not loaded** | Open Data **Address Labels** (`data.coquitlam.ca/datasets/Coquitlam::address-labels-1`), shapefile, EPSG:3857 | `backend/data/staging/Address_Labels_2026-09-13/`, downloaded by the operator **2026-09-13**, 58,220 points | — | by hand |
| **Cadastral overlay** (the parcel lines and house numbers drawn on the kiosk map) | **Display only.** Images; the system cannot read an address from it | City map service `DynamicServices/Cadastral/MapServer/export`, `layers=show:0,1,16` — **layer 0 Road Labels, layer 1 Address Labels, layer 16 Parcels** — rendered by the City and saved as PNG | `backend/data/tiles/cadastral.mbtiles`, written **2026-08-28**, z14–20 | served by `cfr_tiles` | `backend/scripts/crawl_cadastral_tiles.py` |
| **Response zones** | Map grid (1–134) for a point | City map service `DynamicServices/Planning/MapServer/6`, GeoJSON; and a second copy, Hub dataset `109ad5fa4cb149ab93a1f9a2de88f34d_0`, shapefile | GeoJSON `backend/data/staging/emergency_zones.geojson` **2026-08-20**; shapefile `backend/data/Emergency_Response_Zones/` on disk since **2026-06-19** | GeoJSON → `public.zones` (134) by `import_gis_data.py`; shapefile → `public.parcels.zone_id` by `import_parcels.py` | `download_gis_data.py`; `update_gis_data.py` |
| **City boundary** | In or out of Coquitlam | `DynamicServices/Cadastral/MapServer/14` | `staging/city_boundary.geojson` **2026-08-20** | `public.city_boundary` (1) | `download_gis_data.py` |
| **Road centrelines** | Road geometry, names, class, address ranges | `DynamicServices/Transportation/MapServer/16` | `staging/road_centre_lines.geojson` **2026-08-20** | `public.roads` (3,451) | `download_gis_data.py` |
| **Road names** | The street vocabulary | `DynamicServices/AddressSearch/MapServer/2` | `staging/road_names.json` **2026-08-20** | `public.road_names` (1,079) | `download_gis_data.py` |
| **Intersections** | Junction points | **Derived**, not downloaded: computed from `public.roads` | — | `public.intersections` (1,995) by `import_gis_data.py` step 8 | re-run the import after roads change |
| **Hydrants** | Location, status, NFPA 291 flow class | `DynamicServices/Water/MapServer/2` | synced **2026-08-22** | `public.hydrants` (3,390) | `backend/scripts/sync_hydrants.py` |
| **Aerial imagery** | What is on the ground (2025, 7.5 cm) | `CachedServices/Imagery_2025/MapServer/tile`, the City's own tiles, stored unmodified | `backend/data/tiles/ortho.mbtiles` **2026-08-31**, z12–20 | served by `cfr_tiles` | `backend/scripts/compile_mbtiles.py` |
| **Street basemap** (live) | Display only | OpenStreetMap, Geofabrik British Columbia extract, built with Planetiler | `backend/data/tiles/street_vector.mbtiles` **2026-09-09** | served by `cfr_tiles` | `backend/scripts/build_vector_basemap.sh` |
| Street basemap (rollback) | Display only | Carto raster tiles — **see the licence caution in CLAUDE.md §1** | `street.mbtiles`, `street_nolabels.mbtiles` **2026-08-31** | kept, not the default | `compile_mbtiles.py` |
| **Routing graph** (production) | Travel distance and time (§6.2) | OpenStreetMap extract `vancouver.osm.pbf` (a BBBike city extract), `apparatus.lua` profile | built **2026-09-09** from the extract dated **2026-08-14** (`backend/data/osrm/apparatus.build.txt`); served by `cfr_osrm` | OSRM | `backend/scripts/build_osrm_graph.sh` |
| Routing graph (trial) | — | Geofabrik BC extract **2026-09-09** | `apparatus_bc20260909`, served by `cfr_osrm_trial` only | — | — |

Licences: City data is under the Open Government Licence — City of Coquitlam, which is **not held**
([`README.md`](README.md)); OSM, OpenMapTiles and the fonts are held under
[`basemap/`](basemap/).

**Not in the database at all:** building footprints. CLAUDE.md §1 names LiDAR-height building
footprints; they exist only inside basemap tiles (checked 2026-09-10,
[`../city_gis_data_register.md`](../city_gis_data_register.md)).

---

## 2. Layers that can disagree

| Pair | Can disagree because | Last check | Result |
|:--|:--|:--|:--|
| **The cadastral overlay's house numbers vs `public.parcels`** | The overlay is the City's live map service as of its crawl; the parcels are the 2025-06-22 Open Data extract | 2026-09-13, parcel outlines drawn over the overlay tiles at 2963 Glen Dr | **They disagree.** The overlay labels `2963` and `2973` on one lot; the parcels hold only 2963. Crews can read a number on the map that the geocoder does not have. |
| **Address Labels vs `public.parcels`** | Different City products | 2026-09-13, every distinct label point joined to the lot it falls in | Agree on **28,681 of 28,849** points inside a lot (99.4 %). **143** carry a number the lot does not have (134 on a one-street lot, 9 on a lot with several streets); **35** of the 134 would name an address that already exists on a different lot; **69** fall in no lot; **154** parcel numbers have no label. Of #64's sixteen missing numbers the labels hold **two** (2973 Glen Dr, 629 Cottonwood Ave). |
| Zones shapefile (`parcels.zone_id`) vs zones GeoJSON (`public.zones`) | Two copies, two dates | 2026-09-13, each lot's centroid tested against `public.zones` | **Agree**: 0 of 27,855 lots differ. |
| Property Information file (69,708 rows) vs `public.parcels` City rows (69,542) | Import filtering | not checked | **166 rows unaccounted for.** `import_parcels.py` says it imports 100 %. Open. |
| `public.intersections` vs the road network | Derived; goes stale when roads change | — | Rebuilt with every roads import; no separate check. |

---

## 3. Addresses: the open decision

The kiosk map already shows `2973`. That number reaches the screen by this path:

`DynamicServices/Cadastral/MapServer` layer 1 **Address Labels** → rendered by the City's
`export` → saved as images by `crawl_cadastral_tiles.py` on 2026-08-28 → `cadastral.mbtiles`.

So the City's live service has it. What the system cannot yet say is **which City dataset is the
authority for a civic address**, and in what form we should take it. What is known:

| Candidate | Street name? | Units? | Has 2973 Glen Dr? | How we would get it |
|:--|:--|:--|:--|:--|
| Open Data **Property Information** (in use) | yes | yes | **no** (2025-06-22) | shapefile download |
| Open Data **Address Labels** | **no** — one field, `LABEL`, the number; every point stored twice | no | yes | shapefile download (done) |
| Map service **Cadastral layer 1 Address Labels** (the overlay's source) | **no** — fields `OBJECTID, SHAPE, LABEL` (String 20), points, drawn at 1:5,000 and closer. The same data as the Open Data set | no | yes (seen on the overlay) | — |
| Map service **AddressSearch layer 1 `Parcel_Addresses`** | **yes** — `PROPHOUSE, PROPSTREET, PROPSTREETTYPE`, plus `ADDRESS` and `ROADNAME` | **yes** — `PROPUNIT, PROPUNITTYPE` | **unconfirmed** — the layer's data has not been queried | `query`, 1,000 records a page |

**The layer definitions, read 2026-09-13 with the operator's permission** (`…/Cadastral/MapServer/1?f=json`,
`…/AddressSearch/MapServer?f=json`, `…/AddressSearch/MapServer/1?f=json`):

* `AddressSearch` is *"features to support address searching in the City of Coquitlam"*: layer 0
  `Roads` (lines), layer 1 `Parcel_Addresses` (polygons), table 2 `Road_Names` (already our
  road-name source).
* `Parcel_Addresses` carries every field our `Addresses.shp` has under a `PROP` prefix
  (`PROPHOUSE, PROPSTREET, PROPSTREETTYPE, PROPUNIT, PROPUNITTYPE, PROPPOSTAL, PROPBLOCK,
  PROPPLAN, PROPLOT, LEGALDESC, PLAN_AREA, ZONETYPE1–3, GIS_ID`, with `ROLL_NUMBER` where the file
  has `FOLIO`), and adds `ADDRESS, ROADNAME, PROPERTYRSN, PID, layer, CEDMS_LSP` and the
  SC card URLs. That it is the **live counterpart of Property Information** is a reading of the
  schema, **unconfirmed** until its rows are compared with the file.
* The Address Labels layer's description is *"address labels for City of Coquitlam parcels"* and
  carries the City's standard disclaimer of accuracy. It is a labelling layer, not an address
  register.

What would settle it: whether `Parcel_Addresses` holds 2973 Glen Dr, and how its record count
compares with the 69,708 rows of the file. Both are data queries against the City, not
descriptions, and need the operator's permission.

**Not decided, and not to be improvised:** taking a street name for an Address Labels point from
the lot it falls in. The 35 collisions above are the evidence against doing it blindly.
