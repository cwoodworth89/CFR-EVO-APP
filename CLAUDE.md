# CFR EVO: Workspace & Architectural Rules

This rule file defines domain constraints, runtime environments, and workflow standards for **CFR EVO**.

---

## 1. Local-Only Stack, $0 Cost, Municipal Open Data

* **Total offline survival**: STT, geocoding, routing, spatial queries, tile serving and
  WebSocket dispatch MUST all work with no internet. No WAN dependency anywhere.
* **$0 recurring cost**: do NOT reintroduce Supabase, Firebase, AWS RDS, cloud STT, or paid
  geocoding. Everything persists to containerized PostgreSQL 16 + PostGIS 3.4
  (`postgis/postgis:16-3.4-alpine`, `localhost:5432`).
* **PostGIS is the single source of truth.** Parcels, roads, intersections, zones, city
  boundary, road names, `custom_places`, hydrants and vocabulary all live in Postgres.
  In-memory shapefile loading was eliminated. Import scripts: `backend/scripts/
  import_parcels.py`, `import_gis_data.py`.
* **Municipal data authority** — City of Coquitlam Open Data Portal, Open Government
  Licence: 65,401 parcels (`Cadastral.shp` + `Addresses.shp`), 118 active response zones
  (1–134), NFPA 291 hydrants with GPM ratings, LiDAR-height building footprints, and the
  2025 7.5cm aerial orthophotos.

> [!CAUTION]
> **The Open Government Licence covers City data only.** It does not reach
> `basemaps.cartocdn.com`, the source of the street layers — the City neither owns nor
> sublicenses it, and building this for the department does not
> inherit rights the department never held. Carto began stamping unauthenticated tiles
> `API KEY REQUIRED` between the original crawl and the 2026-08-27 re-crawl, which is that
> licence answering for itself. **Do not raise the street layers' `max_zoom` while Carto is
> the source.** Open: punch-list #47b.

**Every code path that reaches outside the LAN is registered in
[`docs/external_calls.md`](docs/external_calls.md)** — what it is, why, and what a crew sees
when the link drops. **Operator ruling 2026-08-31: no new external call without permission.**
Found one? Add a row; do not fix it silently.

**Services**: FastAPI `:8000` · OSRM `:5000` · mbtileserver `:8081` · Mosquitto MQTT over
WebSockets `:9001` (topic `cfr/dispatches`).

**Tiles**: endpoints, zoom depths, the `PRAGMA journal_mode = DELETE` requirement for the
read-only volume, and the `GET`/`OPTIONS`-only constraint (`curl -I` returns 405) are all in
the **`mbtiles-tile-server`** skill. Read it before touching an `.mbtiles` file.

> [!IMPORTANT]
> **Frontend fetches MUST import `API_BASE_URL` / `TILE_BASE_URL` from
> [`frontend/src/apiClient.js`](frontend/src/apiClient.js).** Never use relative paths
> (`fetch('/api/...')`) or hardcoded `localhost` — a kiosk browser reaching the UI over
> Tailscale routes relative requests to the Vite static server and 404s.

---

## 2. Sibling Service Import Path Resolution

Sibling microservices in `/services/*/src` (`gis_service`, `audio_service`,
`notification_service`) are decoupled from `/backend`.

* **Do NOT "fix" sibling imports** in backend orchestration files (e.g. `from gis_service...`).
* Paths are injected into `sys.path` at runtime in
  [`backend/cfr_dispatch/__init__.py`](backend/cfr_dispatch/__init__.py), and into
  `python.analysis.extraPaths` in `.vscode/settings.json` for static analysis.

---

## 3. Git & Remote Kiosk Deployment

**The kiosk (`tcfire@100.95.146.94`, over Tailscale) is the test machine.** The full Docker
stack runs there, not locally. There is no second local stack to keep in sync — local
execution is for scratch scripts and standalone unit checks only.

Edit locally, never on the kiosk. Then:

```bash
git add . && git commit -m "..." && git push origin main
ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP && git pull && cd frontend && npm run build"
```

* **Pre-commit guard**: `git config core.hooksPath .githooks` (once per clone).
  [`.githooks/pre-commit`](.githooks/pre-commit) runs `npm run lint:crash` on staged
  `frontend/src/**`. It blocks only the **crash class** — `no-undef` and TDZ — because those
  compile cleanly through Vite and throw at runtime on the kiosk; `npm run build` does not
  catch them. Bypass with `--no-verify`.
* **Git-ignored files** (`backend/.env`, `frontend/.env.local`, `backend/models/`,
  `backend/data/`) are not synced by git — `scp` them manually.
* The `cfr-postgres` MCP server connects to the kiosk's Postgres over Tailscale. It is the
  one authoritative database.

---

## 4. Skills & Sub-agents

Runbooks live in [`.claude/skills/`](.claude/skills) and load automatically — **check there
before writing a new one.** Specialist personas live in
[`.claude/agents/`](.claude/agents). Both are auto-listed each session; this file does not
duplicate the list.

**The project is in a feature freeze.** Delegate mechanical, bounded work — bulk edits, test
runs, log parsing. Do **not** fan out research or run challenger/auditor chains: their
purpose is to find more, and during a freeze that is the failure mode. A sub-agent returns a
decision (finding, `file:line`, action, confidence), not a report. New discoveries go to
[`docs/post_freeze_backlog.md`](docs/post_freeze_backlog.md) as one line unless they are
crew-visible (§7.1), which promotes immediately.

---

## 5. Address Normalization, Unresolved Locations & Out-of-Bounds

* **No silent coordinate fallbacks.** HUD panels and map components MUST NEVER fall back to
  a default station or city coordinate. This is §6.1 applied to geocoding.
* **Tier 1 — location unresolved** (coords null, NaN or 0): suppress routing lines, show the
  amber standby card (`⚠️ LOCATION UNRESOLVED — Coordinates awaiting operator verification`).
* **Tier 2 — out of bounds**: outside the authoritative City bounding box
  `lat < 49.20 || lat > 49.39 || lng < -122.92 || lng > -122.70` via `isWithinCoquitlam(lat, lng)`,
  show `🌐 NOT AVAILABLE OUTSIDE OF CITY`. **These bounds are depended on by the
  `gis-pipeline-sync` skill — keep them in sync.** Rendering lives in
  `frontend/src/components/kiosk/BlockParcelPanel.jsx` and `PropertySatellitePanel.jsx`.
* **Ambiguity**: when `activeCall.is_ambiguous` or `candidates.length > 1`, show the tactical
  candidate selector, plot every candidate (active gold, alternates sky blue), and recalculate
  OSRM routes on one touch.
* **Canonical normalization** — units, street suffixes, and ` & ` intersection separators —
  is [`frontend/src/utils/addressUtils.js`](frontend/src/utils/addressUtils.js), matched
  backend-side. One implementation, both sides.

---

## 6. No Fabricated Data, No Unsourced Constants

This is an emergency dispatch system. A plausible-looking wrong answer is more
dangerous than a visible unknown, because crews cannot tell it is wrong. These rules
are absolute and override convenience, tidiness, and "the UI looks broken without it."

### 6.1 Never Invent a Value to Fill a Gap
If a value is unknown, it MUST propagate as `null` / `None` and render as an explicit
unknown (`--`, `--:--`, `-- km`, or a Tier 1 warning card). It MUST NEVER be replaced by:
* A default coordinate (see §5 — this is the same rule applied beyond geocoding).
* An estimated ETA, distance, or travel time.
* A default apparatus list, unit roster, radio channel, or incident type.
* A placeholder that reads as real data (`'02:30'`, `'Simulated Address'`, `['SQ1','E1','L1']`).

Suppress the output, warn, and let the operator see the gap. **An unknown reported as
unknown is a correct answer. An unknown reported as a number is a defect.**

### 6.2 Prefer the Authoritative Source Over a Local Model
Where a system of record already computes a value, use its answer rather than
re-deriving one:
* **Routing**: OSRM's `distance` and `duration` are authoritative. Do not recompute
  travel time from speed × distance, and do not estimate turn counts — OSRM returns
  the real turn list in `steps`.
* **Spatial**: PostGIS/PostGIS-backed municipal data is authoritative over hand-derived
  geometry. Do not approximate a spatial relationship with a latitude/longitude
  threshold comparison when the real geometry exists (e.g. rail crossings are
  `railway=level_crossing` in OSM, not `lat < 49.26`).
* **Geocoding**: A miss belongs in `public.intersections` / `public.parcels` as a data
  fix, never as a string-match special case in application code.

### 6.3 Every Magic Number Carries Its Source
Any hardcoded constant affecting operational output MUST carry an inline comment naming
where it came from. Acceptable provenance, in order of preference:

1. **Published standard** — cite it precisely, e.g.
   `# NFPA 1710 s4.1.2.1: 80s turnout time, alarm-to-en-route, fire suppression`
2. **Municipal / authoritative dataset** — name the table or layer, e.g.
   `# public.roads.speed (City of Coquitlam Transportation, posted limit)`
3. **Measured on this system** — state what was measured and when, e.g.
   `# Measured Hall 1 -> 428 Nelson, kiosk OSRM graph 2026-08-21: 9.74 km`
4. **Department operational policy** — name the decision and who set it.

A constant with no comment, or a comment that only restates the number, is treated as a
defect and removed. Invented-sounding rationale ("vehicle momentum preservation",
"assuming ~1.2 turns per km") is not provenance.

Where NFPA figures apply, prefer them over locally invented ones — notably **NFPA 1710**
(turnout and response time objectives) and **NFPA 291** (hydrant flow classification,
already used for hydrant colour coding).

### 6.4 Domain Constants Are Staged, Not Silently Applied
Apparatus physics, response-mode factors, and similar tuning values MUST NOT be applied
implicitly inside a calculation path. They belong in a named configuration surface that
is explicitly enabled and auditable. Until such a feature exists, the data may be
retained as clearly-marked staged seed data that is documented as **not applied** (see
`APPARATUS_TIERS` in `services/gis/src/gis_service/routing_engine.py` and
`frontend/src/utils/EVORoutingEngine.js`).

### 6.5 No Fabricated Dispatches
Test and demonstration paths MUST replay real historical dispatch records
("review" mode). Do not synthesise fake calls, addresses, units, or transcripts to
exercise the kiosk. Genuine pipeline test dispatches use the existing `is_test` flag and
`*TEST*` labelling.

### 6.6 Report Verification Honestly
Do not mark a bug fixed, a phase complete, or a value verified without checking it
against the running system or the working tree. Distinguish **reported** from
**confirmed** in status documents (see `docs/debug_and_qa_punchlist.md`), and state
plainly when something could not be verified and why.

**This applies to our own records first.** The punch list lags the code: a 2026-08-31 sweep
of the 21 crew-visible open items found **five already fixed and merely unrecorded**. Before
working an item, query the database or read the code — a punch-list entry is a *report*, and
the running system is the record. Closing something already done costs an afternoon; the
query costs a minute. `DATABASE_URL` points at the kiosk and the `cfr-postgres` MCP server is
read-only, so checking is always safe.

The same distrust applies to a value stored beside the thing it was derived from. If `X` is
computed from `Y`, name what recomputes `X` when `Y` moves — or do not store `X` (see
`docs/standards/dependency-behaviour.md`, *The same failure outside libraries*).

---

---

## 7. Start From The Source Of Record

§6.3 requires every operational constant to carry its provenance. This section is that
rule moved upstream: **find the source before you write the value, not after.**

Every serious defect found in the 2026-08-21/22 review was a missing or wrong source
rather than a coding error — parcel proximity standing in for road topology, a fuzzy
score standing in for a street vocabulary, an alphabetical list standing in for a token
budget. None of them looked like bugs. They looked like working code.

### 7.1 Before Implementing, Identify What Governs It
Any change that produces an **operational value** or defines a **domain model** —
routing, geocoding, spatial relationships, response-time figures, hydrant classification,
dispatch parsing, STT tuning — starts by identifying the authority for it.

The first stop is [`docs/standards/README.md`](docs/standards/README.md), the index of
standards this project has obtained and what each one governs.

This does **not** apply to ordinary engineering choices — file layout, naming, a helper
extraction, a React hook. Those are judgement, not domain. The test is: *if this value or
model is wrong, can crews tell?* If not, it needs a source.

### 7.2 If Nothing Covers It, Stop And Say So
If `docs/standards/` has no entry covering the decision, **raise it with the user before
implementing.** State what you are about to decide, what would normally govern it, and
that nothing in the project covers it.

Do not improvise a model and carry on. Do not settle it with a "reasonable default". An
invented domain model is the most expensive kind of defect here, because it is invisible:
it produces plausible output indefinitely and nothing flags it.

### 7.3 Recollection Is Not Provenance
If you rely on a specification you know but that is **not** in `docs/standards/`, label it
as recollection and verify it against something authoritative before it reaches code —
the installed source of a pinned dependency counts, memory does not.

This has already bitten: a "224 token" Whisper limit was asserted from memory during the
review. It happened to be right, confirmed afterwards against the installed
`faster_whisper/transcribe.py`, but it was stated as fact before it was checked.

### 7.3a The API Name Is Not The Contract
Most of what governs this system is not a published standard at all — it is the behaviour
of the libraries it runs on. Those defects are the more dangerous kind, because a missing
standard *feels* like a gap while a library assumption feels like knowledge.

Every library defect found so far had the same shape: **the name described the intent, not
the behaviour.**

| Called | The name implies | It actually does |
|:--|:--|:--|
| `hotwords=` | these words are boosted | keeps the first 223 tokens, discards the rest silently |
| `token_set_ratio` | a similarity ratio | returns **100** when one token set is a subset of the other |
| `ST_Contains` | the point is in the polygon | excludes the boundary, so a junction on a zone edge is not contained |

Before an operational decision rests on a library function's behaviour, verify it against
the installed source of the pinned version, and record it in
[`docs/standards/dependency-behaviour.md`](docs/standards/dependency-behaviour.md).

The check is cheap. `token_set_ratio('LOUGHEED HWY', 'ALDERSON AVE & LOUGHEED HWY')`
returns `100`; running that took ten seconds and would have prevented a 4.3 km routing
error.

### 7.4 Cite The Clause, Not The Document
"Per NFPA 1710" is not provenance; `NFPA 1710 s4.1.2.1` is. A citation that cannot be
looked up is decoration. Where a standard has revisions, record which one.

### 7.5 Absence Is Recorded, Not Silent
When a standard *should* exist for something and the project does not have it, it belongs
in `docs/standards/README.md` as an open gap. An unknown source is tracked the same way an
unknown value is (§6.1): visibly.


**Picking up debugging work?** Start at
[`docs/review_status_handoff.md`](docs/review_status_handoff.md) — system state, what
changed, open items in priority order, and the environment gotchas that cost the most time.

See also: [`docs/standards/README.md`](docs/standards/README.md) for the standards index and
[`docs/standards/dependency-behaviour.md`](docs/standards/dependency-behaviour.md) for verified library semantics (§7),
[`PROJECT.md`](PROJECT.md) for architecture/feature/milestone tracking, [`README.md`](README.md) for setup instructions, and [`docs/agent_onboarding.md`](docs/agent_onboarding.md) for the full CLI command reference, SSH/audio (`XDG_RUNTIME_DIR`) heuristics, and the STT MLOps feedback pipeline.
