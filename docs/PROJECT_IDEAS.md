# CFR EVO: Project Ideas & Feature Backlog

This document tracks feature requests, operational enhancements, and future ideas for **CFR EVO**.

---

## 📌 Feature Ideas & Roadmap Backlog

### 1. 📍 Call Pin Mode (Incident Map Analytics)
* **Description**: Interactive historical call map layer displaying pins across Coquitlam for past dispatches, allowing station crews and department leadership to review incident geography, seasonal call volume, and emergency spatial patterns.
* **Timeframe Filters**:
  - ⏱️ `Last 24 Hours`
  - 📅 `Last 7 Days`
  - 🗓️ `Last 30 Days` (Month)
  - 📊 `Last 365 Days` (Year)
* **General Call Type Pin Categorization**:
  - 🚑 **Medical**: Medical Aid, Cardiac, Overdose, Assault, Medical Emergency.
  - 🔔 **Alarms**: Commercial/Residential Fire Alarms, Waterflow, Smoke Detector Activation.
  - 🚗 **MVA**: Motor Vehicle Accidents, Vehicle Entrapments, Highway Collisions, Rollovers.
  - 🚨 **Chief Tone Calls**: Structure Fires, Working Fires, Hazardous Materials, Technical Rescues, Commercial Fires.
  - 📋 **Other**: Public Assistance, Power Lines Down, Burn Complaints, Misc Incidents.
* **Key Features**:
  - **Color-Coded Map Pins**: Distinct visual pins/markers corresponding to each call category on the Leaflet map.
  - **Time-Range Slider / Selector**: Quick toggle buttons for 24h / 7d / Month / Year views.
  - **Category Filtering**: Checkbox toggles to isolate or layer specific call types (e.g. view only MVAs or Chief Tone calls).
  - **Incident Detail Popups**: Click/hover popups displaying call timestamp, unit responses, address, and incident summary.

---

### 2. 🗺️ Cross-Road Spatial-Phonetic Radius Correction & Block-Segmented Preprocessing
* **Description**: Enhance cross-street transcription and extraction accuracy by applying a preprocessed spatial radius filter derived from the primary address block segment.
* **Core Concept**:
  1. **Primary Address Anchor**: Once the primary address is geocoded with high confidence (e.g. `3030 Gordon Ave`), extract its block number (`3000-Block Gordon Ave`) and spatial coordinate $(Lat, Lng)$.
  2. **Block-Segmented Linear Neighbor Map (`spatial_street_index.json`)**:
     - **Short Residential Streets** (e.g. `Sandstone Cres`): Single entry mapping to all nearby intersecting streets.
     - **Long Arterial Corridors** (e.g. `Lougheed Hwy`, `Como Lake Rd`): Divided into linear block buckets (e.g. `LOUGHEED HWY (2000-Block)`, `LOUGHEED HWY (3000-Block)`, `LOUGHEED HWY (4000-Block)`).
     - **Linear Overlap (No Border Edge-Effects)**: Each block segment's spatial buffer overlaps neighboring blocks by ±600ft, ensuring cross-streets right on block or zone boundaries are never missed.
  3. **$O(1)$ Instant Preprocessed Lookup**:
     - At runtime, query `STREET_NEIGHBORS["3000-BLOCK LOUGHEED HWY"]` for zero-latency $O(1)$ retrieval of candidate cross-streets (~10–15 streets).
  4. **Two-Stage Integration (Prompt Weighting & Post-Processing Snapping)**:
     - **Stage 1 (Transcription Biasing)**: Inject candidate block-neighbor street names into Whisper's `initial_prompt` / `hotwords` to weight audio decoding toward correct phonetic spelling.
     - **Stage 2 (Post-Processing Extraction)**: Extract the raw cross-street phrase and fuzzy-match against candidate block-neighbors (Levenshtein / Double Metaphone).
  5. **Safe Pass-Through Fallback (Zero Risk)**:
     - Enforces a strict 75%+ similarity threshold. If no local candidate matches above threshold (or if audio is ambiguous), the engine **safely passes raw text through unchanged**. It will NEVER force an inaccurate match.
* **Benefits**:
  - Eliminates phonetic ambiguity for misheard cross-streets (e.g. snapping "near Christmas Way" vs "near Cristmas Way").
  - Prevents zone-boundary edge effects by using linear road-geometry buffer overlaps instead of hard polygon borders.
  - $O(1)$ instant execution with zero runtime spatial calculation overhead.
  - Safe pass-through fallback ensures zero risk of forced false matches.

---

### 3. 🏷️ Isolated Target Property Address Badge on Satellite PIP View
* **Description**: On the high-resolution 7.5cm Satellite Picture-in-Picture (PIP) and expanded modal views, render an isolated, high-contrast civic address number badge directly centered on the dispatched target parcel polygon (without loading the entire municipal cadastral grid or surrounding street line overlays).
* **Key Concept**:
  - Keep the base aerial orthophoto 100% clean and uncluttered (zero surrounding cadastral lines or neighboring lot numbers).
  - Extract the house number from `activeCall.address` and render a lightweight, glowing Leaflet DivIcon badge (e.g. `📍 428`) centered on the target parcel centroid.
* **Benefits**:
  - Instant target property identification for apparatus operators during nighttime arrival and rooftop/driveway size-up.
  - Preserves maximum visual contrast of high-resolution 7.5cm aerial imagery.

---

### 4. 🎮 Driver Training & Recruit Game Engine (Standalone Module Reimplementation)
* **Description**: Reimplement the original map-quiz training modes (Emergency Zones, Street Intersections, Block Ranges, Parcel Addresses) that were removed from `MapBoard.jsx`/`DashboardHUD.jsx` (commit `d5fbdcc`) during the v1.0.0 feature freeze. The original implementation was purged because it relied on deprecated processes: static pre-extracted JSON quiz datasets (`addresses.json` ~18MB, `blocks.json`, `intersections.json`) built from the old in-memory shapefile pipeline, predating the PostGIS migration.
* **Core Concept**:
  - Rebuild as a **decoupled standalone module** rather than `appMode` branches woven through the live dispatch kiosk components, so training logic can't tangle with real-time dispatch code again.
  - Source quiz data live from PostGIS (`public.zones`, `public.roads`, `public.intersections`, `public.parcels`) instead of static pre-baked JSON snapshots, so it stays in sync with GIS updates automatically.
  - Preserve the 4 original training modes (Zones, Intersections, Blocks, Addresses) with score/feedback/tolerance-based guessing.
* **Benefits**:
  - Keeps recruit map-training available without reintroducing the deprecated data pipeline or the maintenance burden of hand-synced static datasets.
  - Clean separation means training mode can be developed/tested independently of the dispatch HUD without risking regressions there.

---

### 5. 🏢 Multi-Hall Expansion (Halls 2–4 Kiosk Rollout)
* **Description**: CFR EVO currently runs as a single-hall deployment (one test kiosk, `tcfire@100.95.146.94`). The original design (per `README.md`) targets 4 station kiosks (Hall 1 master DB server + Halls 2–4 slave displays) sharing one backend. This entry tracks the feature work needed when expanding beyond the single-hall test setup.
* **Core Concept**:
  - **Hall Identification**: `frontend/.env.local` already supports `VITE_DEFAULT_HALL` per kiosk; verify this cleanly differentiates hall-specific UI/behavior (e.g. home station highlighting, default map center) across multiple simultaneous kiosk instances.
  - **Shared Backend, Multiple Displays**: Confirm FastAPI (`:8000`), MQTT (`:1883`/`:9001`), and the PostGIS database on Hall 1 correctly fan out to Halls 2–4 over the local network/Tailscale without per-hall data drift.
  - **Per-Hall Deployment & Update Workflow**: Extend the current single-kiosk git-pull-and-rebuild workflow to cover multiple physical kiosks (e.g. a deploy script that pulls/rebuilds across all hall IPs rather than just one).
  - **Hardware Provisioning**: Physical kiosk hardware, audio input devices, and network/Tailscale setup for Halls 2–4 (see `docs/hardware_specification.md`, `docs/laptop_kiosk_setup.md`).
* **Benefits**:
  - Realizes the originally designed multi-station architecture once single-hall testing is stable.
  - Scoping this as its own feature effort (rather than assuming it "just works" from the single-hall docs) avoids surprises when Halls 2–4 come online.

---

### 6. ⚙️ CFR Customized Route Configuration (Apparatus-Aware ETA Layer)
* **Status**: Design only. Not implemented. Routing currently runs on **stock OSRM** —
  `distance` and `duration` come straight from the router with no local adjustment
  (commit `c332b81`).
* **Description**: A named, auditable configuration surface that layers CFR-specific
  apparatus behaviour on top of the OSRM baseline, rather than burying tuning constants
  inside the calculation path (CLAUDE.md §6.4).

#### Core Concept
OSRM stays authoritative for the route and its baseline duration. The config layer
applies a documented, explicitly-enabled adjustment on top:

```
final_eta = osrm_duration × apparatus_factor(unit_class, response_mode)
```

Never a re-derivation from speed × distance, and never an estimated turn count — OSRM
already returns the real turn list in `steps` (CLAUDE.md §6.2).

#### Speed Model (department operational policy — Curtis Woodworth, 2026-08-21)
Apparatus speed is expressed as an **offset from the posted limit**, not an absolute
average. This pairs directly with `public.roads.speed`, which carries the City of
Coquitlam posted limit for all 3,214 road segments:

| Apparatus Class | Units | Speed Relative to Posted Limit |
| :--- | :--- | :--- |
| **Light** | Squad, Medic, Command Car, LAV, Specialty | +10 to +20 km/h |
| **General** | Engine, Rescue, Quint, Pumper | +0 to +10 km/h |
| **Heavy** | Ladder, Tower Platform, Water Tender | posted limit, up to +5 km/h |

Also expected, and **not yet sourced**:
* **Grade penalties** — apparatus lose speed on climbs (Burke Mtn, Westwood Plateau)
  and are braking-limited on descents. Requires real elevation data; there is none in
  the codebase today.
* **Turn penalties** — heavier apparatus lose more time per turn. OSRM returns the true
  turn list in `steps`, so this is a per-turn cost applied to real turns, never an
  assumed turns-per-km rate.

#### Scope Notes
* **Turnout time is explicitly out of scope.** The current objective is *drive ETA only*.
  If added later, cite **NFPA 1710 §4.1.2.1** rather than inventing a figure.
* Seed data lives in `APPARATUS_TIERS` in
  [`routing_engine.py`](../services/gis/src/gis_service/routing_engine.py) and
  [`EVORoutingEngine.js`](../frontend/src/utils/EVORoutingEngine.js), both marked
  **PROVENANCE REQUIRED** — the inherited speed/road-factor/turn-penalty numbers carry
  no cited source and must be replaced by the offsets above (or measurement) before use.
* `EVORoutingConfigModal` / `hud/RoutingConfigModal.jsx` is the existing UI shell. Its
  current controls (EMTRAC preemption, rush-hour efficiency) reference values removed in
  `c332b81` and **currently do nothing** — it should be rebuilt against this feature.
* Per CLAUDE.md §6.4, the layer must be explicitly enabled and auditable: an operator
  should be able to see that an ETA was adjusted, by how much, and why.

---

### 7. 📲 Per-Unit Ntfy Topic Routing
* **Status**: Design only. Single-topic operation is the current, intended behaviour.
* **Current state**: All dispatches publish to the single master topic **`chief-master`**
  (see [`ntfy_server_access_and_qr_spec.md`](./ntfy_server_access_and_qr_spec.md) §2A),
  set via `NTFY_TOPIC` in `backend/.env` and on the `api` service in `docker-compose.yml`.
  Both must stay in sync — a mismatch publishes agent and API notifications to different
  topics, which is exactly how pushes were silently lost on 2026-08-21.
* **Description**: Route each dispatch to topics derived from the **units assigned to
  that call**, so crews receive only the calls they are responding to, while
  `chief-master` continues to receive everything.
* **Core Concept**:
  - `chief-master` remains permanent and receives all dispatches across all halls.
  - Per-apparatus topics follow the monthly-salted format already specified in
    §2B of the ntfy spec (e.g. `engine-1-aug2026-9f8a3b`), with a 3-day rotation
    grace period.
  - `post_to_ntfy` fans out: one publish to `chief-master`, plus one per unit in
    `responding_units`.
* **Open questions**:
  - Does a unit topic follow the apparatus or the crew member?
  - Behaviour when `responding_units` is empty or unparsed — `chief-master` only,
    presumably, since inventing a recipient is not acceptable (CLAUDE.md §6.1).
  - Whether salt rotation is worth the operational overhead on a closed Tailscale
    network.
* **Do not build this before multi-hall (#5)**: with one hall and one kiosk, a single
  topic is simpler and demonstrably sufficient.


---

### 8. 🔑 Keyed Gate Access Overlay (`public.gate_keys`)

* **Status**: Design only — deferred by the v1.0.0 feature freeze
  (see [`development_freeze_summary.md`](./development_freeze_summary.md)).
* **Description**: A toggleable map layer marking gates across the Coquitlam response
  area that require a key carried by first-due apparatus, with the key ID and a
  descriptor surfaced on hover and click. Distinct from road closures: a gate is a
  permanent access constraint, not a temporal event, and it has no Open511 feed or
  municipal source behind it.
* **Scope**: Physical gates on roads controlling access to **rural and backcountry
  areas** — provincial parks, Forest Service Roads, BC Hydro roads, Metro Vancouver
  parks and watershed, and City of Coquitlam parks and utility areas. Not Knox boxes,
  not building access, not gate codes.
* **Why it matters**: These gates are used rarely — a crew may encounter one once in
  several years — which is precisely when institutional memory fails. Low usage
  frequency is the argument *for* the feature, not against it.

#### Data Source — no external authority exists
Every other GIS layer in CFR EVO derives from the City of Coquitlam Open Data Portal
and can be rebuilt by re-running an import script. This one cannot. There is no
municipal, provincial, or regional dataset that publishes which key CFR carries for a
given gate. The data is **hand-curated in conjunction with Coquitlam SAR**.

This makes `public.gate_keys` the **first irreplaceable table in the system**, which is
the direct motivation for backlog item #9. Do not build this before a backup routine
exists — losing hand-curated SAR fieldwork to an SSD failure is not recoverable.

OpenStreetMap tags gates as `barrier=gate` (with `locked`, `access`, `operator`), and
the regional `vancouver.osm.pbf` already on the kiosk for OSRM covers well beyond the
city limits. That is a viable *geometry* seed at $0 with no new dependency, but it can
never supply `key_id`. Investigated and set aside in favour of hand curation; recorded
here so the option is not re-derived from scratch later. Backcountry OSM gate coverage
is patchy, so an absent marker must never be read as "no gate here" (CLAUDE.md §6.1).

#### Schema
```sql
CREATE TABLE IF NOT EXISTS public.gate_keys (
    id          BIGSERIAL PRIMARY KEY,
    -- Ordinal from the curated CFR/SAR list. Display only -- renumbering the
    -- source list must never repoint a record. gate_id carries identity.
    list_index  INTEGER,
    gate_id     VARCHAR(32) UNIQUE NOT NULL,
    gate_desc   TEXT,
    -- NULL means no CFR key is held for this gate. Do not default, and do not
    -- render blank: "NO KEY ON RECORD" is the operationally useful answer and
    -- saves a crew driving to a gate they cannot open (CLAUDE.md 6.1).
    key_id      VARCHAR(32),
    key_desc    TEXT,
    lat         DOUBLE PRECISION NOT NULL,
    lng         DOUBLE PRECISION NOT NULL,
    geom        geometry(Point, 4326),
    source      VARCHAR(64),   -- 'coquitlam_sar', 'cfr', ...
    -- Last date the gate/lock was physically confirmed. NULL = never confirmed.
    verified_at DATE,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```
* `geom` and `updated_at` should be maintained by triggers. With hand edits, updating
  `lat`/`lng` without `geom` silently diverges the popup coordinates from the marker
  position, and `updated_at` will simply be forgotten.
* `verified_at` earns its place here more than on any other table: a stale `key_id` is
  the dominant failure mode, and unlike a hydrant flow class, no external sync will
  ever correct it. Entries past an age threshold must render as visibly unconfirmed.

#### Maintenance Model
Database-only, manually updated. Change cadence is **every few years** — comparable to
cadastral or hydrant data — and a typical edit is a single value:
```sql
UPDATE public.gate_keys SET key_id = 'K-7', verified_at = CURRENT_DATE
 WHERE gate_id = 'G-014';
```
A CSV-plus-reload pipeline was considered and rejected: at this cadence it buys nothing
and introduces a second source of truth. The `cfr-postgres` MCP server reaches the kiosk
database directly over Tailscale, so an edit needs no script, file, or rebuild.

#### Layer
Direct copy of the hydrant pattern in [`MapLayers.jsx`](../frontend/src/components/MapLayers.jsx)
(`HydrantDetailCard`, ~L164): one detail component rendered into both a `<Tooltip>`
(hover) and a `<Popup>` (click) so the two cannot drift. Add `showGateKeys` to
[`useMapLayerPreferences.js`](../frontend/src/hooks/useMapLayerPreferences.js) and a 🔑
icon to [`layerIcons.js`](../frontend/src/components/map/layerIcons.js).

Every difference from `HydrantsLayer` is a simplification: no bbox query, no cache TTL,
no nearest-neighbour computation, no `minZoom` gate, and **no bounds check of any kind**.
At a few dozen rows the layer fetches all of them once and renders. Default toggle off.

* **No boundary filtering**: many gates sit outside the City of Coquitlam. Note that
  `isWithinCoquitlam()` ([`addressUtils.js:38`](../frontend/src/utils/addressUtils.js))
  means *"orthophoto and cadastral coverage exists here"* — it is not a validity test
  for curated data, and must not be applied to this layer. The §5 Tier 2 banner firing
  on an out-of-city **incident** remains correct and should be left alone.
* **Tile coverage**: gates outside the municipal tile-coverage polygon will render over
  the "no map data" hatch. Tracked separately with the map/imagery work — the layer
  does not block on it.

#### Explicitly Not In Scope
* **No routing alert.** The original concept included warning crews of keyed gates near
  an incident. Deferred deliberately: an alert built on an unpopulated dataset either
  fires wrong or never fires, and a wrong key alert is worse than none. The schema
  above supports adding a coordinate-radius alert later without modification.
* **No OSRM integration.** Gates are advisory, matching how `public.road_closures` is
  display-only today (see [`routing.py:37`](../backend/api/routers/routing.py)).
* **No kiosk authoring UI, no auth model, no multi-lock schema.** One lock, one key,
  developer-maintained.

---

### 9. 💾 Backup & Disaster Recovery for Irreplaceable Assets

* **Status**: ⚠️ **Open gap — no backup routine exists anywhere in the project.**
  A repository-wide search for `pg_dump` / `pg_restore` / `backup` returns hits only
  inside `.venv`.
* **Why now**: Every table in PostgreSQL today derives from an external authoritative
  source and can be rebuilt by re-running an import script — which is why no backup has
  been needed so far. Backlog item #8 (`gate_keys`) breaks that assumption, and the HITL
  ground-truth corpus already has. This is worth resolving *before* #8 is built.

#### Current Coverage
GitHub (`cwoodworth89/CFR-EVO-APP`) covers **the code completely and the data not at
all**. Everything that cannot be regenerated lives on a single SSD in the fire hall.

| Asset | In Git? | Recoverable? | Notes |
| :--- | :--- | :--- | :--- |
| Source, docs, migrations, compose, `data/gis/*.geojson` | ✅ | — | Fully covered |
| **PostgreSQL database** | ❌ | ❌ **No** | Docker named volume `postgres_data`. Holds dispatches, `verified_*` HITL corrections, `custom_places`, and (future) `gate_keys` |
| **Dispatch audio recordings** | ❌ | ❌ **No** | `backend/audio_files/`, `frontend/public/recordings/`; `*.wav` blocked globally |
| **Fine-tuned Whisper model** | ❌ | ⚠️ Costly | `backend/models/whisper-base-cfr-ct2/`, `*.safetensors`/`*.bin`/`*.pt`. Retrainable only if the training audio survives |
| `backend/.env` secrets | ❌ | ⚠️ Manual | Intentionally ignored; needs a documented recovery path, not a repo copy |
| MBTiles archives | ❌ | ⚠️ Hours | `backend/data/tiles/`. Re-crawlable (~430k tiles z12–20) but slow and CDN-dependent |
| Raw ESRI shapefiles | ❌ | ✅ Cheap | Re-downloadable from the Coquitlam Open Data Portal |

#### The Compounding Risk
The audio recordings and the `verified_*` database columns are **one dataset in two
places** — the paired system-vs-actual corpus the STT backtest and parser regression
suites are built on. Losing either half destroys the pair, and no amount of re-importing
municipal data reconstructs it. This is the single highest-value irreplaceable asset in
the system, ahead of even the fine-tuned model, which is derived from it.

Note also that `docker compose down -v` destroys `postgres_data` in one command. There
is currently nothing between that keystroke and total loss of the HITL corpus.

#### Proposed Scope
1. **Scheduled `pg_dump`** of the full database on the kiosk, retained locally with
   rotation. Compressed, this is small; it is the highest value-per-effort step by a
   wide margin and should land first.
2. **Off-kiosk copy.** A backup on the same SSD as the thing it backs up protects
   against `down -v` and bad migrations, not hardware failure. Constrained by the $0 /
   no-cloud rule (CLAUDE.md §1) — candidates are the Nextcloud store already in use for
   this repository, or an external drive at the hall. **Needs a decision.**
3. **Per-table export for curated data.** For `gate_keys` specifically, a one-way
   `pg_dump -t public.gate_keys` into the repo gives git history, authorship, and diffs
   for hand-curated rows. Direction is strictly DB → file: the dump is a backup
   artifact, never an input, so no second source of truth is created.
4. **Audio corpus archival** — the largest asset by volume and the one with no
   regeneration path at all.
5. **Documented restore drill.** An untested backup is a hypothesis. The restore path
   must be written down and actually exercised once.

#### Open Questions
* Where does the off-kiosk copy go, given no cloud dependencies? (Blocks step 2.)
* Retention policy for dispatch audio — is there a privacy or records-retention
  constraint from the department? See [`privacy.md`](./privacy.md).
* Does `backend/.env` recovery belong in a sealed document rather than any repository?
