# Punch list #21 — Rail crossing list is hand-entered and probably incomplete

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | crew-visible |
| **Area** | 🧱 Duplicated & Unsourced Frontend Constants |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L898 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 21. Rail crossing list is hand-entered and probably incomplete
> **Status**: 🟡 **Measured 2026-09-05 — the four are real crossings, each within 53 m of OSM `level_crossing` nodes; inside the City the extract adds three CPKC spur crossings off United Blvd. Closes on the operator's word about those.** *(Opened as: ⚠️ Open — found 2026-08-22.)*

`frontend/src/components/map/railroadCrossings.js` holds **four** level crossings with
seven-decimal coordinates and `avoidable` flags, none of which carry provenance (§6.3).

CLAUDE.md §6.2 already names the authoritative source for exactly this data — *"rail
crossings are `railway=level_crossing` in OSM, not `lat < 49.26`"*. This list is the same
defect one level up: four hand-placed points standing in for the OSM layer. Coquitlam
almost certainly has more than four level crossings, and **an incomplete hazard layer is
worse than an absent one**, because a crew reading a clear map concludes there is no
crossing.

**Mitigating for now**: display only. The layer defaults to off and no route avoids these
points, so no apparatus routing depends on them today.

**Fix**: derive from OSM `railway=level_crossing` into a table, the way intersections are
now derived from `public.roads`, and drop the `avoidable` judgement unless it can be
attributed to someone.

### Measured 2026-09-05

`tools/osm_level_crossings.py`, on the kiosk, against the extract OSRM routes on
(`vancouver.osm.pbf`, 2026-08-14) and `public.city_boundary`:

| | |
|:--|--:|
| `railway=level_crossing` nodes in the section 5 bounding box | 206 |
| inside the City polygon | 8 |
| of those, on a road | 8 (7 crossings; one road has two tracks) |

The bounding box reaches into Port Coquitlam, Port Moody, Burnaby, New Westminster and Surrey;
the CP yard in Port Coquitlam alone accounts for most of the 206. Inside the City:

| Crossing | Road | Rail | Barrier | On the kiosk list |
|:--|:--|:--|:--|:--|
| 49.239761, -122.813568 | Colony Farm Road | CPKC branch | full | RR-04, 53 m |
| 49.250530, -122.801011 | Pitt River Road + its link | CPKC branch | half | RR-03, 45 m |
| 49.229873, -122.864847 | United Boulevard | CPKC spur, tagged *disused* | none | no |
| 49.231283, -122.863669 | unnamed service road | CPKC spur | none | no |
| 49.231724, -122.862323 | unnamed service road | CPKC spur | none | no |
| 49.264930, -122.886261 | unnamed service road | SkyTrain (BC Rapid Transit) | none | no: guideway access, not a road crews use |

RR-01 (Westwood St) and RR-02 (Kingsway Ave) match OSM nodes at 46 m and 39 m but lie on the
Port Coquitlam side of the boundary, which is why the polygon count is two, not four. All four
hand points sit about 45 m west of the rails. The file now names its source (the operator) and
the OSM node ids per crossing.

Open for the operator: are the two spur crossings in the United Blvd industrial park, and the
disused one across United Blvd itself, crossings a crew would want on the layer?
