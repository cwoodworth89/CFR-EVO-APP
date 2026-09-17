# System Monitor & Metrics panel — a refresh, ideas for the operator to pick from

**Status: future development. Nothing built. The road closure row stays exactly as built
(#89–#92).** Compiled by lead on 2026-09-17 from five specialists, each asked for its own
surface only, in one fixed shape: *name · what it shows · source that exists today or "needs
building" · when it shows `--` · what an admin does on seeing it.* Every "exists" below was
verified by the contributor reading the code or running a single SELECT on 2026-09-16/17;
every "needs building" names what would be built. The operator picks; nothing here is a
design.

The panel is `frontend/src/components/admin/SystemMetricsPanel.jsx`, mounted from Dispatch
Review (`DispatchReview.jsx:662`), polling `GET /api/metrics/summary` every 10 s.

## 1. What the panel shows today — and why it reads as broken

| Card | Source | What it actually shows |
|:--|:--|:--|
| API status chip | summary HTTP ok | real |
| Phase 1 phone latency · Phase 2 broadcast total · Whisper STT speed and ratio · GIS parcel lookup | summary `telemetry.*` | **`--` on every tick since the panel was built** — `evaluations.py:118–125` returns `None` literals; the agent keeps its timings in memory and stores nothing |
| Pipeline stages bar + "Call ID" | static | the stage order only, no timings |
| WER · CER · Perfect % · Mismatches % | newest `evaluation_history` row, `stage = 'stt'` | a run dated 2026-09-02, with no date or `n` shown; the endpoint's `stage` filter ignores 25 `chain` rows with WER up to 09-06 |
| Operational matches % | `operational_percent` | **a field the endpoint never returns** |
| Container health | summary `containers` | **always `None`** (no Docker socket); only the explanatory sentence shows |
| Road closure feed (three cards) | `GET /api/road-closures` `sync` + served list | real — keep |

Also returned by the summary and shown nowhere: `total_dispatches` (676), `verified_dispatches`
(662 — **form submissions, including 86 rated PENDING**, not "rated"), `flagged_dispatches`
(51, all-time). `/api/health` returns a hardcoded `"version": "1.0.0"` (`server.py:163`).

**So the refresh is less "add tiles" than "replace cards that have never measured anything."**
Of the 10-second tick, only the API chip and the road closure row carry real numbers.

## 2. The panel's own rule (frontend, idea 8) — adopt before anything else

`--` is for a value that *could* be measured and was not this time. A value the system does
not measure at all gets **one sentence saying so**, collapsed, never a dash at display size —
five dead cards today read as "broken", not "not measured" (§6.1 in reverse: an unknown must
not look like a fault either). Every idea below states its `--` rule against that.

## 3. Ideas, by surface

Legend: **E** = source exists today (verified) · **B** = needs building · **E/B** = half and half.

### 3a. Operations — the kiosk as a machine (lead, from tonight's SSH work; the frontend agent's 1, 2, 5)

| # | Idea | Shows | Source | `--` when | Admin does |
|:--|:--|:--|:--|:--|:--|
| O1 | **Display bundle vs the kiosk's HEAD** | the build the display runs (time + SHA) beside the repo's checked-out HEAD; "bundle is behind HEAD" | **B** — `__BUILD_DATE__` exists (`vite.config.js:10`); needs a build-time `__GIT_SHA__` (local `git rev-parse`) and `GET /api/deploy/status` reading the kiosk repo and `frontend/dist`. Compare to the *kiosk's* HEAD only — GitHub would be an external call | the endpoint cannot read the repo or `dist` | "behind" = pulled but not rebuilt — tonight's `727c297b` gap. Build |
| O2 | **ntfy subscribers** | how many devices hold the `chief-master` topic, and when the count last changed | **B** — the number is in `cfr_ntfy`'s minute-by-minute stats log (`subscribers=N`) and nowhere the api can read; a small host-side writer into `backend/data/` (the listener-heartbeat pattern) or ntfy's own stats endpoint if its version exposes it — to be read, not recalled | no stats line in the last 2 min | **0 with the server up = the phone dropped** — 2026-09-15 20:31 to 16 evening would have shown here, not been noticed by the absence of pushes |
| O3 | **Containers: image build time and age** | per compose service: image created, up since, healthy | **B** — no Docker socket in the api (that is why the existing card is null); the same host-side writer, or `kiosk-remote-operator`'s runbook run on a timer. **Not** a socket mount into the api | the file is older than 2 min | an api image older than the last backend commit = not rebuilt |
| O4 | **Error-boundary hits, display and console** | count and last time of the root diagnostic card per surface, with the error's first line; stale-chunk reloads | **B** — `main.jsx:97` `componentDidCatch` and `recoverFromStaleChunk` (`:67`) only log; needs `POST /api/client-events` (a counter per event type, our API) and a read | none recorded | any hit on the display is crew-visible downtime; `727c297b`'s hook crash would have shown as "#300" |
| O5 | **MQTT feed state (this browser)** | connected / reconnecting / error; last `cfr/dispatches` message time and id | **B** frontend state only — `useMqttListener.js` handles `connect`/`message`/`error` (`:55`, `:66`, `:99`) but exposes nothing. Describes the console's own browser, not the display's (that needs O4's endpoint) | no message since page load | connected but hours-old on a busy night = check the agent and Mosquitto; reconnecting = `:9001` |
| O6 | **Disk on the kiosk** | free space on the data volume; `backend/data/` size; Postgres size | **B** — same host-side writer (`df`, `du`, `pg_database_size`) | file stale | the tile archives and audio grow; nothing warns today |

### 3b. Pipeline — capture, tone gate, STT, parser (pipeline-core-engineer)

| # | Idea | Shows | Source | `--` when | Admin does |
|:--|:--|:--|:--|:--|:--|
| P1 | **Listener heartbeat, age, device** | capture process alive, seconds since heartbeat, device setting | **E** — `GET /api/listener/status` (`audio.py:60–96`) reads `backend/data/listener_status.json`, written every 5 s (`audio_listener.py:50–69`); the console fetches it (`DispatchReview.jsx:115–124`) but shows only a pill. **Two defects in the signal:** `capture_full_dispatch` (`sound_capture.py:8–66`) never writes the heartbeat, so a live 75 s capture reads as "unresponsive" from 30 s in (`audio.py:78, 86–92`); `device` is the `AUDIO_DEVICE_ID` setting (`hardware.py:7–17`), not the resolved name | file absent/unparsable | age > 30 s with no capture in flight = listener or device gone; `journalctl -u cfr-agent` first |
| P2 | **Capture in progress / phase 2 pending — the SAFE/UNSAFE number** | `CAPTURING DISP-… for N s` or `phase 2 pending for N s`, else 0 | **E/B** — phase-2 half exists: a `public.dispatch_sessions` row means phase 1 published and phase 2 not finalised (`session_store.py:82–118`, deleted in phase 2's `finally`, `phase2.py:594`); confirmed on the kiosk, zero rows idle; TTL 600 s but swept lazily, so age > 600 s = dead. Capture half needs the listener to write `state, dispatch_id, since` into its heartbeat (logged at `sound_capture.py:24`, persisted nowhere). The decision rule already exists: `kiosk_capture_state.sh:34–57` | table or file unreadable (never 0) | nonzero = do not restart `cfr-agent` — the 2026-09-05 kill, on screen |
| P3 | **Time since last tone trigger · since last dispatch** | two ages | **E/B** — last dispatch from the panel's `dispatches` prop (`timestamp`; `audio_url` non-null = phase 2 done). Last trigger needs a small endpoint tailing `backend/data/tone_spectral_history.jsonl` (written on every confirmed tone, PA page and rejection, `audio_listener.py:71–98`) | JSONL absent / list empty | trigger age far past the ~11-a-day cadence = the radio feed or device is silent; triggers recent but no dispatch = the gate fires and phase 1 never completes |
| P4 | **Phase-1 and phase-2 stage times, last N** | per-stage ms and a median | **B** — computed and discarded today: `[METRICS] Phase 1 TTA … (DSP: …, STT: …, GIS: …, MQTT: …)` at `phase1.py:166–171` is **worker processing time**, not tone-to-alert (it excludes the 10 s minimum buffer and queue wait — the panel must not label it TTA); phase 2 measures `audio_save_ms, dsp_ms, stt_ms` (`phase2.py:146–166`) and never logs them. Store the `metrics` dict on the row (`target->'pipeline_metrics'`, already `post_freeze_backlog.md:56`) and let the summary replace its nulls | until stored; never a median over fewer than N | STT ms climbing = CPU contention or a heavier model; GIS ms = the geocoder |
| P5 | **STT model loaded, cache state, hotword budget** | model name; loaded from the local cache; `K/N terms kept, U/223 tokens` from the last transcription; the "no HITL street survived" warning | **B** — every value exists in the worker (`transcriber.py:19, 35–48`; `bias_prompt.py:349–356`; 223 verified in `dependency-behaviour.md:178–188`) and none is written anywhere; the worker would write `backend/data/worker_status.json` after `get_whisper_model()` (`worker.py:107`) | file absent / model failed to load | model not what was deployed, or no HITL street survived the cap = look at `.env` or hotword ordering before the next call |
| P6 | **Tier 1 unresolved since T** | count and list of calls shown LOCATION UNRESOLVED | **E** — `LOCATION_UNRESOLVED` in `target.review_flags` (`review_flags.py:36, 108–109`), on rows the panel already holds. Measured: 4 of 66 in 7 days, and `lat IS NULL` gives the same 4; count `lat IS NULL` for full coverage since flags exist only from 08-24/29 | list not arrived; 0 is real | open each; a cluster on one street is a data fix (§6.2), never a string special case |
| P7 | **Parser blanks per field, last N** | nulls per field: talk group, grid, units, call type, response type | **E** — the named flags (`review_flags.py:40–47`; `announcement.py:73–178`). Measured, 66 calls / 7 days: talk group 1, grid 1, response type 1, units 1, call type 2 | no calls in window | a field jumping after a deploy = parser or sanitize regression → `stt-mlops-evaluator`, backtest before/after |
| P8 | **Captures ending on the 75 s cap** | how many recordings stopped at `MAX_DISPATCH_DURATION_S` rather than on silence | **E as a number** — `audio_duration >= 74.9` on the `dispatches` prop (cap `dsp.py:11`, fires `sound_capture.py:65`; the reason is in the journal alone). **Measured: 49 of 302 in 30 days (16%), 3 of the last 5.** Cause not known (§7.7); the runbook's third-round calls would show here | `audio_duration` null | a rising rate = the tail of calls is being cut; listen to a capped recording before touching either constant |

### 3c. GIS, routing, tiles (gis-spatial-engineer)

One fact makes most of these cheap: the api already mounts `./backend/data`, so OSRM build records and the `.mbtiles` archives are readable with no new mount.

| # | Idea | Shows | Source | `--` when | Admin does |
|:--|:--|:--|:--|:--|:--|
| G1 | **Routing graph served** | the `.osrm` name `cfr_osrm` runs, build date, profile, `CFR_CITY_LIMITS_FACTOR`; green/red "OSRM answers a route" | **B** `GET /api/health/routing` — `backend/data/osrm/<name>.build.txt` + one local route between two hall origins | no build record matches; OSRM silent | wrong or unrecorded graph = swapped by hand, rebuild with the script; OSRM down = routes and ETAs off on the kiosk, restart `cfr_osrm` (operator's) |
| G2 | **Route snap far (#88)** | count of dispatches with `ROUTE_SNAP_FAR` (> 50 m), 7/30 d, and the largest with its id | **B** (a SELECT) — `target->'review_flags'` and the snap distance `compute_routing_metrics` records | no routing metrics in window | a cluster at one address = a front point off the road, a data fix |
| G3 | **Geocoding misses** | `LOCATION_UNRESOLVED`, `LOCATION_SUBSTITUTED`, `XSTREET_UNRESOLVED`, `STREET_SECTION_ONLY` counts, 7/30 d, last three addresses | **B** (a SELECT) — `target->'review_flags'` (`review_flags.py`) | no dispatches in window | each address is a candidate fix in `parcels`/`intersections` (#82/#85's rules) |
| G4 | **Tile archives** | per archive: listed by `cfr_tiles`, probe result as HTTP code + bytes (real tile vs blank), WAL mode | **B** `GET /api/health/tiles` — `http://tiles:8080/services` and the `tile-health` probes over the compose network; `PRAGMA journal_mode` on the mounted `.mbtiles` (read-only) | tile server silent | blank or missing = an empty map layer on the kiosk; WAL = the read-only volume cannot serve it (`mbtiles-tile-server` skill) |
| G5 | **GIS layer copies** | per spatial table: row count now beside the copy date and expected count | **B, the only one needing a migration** — a `gis_layer_copies` table written by the import scripts (date, product, count), cited by `data_sources.md`; parsing the register's markdown live is fragile | a layer with no recorded copy | a count that moved without a new copy = changed outside an import; an old date = check the City's product (a bench pull, operator's) |
| G6 | **Zone coverage gap (#92's strip)** | active closures with `zone_id` null (in the buffer, no zone in reach); dispatches in 30 d inside the boundary but in no zone | **B** (two SELECTs) — `road_closures`, `dispatches`, `zones`, `city_boundary` | zone or boundary query fails | a non-zero dispatch count = a real call landed where no zone covers it; the evidence to take to whoever owns the zone layer (the Bypass strip is 27 m) |
| G7 | **Closure feed scope as served** | DriveBC: the `bbox` asked for and events returned; Municipal 511: files fetched, issues seen, kept by publisher, dropped by the spatial tests | **B, no migration** — per-step counts added to `road_closure_sync_status.sources` (JSONB) by the sync, read by the existing `sync` block; today only the summed counts exist | before the first sync that records them | a box count of 0 for days, or "issues kept" collapsing = the feed changed shape or the publisher string changed — #92's silent failure |
| G8 | **Spatial query health** | slowest closure spatial statement in the last sync; `zones.hall_id` null count (134 of 134) | **B, no migration** — timings into the same JSONB; `hall_id` from `zones` | before the first sync that records it | a slowest-statement figure climbing toward seconds is the #92 regression's signature — catch it before a sync stalls |

GIS's order if fewer: **G1, G4, G6, G3**; G7 and G8 cheapest; G5 the only migration.

### 3d. Metrics — the running numbers (performance-metrics-analyst)

Each with a one-sentence definition; every window with no data is `--`, never a 0 dressed as a rate. All buckets must use `AT TIME ZONE 'America/Vancouver'` — the DB session is UTC.

| # | Idea | Definition | Source | Now | Admin does |
|:--|:--|:--|:--|:--|:--|
| M1 | **Dispatch volume, 7 d / 30 d** with a per-day strip | count of `dispatches` rows by `timestamp` in the trailing window, bucketed by local day | **E** — one SELECT (in the source list) | 66 / 302 | a day at 0 while the radio was busy = the agent missed calls |
| M2 | **Located share by week (Tier 1 rate)** | per ISO week, rows with `target.lat` non-null over all rows | **E** — `jsonb_typeof(target->'lat') <> 'null'`; cross-checked 8/8 against `LOCATION_UNRESOLVED` | 270 / 302 (89.4%) in 30 d; weeks 57/59, 60/63, 33/36 | a falling week = geocoder misses; open the unresolved calls' notes |
| M3 | **Phase-1 time-to-alert, median and p90, last 30** | phase-1 publish wall time − tone-detection wall time | **B** — the alert-side time exists (`timestamp` is the phase-1 INSERT's `now()`); the tone-side time is recorded nowhere the API can read; store both in `target->'pipeline_metrics'` (see P4) | `--` until stored; show `n` under 30 | p90 creeping up = STT or GIS slowing |
| M4 | **STT word error rate** | (a) the newest harness WER **with its date and `n`** — served today without either; (b) per-call WER of `raw_transcript` vs `verified_transcript` over the last N verified calls | **(a) E, (b) B** — corpus: 661 of 676 verified (288 in 30 d); exclude 12 against a `[Transcription Failed]` sentinel; **caveat that must print beside (b): 324 of 661 verified transcripts are byte-identical to `sanitized_transcript`** (accepted through Prefill), so raw-vs-verified there measures the sanitizer as much as hearing | (a) 2026-09-02 run | a rise after a model or hotword change; the holdout run is the honest number, the live one the early warning |
| M5 | **Review backlog** | rows rated `PENDING`, split never-opened (`feedback_submitted` not true) vs submitted-without-a-rating, plus the oldest | **E** — one SELECT | **100 unrated — 14 never opened, 86 submitted with no rating chosen**; oldest 2026-07-12 | work the queue; the 86 are the surprise, since M2, M7 and the review ideas rest on the rating |
| M6 | **Ground-truth corpus size** | rows with a verified transcript, an `audio_url`, and `include_in_training` not false (missing key = true, the extract scripts' convention — the DDL default says false and 57 rows lack the key; the definition must name this) | **E** — one SELECT; per-field fill beside it | **625 training-eligible** (468 on 08-31); 638 with all four core fields; talkgroup 584, grid 579, response type 161, x-streets 150/136 | flat for a week while calls arrive = review has stopped; the per-field row shows what is thin |
| M7 | **Operator rating mix, last 30 rated** | PERFECT / OPERATIONAL / FAILED over the 30 most recent rated calls; all-time beside | **E** — one SELECT; notes via `COALESCE(target->>'review_notes', review_notes)` (333 in JSON, 60 in the column) | 25 / 5 / 0; all-time 298 / 246 / 32 of 576 | PERFECT drifting to OPERATIONAL = "something small missing"; any FAILED = open its note. **The rated set is what the operator chose to review, not a sample; no trend without saying so** |
| M8 | **Review flags by name, 30 d** | share of rows with a non-empty `target.review_flags` over rows carrying the key; count per flag | **E** — one SELECT (`jsonb_array_elements_text`) | 51 of 163 (31.3%): XSTREET_UNRESOLVED 26, XSTREET_SUBSTITUTED 13, LOCATION_SUBSTITUTED 11, LOCATION_UNRESOLVED 8, GRID_MISMATCH 4 … | the top name says where to look — today cross-streets, not addresses |

### 3e. Review state (call-review-analyst)

Column semantics counted on the live table: `quality_rating` is never null (PERFECT / OPERATIONAL / FAILED / PENDING); **"not reviewed" is `feedback_submitted = false`** (14 calls, 09-15 to 09-16), not a missing rating; `model_updated` is the "fed back to the corpus" flag and **stops after 2026-09-01** (164 reviewed calls since with `false`); nothing stores Tier 2 out-of-city — the kiosk computes it at display time.

| # | Idea | Shows | Source | `--` when | Reviewer does |
|:--|:--|:--|:--|:--|:--|
| R1 | **Awaiting review** | count and oldest age of `feedback_submitted = false`, split PENDING vs rated | **E** | query fails (0 is 0) | work the queue oldest first |
| R2 | **Rating mix, last N days**, reviewed calls only | PERFECT / OPERATIONAL / FAILED / PENDING counts | **E** | no reviewed calls in window | a rise in FAILED or OPERATIONAL = pull those calls through intake before trusting a trend |
| R3 | **Reviewed but not fed back** | `feedback_submitted = true AND model_updated = false`, with the newest `model_updated = true` date | **E** — 164 now, nothing since 09-01. **Operator question: does anything still set `model_updated` since training mode was removed (`d5fbdcc`)?** If not, this tile says "no feed-back process", not a count | query fails | run the export/backtest, or ask why it stopped |
| R4 | **Flagged since last review** | calls with non-empty `review_flags` newer than the newest reviewed call, by flag | **E** for Tier 1 and the parser flags; **Tier 2 needs a new endpoint** (`ST_Covers` against stored lat/lng) — until then `--` "not recorded", never 0 | the period before flags existed (~mid-August) — not zero | start with those calls; LOCATION_SUBSTITUTED and NO_TALK_GROUP are closest to crew-visible |
| R5 | **Rated PERFECT but the record disagrees** (§6.6) | calls rated PERFECT with a `verified_*` value different from the system field, comparing only where both sides are non-null | **E** — `verified_*` vs `incident_type` / `target->>…` | no call has both sides filled | re-rate, or fix the verified value — before it feeds a figure or closes a punch-list item |
| R6 | **Notes-mirror drift** | rows where `review_notes` (column) ≠ `target->>'review_notes'` | **E** — the weakest; drop it if room is short | neither set | trust the review screen, not an export built on the column |

## 4. New endpoints and tables the ideas would need

| Needed by | What |
|:--|:--|
| O1 | `GET /api/deploy/status` + a build-time `__GIT_SHA__` |
| O2, O3, O6 | a small host-side writer into `backend/data/` (ntfy subscriber count, container ages, disk) — the listener-heartbeat pattern; **not** a Docker socket in the api |
| O4, O5 (display half) | `POST /api/client-events` + a read |
| P2 (capture half), P5 | the listener and worker writing their state files |
| P3 (trigger half) | an endpoint tailing `tone_spectral_history.jsonl` |
| P4, M3 | the pipeline storing its per-call `metrics` on the row (`post_freeze_backlog.md:56`) |
| G1, G4 | `GET /api/health/routing`, `GET /api/health/tiles` |
| G2, G3, G6, R4 (Tier 2) | SELECT endpoints |
| G5 | a `gis_layer_copies` table — the only migration |
| G7, G8 | per-step counts and timings into `road_closure_sync_status.sources` (no migration) |

Everything reads a local source. **No new external call anywhere in this document.**

## 5. Caveats found while reading — recorded, not fixed

- **`is_test` never reaches the corpus.** `payload_builder.py:496` sends it; `DispatchCreateSchema` (`schemas.py:17–38`) has no field, so Pydantic drops it; 0 of 676 rows carry the key. `*TEST*` reaches ntfy and MQTT but not the row, so **no corpus figure can exclude test dispatches** (§6.5). Backlog.
- **The listener heartbeat reads "unresponsive" during any capture** past 30 s, and `device` is the setting, not the resolved name (P1). Backlog — the first one matters for restart decisions.
- **`[METRICS] Phase 1 TTA` is processing time, not tone-to-alert.** Any tile must not call it TTA.
- **`verified_dispatches` on the summary counts form submissions**, including 86 PENDING.
- **`operational_percent`** is read by the panel and never returned; `/api/health`'s version is hardcoded.
- **The DB session is UTC**; every daily or weekly bucket needs `AT TIME ZONE 'America/Vancouver'`.
- **`model_updated` stops at 2026-09-01** — the operator's question in R3.
- **16% of captures end on the 75 s cap** (P8); cause unknown, stated as such.

## 6. If the operator wants a short list first

The contributors' own orderings, merged by lead: **P2** (the SAFE/UNSAFE number — the 09-05 kill on screen), **O2** (ntfy subscribers — yesterday's silent phone), **O1** (bundle vs HEAD — tonight's deploy gap), **G1** and **G4** (wrong graph, blank map — both crew-visible), **M5/R1** (the review backlog, which everything else rests on), **P6/G3** (unresolved and misses, the data fixes), then the §2 rule applied to the five dead cards. The road closure row as built.

Backlog line: [`../post_freeze_backlog.md`](../post_freeze_backlog.md), 2026-09-17.
