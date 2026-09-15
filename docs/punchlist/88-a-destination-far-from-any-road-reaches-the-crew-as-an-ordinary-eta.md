# Punch list #88 — A destination far from any road reaches the crew as an ordinary ETA: the snap distance is never read

| | |
|:--|:--|
| **Status** | BUILT 2026-09-15, deployed to the kiosk, awaiting the API container rebuild. Confirmed on the live graph; not yet seen on a live call. |
| **Severity** | 🔴 crew-visible: the route and ETA look normal while ending up to kilometres from the address |
| **Area** | 🚒 Routing · 🖥️ Kiosk |
| **Origin** | gis-spatial-engineer, while checking the regional graph against the routing rules, 2026-09-15 |
| **Related** | #86 · #85 (lot-centre pins) · the regional graph swap (operator ruling 2026-09-15) |

[← punch list index](../debug_and_qa_punchlist.md)

---

## What happens

OSRM moves ("snaps") a route's destination to the nearest road segment and returns how far it moved it. The routing
engine does not read that distance (`services/gis/src/gis_service/routing_engine.py:249-255`), so nothing tells the
crew that the route ends away from the address.

## Measured on the kiosk, 2026-09-15 (Hall 1, to lot centroids)

| Destination | Graph | Snapped to | Snap | Route |
|:--|:--|:--|--:|--:|
| 6000 Quarry Rd | live `:5000` | Quarry Road | **2,150 m** | 12.58 km |
| 6000 Quarry Rd | regional trial `:5001` | Rannie Road, 597 m outside `city_boundary` | 1,363 m | 24.53 km, through Pitt Meadows |
| 5600 Quarry Rd | both | Quarry Road | 430 m | 12.58 km |
| 4972 Quarry Rd | both | Quarry Road | 289 m | 11.94 km |

These are lot centroids, not arrival points; production routes to the arrival point where one exists. Not measured:
how many dispatched destinations snap further than some distance, or what distance should warn. That threshold is a
domain value and needs a source or an operator ruling (§6.3, §7.2) before it is built.

---

## Measured across the corpus, 2026-09-15

Every dispatch carrying a placed destination (578 of them), routed Hall 1 apron → destination on the live graph
`apparatus_bc_city01_20260915`, reading OSRM's own `waypoints[-1].distance`. The router answered for all 578.

| | metres |
|:--|--:|
| median | 5.73 |
| 75th percentile | 21.92 |
| 90th percentile | 34.55 |
| 95th percentile | 42.61 |
| 99th percentile | 77.10 |
| max | 475.19 |

Above the ruled threshold of 50 m: **24 calls (4.15%), at 15 distinct addresses** — 9 of them 2929 Barnet Hwy
(Coquitlam Centre), 2 at 1240 Lansdowne Dr, the rest one apiece. The worst two are 3990 and 4000 Quarry Rd at
475.19 m. That is sparse enough for the flag to mean something, the same property the flag list was adopted on
(80% of dispatches carry none).

## Built

Operator ruling 2026-09-15: flag it above **50 m**, "and we can adjust from there".

* `services/gis/src/gis_service/routing_engine.py` — `_fetch_osrm_route` reads `waypoints[-1].distance` out of the
  response it already has and returns it; `calculate_unit_metrics` and `calculate_route` carry it as
  `destination_snap_m`. OSRM's number, never recomputed (§6.2); absent means `None`, never 0 (§6.1).
* `backend/cfr_dispatch/pipeline/review_flags.py` — `ROUTE_SNAP_FAR`, "Route ends away from the address marker",
  and `ROUTE_SNAP_FLAG_METRES = 50`, the one definition of the threshold. An unknown snap raises nothing: a flag
  asserts a measurement.
* `frontend/src/utils/reviewFlags.js` — the label mirror, and `flagDetail()`, which renders
  "The route stops at the nearest road, N m from the marker. The ETA is to that point." under the flag on the
  kiosk banner and the review sidebar. N is OSRM's metres rounded; it is never converted into extra minutes.

Amber, on the existing flag treatment. No new severity — there are none (operator decision 2026-08-29).

**What a crew sees when the snap is unknown**: nothing new. No flag, because there is no measurement — and on the
path where the router did not answer the ETA already reads `--:--`. A record written before this field existed is
the same case. This is the flag's known blind spot, not a silent zero.
