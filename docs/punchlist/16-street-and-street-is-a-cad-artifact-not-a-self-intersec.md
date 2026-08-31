# Punch list #16 — `<street> and <street>` is a CAD artifact, not a self-intersection

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | crew-visible |
| **Area** | 🔎 Geocoder Substitution |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L738 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 16. `<street> and <street>` is a CAD artifact, not a self-intersection
> **Status**: ✅ **Closed 2026-08-22.**

`DISP-2026-546B9E` transcribed as *"lougheed highway and lougheed highway, near lougheed
highway and lougheed highway ... map grid 49"* — Locution filled both the address slot and
the "near" cross-street slot with the same street because the CAD record had no cross
street. It is not a junction: `ST_IsSimple` is true for Lougheed Hwy, so the centreline
never crosses itself.

Resolved as a **street section** rather than a point: the stretch of that street inside
the announced map grid (533 m of Lougheed Hwy in grid 49). The kiosk highlights the
section in amber (`StreetSectionBanner`, and a dashed polyline on the map) and states
plainly that it is not a located incident; each unit routes to whichever end of the
section is nearest its own hall rather than to a midpoint that may be past the incident.

With **no** map grid it stays unresolved and raises the §5 Tier 1 card — without a grid
the "section" is the whole street, up to 14 km, which is not a location.
