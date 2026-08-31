# Standards & Specifications Index

**This is the first stop for any change that produces an operational value or defines a
domain model** (CLAUDE.md §7). It records what governs each subsystem, whether this
project actually holds the document, and where we are known to deviate.

The system is offline-first, so obtained standards are **vendored into this directory**
with their revision recorded — not linked. A link is not available at 3am on a kiosk with
no WAN.

> **Municipal data gaps are tracked separately.** Where the City of Coquitlam's own data is
> missing, inconsistent, or disagrees with dispatch, the question belongs in
> [`../city_gis_data_register.md`](../city_gis_data_register.md) — not here, and never in code.

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

> [!CAUTION]
> **`docs/emergency_routing_gis_parcels_standard.md` is not a source, despite its contents.**
> It was written as an "Authoritative Engineering Standard, Release 1.0.0" and cites NENA,
> NFPA and APCO clauses precisely throughout — but it was never ratified, and **it holds none
> of the documents it cites**, exactly as this table records. It was retitled to *Design
> Proposal (UNADOPTED)* on 2026-08-29 and annotated with its measured errors in its own §0.
> Do not treat a clause number found there as provenance; every one of them is unverified.
>
> **Stripped 2026-08-30 from 126 KB to 60 KB.** Sections 1, 3 and 4 — routing-engine
> evaluation, the NENA/NFPA/APCO compliance matrices, topographic physics with no elevation
> data, and the implementation blueprint — were deleted outright. Only **Section 2** remains,
> because live parcel-snapping code and tests cite it by section number, plus its **§0**,
> which is the measured audit of what the document got wrong and is the most useful thing
> in it. §0's findings about the deleted sections are deliberately retained.

> [!CAUTION]
> **`docs/evo_routing_engine.md` was deleted on 2026-08-30, and this is why.**
> It described apparatus "physics classes" — vehicle weight, acceleration inertia, turn
> deceleration, hill-climbing power — as the live routing architecture. The figures came
> from AI-generated research commissioned during the design phase, which returned fluent,
> precisely structured, authoritative-sounding material with **no sources behind it**. The
> system was steered by it and went the wrong way.
>
> **Operator ruling 2026-08-30**: that line of work was a wild goose chase. The routing
> engine was deliberately reset to a basic level and will be approached again from scratch.
> The document was pruned rather than annotated because its only remaining function was to
> make an abandoned, unsourced design look like a specification.
>
> This is the reference case for §6.3's rule that invented-sounding mechanical rationale is
> not provenance. `APPARATUS_TIERS` remains **staged, not applied** (§6.4). OSRM's
> `distance` and `duration` stay authoritative (§6.2). When routing restarts, it starts at
> the *Apparatus routing profile* row below — which reads NOT HELD, the honest position.

> [!CAUTION]
> **The research drafts behind that document are archived, and carry the same warning.**
> `explorer_standards_research_1`, `explorer_routing_engines_1` and `explorer_gis_parcels_1`
> (137 KB of agent-generated research, 2026-08-28) cite NENA, NFPA and APCO clauses
> throughout and hold none of them. They were moved to
> `../CFR-EVO-APP-agent-archive/` on 2026-08-30. They are **leads for a future inventory
> pass, not provenance** (§7.3) — a clause number found there is recollection until the
> document itself is obtained and vendored here.

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
| Basemap tile licensing (Carto, Esri) | Carto Basemaps ToS / Esri World Imagery terms | ⚠️ NOT HELD | **Open question, punch-list #47.** `compile_mbtiles.py` bulk-downloads ~789k tiles from `basemaps.cartocdn.com` (Carto Voyager, OSM-derived) and ~431k from `server.arcgisonline.com` (Esri World Imagery, Maxar-sourced), both **unauthenticated and with no API key**, and stores them for permanent offline use. No key is needed and nothing is watermarked — but neither provider's terms have been read, and bulk pre-caching for redistribution is the use most likely to be restricted. The City orthophotos and cadastral layers are separately covered by the Open Government Licence and are not in question. |
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
