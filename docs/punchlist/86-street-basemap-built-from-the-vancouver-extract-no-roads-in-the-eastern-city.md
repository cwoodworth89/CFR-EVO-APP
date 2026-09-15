# Punch list #86 — The street basemap was built from the Vancouver extract, so the eastern City has no roads

| | |
|:--|:--|
| **Status** | FIXED in `86eee32e`; rebuild on the kiosk in progress 2026-09-15; `cfr_tiles` restart (operator) and an on-screen check pending |
| **Severity** | 🔴 crew-visible: tiles exist there, so the map looks complete; only the roads are missing |
| **Area** | 🗺️ Basemap · 🖥️ Kiosk |
| **Origin** | Scaffolding chat, 2026-09-15; confirmed by a read-only gis-spatial-engineer job against the kiosk the same day |
| **Related** | #47b (tile licensing) · #40 · [`../standards/data_sources.md`](../standards/data_sources.md) · the routing graph, which is built from the same Vancouver file (being checked 2026-09-15) |

[← punch list index](../debug_and_qa_punchlist.md)

---

## What happened

`backend/scripts/build_vector_basemap.sh` named `coquitlam_region.osm.pbf` as `EXTRACT`, but its
docker line hard-coded `--osm_path=/data/osrm/vancouver.osm.pbf` and used `EXTRACT` only in an
input-exists check. The live `street_vector.mbtiles` (2026-09-09 22:28 PDT) came from that run:
`street_vector.build.log:92` records the Vancouver path, and the tileset's
`osmosisreplicationtime` (2026-08-07T23:00Z) matches the BBBike file's header exactly.

## Measured on the kiosk, 2026-09-15

* Tiles cover the whole scroll box at z0–14, so nothing looks blank. East of about **-122.655**
  they hold land cover, water and boundaries, and **no transportation layer**.
* **5.71 km²** of `public.city_boundary` lies east of the Vancouver extract's edge (-122.668);
  **19 parcels** have their centroid there. 6000 Quarry Rd's z14 tile holds no roads.
* In lng -122.655..-122.62, lat 49.28..49.36, the regional extract holds **261 highway ways**
  (Crane Dyke, Homilk'um Dyke, Snake Rock Dyke, Main Trail, ...); the Vancouver extract holds 0.
* North of about lat 49.44 the z14 rows hold no road vertices either. Not checked whether OSM has
  roads there.

## Operator intent (2026-09-15)

Serve the OSM vector basemap across everything the kiosk map can scroll, to a decent zoom. The
archive reaches z14 and MapLibre overzooms to 22.

## Fix

`86eee32e` derives the container path from `EXTRACT`, which must sit under `backend/data`
(mounted as `/data`). Rebuild ordered by the operator 2026-09-15.

**Closes when:** the new build log shows `coquitlam_region.osm.pbf`, the operator has restarted
`cfr_tiles`, and roads show at the east edge on screen.
