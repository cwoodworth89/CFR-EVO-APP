# Standards & Specifications Index

**This is the first stop for any change that produces an operational value or defines a
domain model** (CLAUDE.md §7). It records what governs each subsystem, whether this
project actually holds the document, and where we are known to deviate.

The system is offline-first, so obtained standards are **vendored into this directory**
with their revision recorded — not linked. A link is not available at 3am on a kiosk with
no WAN.

> **This file covers domain standards.** For what the libraries we depend on actually do —
> as opposed to what their API names suggest — see
> [`dependency-behaviour.md`](dependency-behaviour.md). That is where the majority of this
> project's real defects have come from, and it is already populated.

## How to use this

1. Find the row covering what you are about to change.
2. If the row says **HELD**, read the cited clauses and cite them in code (§7.4).
3. If the row says **NOT HELD** or there is no row at all, **stop and raise it with the
   user** (§7.2). Do not improvise a domain model.
4. If you resolve a gap, update this table in the same commit.

> [!WARNING]
> **As of 2026-08-22 this project holds no standards documents.** Every row below is
> `NOT HELD`. This is recorded rather than left silent (§7.5), and a documentation
> inventory pass is planned. Until a row says HELD, treat this table as a list of known
> gaps, not as a source.

## Status

| Subsystem | Governing standard (expected) | Status | Notes |
|:--|:--|:--|:--|
| Road centrelines, address points, service boundaries | NENA NG9-1-1 GIS Data Model | ⚠️ NOT HELD | Closest thing to a governing spec for `public.roads`, `public.parcels`, `public.zones` and the derived `public.intersections`. Confirm the current revision and whether it defines an intersection layer (believed not — junctions are derived). |
| Alarm processing & dispatch time objectives | NFPA 1225 (formerly NFPA 1221) | ⚠️ NOT HELD | Governs the dispatch pipeline itself. Not currently referenced anywhere in the project. |
| Turnout & response time objectives | NFPA 1710 | ⚠️ NOT HELD | Cited by name in `docs/PROJECT_IDEAS.md`; the document itself is not held and no clause is cited. |
| Hydrant flow classification | NFPA 291 | ⚠️ NOT HELD | Colour/GPM classes are used in `sync_hydrants.py` and the kiosk hydrant layer. Behaviour looks correct but no clause is cited. |
| Spatial predicate semantics | OGC Simple Features / PostGIS | ⚠️ NOT HELD | `ST_Contains` (strict interior) vs `ST_Intersects` cost 155 intersections their map grid — punch-list #13. The semantics are specified; we were guessing. |
| Apparatus routing profile | OSRM profile documentation | ⚠️ NOT HELD | Punch-list #1 (arterial vs alleyway weighting) is open and unexamined. Do not tune the Lua profile without it. |
| STT decoding & prompt biasing | faster-whisper (pinned version) / Whisper | ⚠️ NOT HELD | The 223-token hotword cap was verified against the **installed source** (`faster_whisper/transcribe.py`, `get_prompt`) rather than documentation — punch-list #18. Installed source counts as authoritative for a pinned version (§7.3); documentation still wanted for upgrade safety. |
| Civic address format | NENA CLDXF | ⚠️ NOT HELD | Relevant to `normalization.py` and the street-suffix vocabulary now in `public.vocabulary`. |
| Canadian NG9-1-1 divergence | CRTC NG9-1-1 / ESWG | ⚠️ NOT HELD | NENA is US. Worth knowing where BC practice differs before treating NENA as normative. |
| Response mode terminology | Coquitlam Fire/Rescue operational policy (§6.3 tier 4) | ⚠️ NOT HELD | **Operator ruling 2026-08-23**: the authoritative terms are **`routine`** and **`emergency`** — as transmitted over the radio, and as already stored in `public.vocabulary`. **Numeric response codes are removed from the system entirely** — deleted, not renamed, with no mapping retained as a fallback; the operator will introduce one themselves if ever needed. An **unparsed response type is `NULL`, never a guess** (§6.1). Punch-list #30 (wording) and **#31** (the field never reaches the kiosk at all). Until a department policy document exists, the operator is the authority. |
| Call-type structure & vocabulary | Coquitlam Fire/Rescue operational policy (§6.3 tier 4) | ⚠️ NOT HELD | **Operator ruling 2026-08-23**: a call type is a **main type** optionally followed by a **sub type**, joined by ` - ` (`Medical Aid - Overdose`, `Structure Fire - Detached Structure`). A main type **can stand on its own** (`Assist`, `Rescue`, `Alarm Activated`), but **most calls carry a sub type** — measured **77%** of 202 verified calls, and **93%** of `Medical Aid`. The sub type is the operationally significant half. The two levels are deliberately **NOT** split into separate categories, columns, or tables: `public.vocabulary` keeps one flat running list of complete terms, and ` - ` is the only structure. Sub types are never offered or stored independently of their main type. Canonical spellings are operator decisions (`Breathing Problem` singular, `Smouldering` Canadian). Recognition-only spellings belong in `metadata->'aliases'`, never as a second row — punch-list #43. Until a department document or an E-Comm call-type list exists, the operator is the authority. |
| Municipal open data terms | Open Government Licence — City of Coquitlam | ⚠️ NOT HELD | Governs use of the parcel, zone, hydrant and orthophoto data the whole system rests on. |

## Known deviations

Recorded here so they are visible even before the governing document is obtained.

* **Intersection derivation tolerances.** `JUNCTION_CLUSTER_EPS_M = 25.0` and
  `ENDPOINT_SNAP_M = 2.0` in `backend/scripts/derive_intersections.py` are **measured on
  this system**, not taken from any standard (§6.3 tier 3). Both carry their measurements
  inline. If NENA or another source specifies a noding tolerance, these should be
  reconciled with it.
* **Zone edge tolerance.** `public.zone_for_point()` falls back to the nearest zone within
  5 m to close hairline gaps between adjacent zone polygons. Measured, not specified.
* **Street suffix canonical forms.** The 14 pre-existing abbreviations are inherited; the
  10 added on 2026-08-22 take their canonical form from `public.roads.roadtype` rather
  than from a postal or NENA standard. See
  `backend/migrations/2026-08-22_street_suffix_vocabulary.sql`.
* **Lougheed Hwy & Mariner Way manual coordinate.** Derived geometrically, **not
  operationally confirmed** — punch-list #17.

## Adding a standard

Vendor the document into this directory, then update its row with:

* the exact revision or edition,
* the date obtained,
* which clauses actually apply to this system,
* any deviation, moved into **Known deviations** above with its justification.
