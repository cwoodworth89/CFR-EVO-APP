# Punch list #88 — A destination far from any road reaches the crew as an ordinary ETA: the snap distance is never read

| | |
|:--|:--|
| **Status** | REPORTED 2026-09-15, not built. Severity is the lead's recommendation; the operator has not ruled on it. |
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
