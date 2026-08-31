# Punch list #38 — `DISP-2026-ACCF6D` routed to the wrong street — the parcel front point is on Pinetree Way

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | crew-visible |
| **Area** | 🖥️ Live Operation Batch, 2026-08-23 |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L2167 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 38. `DISP-2026-ACCF6D` routed to the wrong street — the parcel front point is on Pinetree Way
> **Status**: ⚠️ **Open — confirmed by spatial query. Likely systemic; see the estimate.**

Dispatch (2026-08-23 09:29) for **`1178 Heffley Cres`**, transcript
*"medical aid - chest pain, 1178 heffley crescent Number 1202"*, confidence 100. The operator
reports the route ends one street over.

**It does.** The dispatch used `lat/lng = 49.2807084, -122.7932581`, taken from the parcel
`front_lat` / `front_lng`. Measured against `public.roads`:

| Point | Nearest road | Distance |
|:--|:--|--:|
| **Stored front point** | **Pinetree Way** | **0.0 m** |
| Stored front point | Heffley Crescent | **109.2 m** |
| Parcel centroid | Pinetree Way | 56.8 m |
| Parcel centroid | Heffley Crescent | 59.4 m |

The stored "front" of a Heffley Crescent address sits **exactly on Pinetree Way**, 109 m from
the street it is addressed on. Heffley Crescent is not even among the three nearest roads.
OSRM is behaving correctly — it is being handed the wrong destination.

Note the centroid is not obviously better here (roughly equidistant), so this is not a
"use the centroid instead" fix; the front point is simply wrong.

**Scope estimate — read the caveats.** Over a random 1,500-parcel sample with a front point,
comparing the first token of the address street to the nearest road `roadname`:

| Result | Parcels |
|:--|--:|
| Front point within 30 m of its own named street | 1,058 |
| Marginal, 30–60 m | 139 |
| **Over 60 m from its own street** (the Heffley signature) | **173 (11.5%)** |
| Own street name not matched in `public.roads` | 130 |

⚠️ **This is an estimate, not a count.** The comparison uses only the *first word* of the
street name, so multi-word streets fall into the "not matched" bucket rather than being
judged; large institutional parcels may legitimately sit far from their named street; and no
sampled case other than Heffley was inspected individually. Extrapolating ~11.5% across 65,400
parcels would be roughly 7,500 affected — **do not quote that figure as fact** until a proper
audit runs.

**Next step**: a real audit of `parcels.front_lat/front_lng` provenance — how the front point
was derived, and whether it can be re-derived by projecting the parcel centroid onto the
nearest segment *of the road it is addressed on* rather than the nearest road of any name.
That is the same class of defect as the intersections rebuild: a plausible geometric shortcut
standing in for the real relationship (§6.2).

---
