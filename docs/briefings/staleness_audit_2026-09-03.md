# Staleness audit — 2026-09-03

**Scope:** the whole tree — 421 tracked files, 144 of them Markdown — plus the eight
`.claude/agents/` personas and the fourteen skill `description:` lines, neither of which the
[2026-08-30 skills audit](skills_audit_2026-08-30.md) covered.
**Method:** deterministic cross-reference scans (`tools/audit_staleness.py`), every
candidate then checked against the source line, git history, or the kiosk database
(`cfr-postgres`, read-only) before it appears here. No item below came from judgement about
prose. The raw scan output is [`staleness_audit_2026-09-03_raw_scan.md`](staleness_audit_2026-09-03_raw_scan.md).
**Operator rulings the same day:** the `.env.example` files go; anything about setting up a
machine is deferred until the code is stable; Antigravity is no longer used on this project.

| Check | Scanned | Flagged by scan | Real after verification |
|:--|--:|--:|--:|
| File paths referenced from Markdown | 731 | 35 | 11 (the rest bannered-historical, or excused with `audit-ok`) |
| Schema objects dropped/renamed by migrations, still in code | 16 | 11 | 1 |
| Python modules with no importer | 134 | 2 | 2 |
| Scripts / shell files referenced from nothing | 45 | 13 | 4 (tests and `oneshot/` excluded) |
| Frontend files with no importer | 62 | 1 | 1 |
| Frontend/pipeline API calls vs backend routes | 23 calls / 45 routes | 4 | 1 |
| Container / service names in docs vs compose | 22 names | 22 | 3 |
| Env vars: code vs `.env.example` vs compose | 26 | 22 | both example files stale |
| Punch-list header status vs body status line | 71 files | 12 | 12 (the body line is the fossil) |
| Machine-specific `file:///` links | — | 32 | 32 |
| Agent personas read against the code they describe | 8 | — | 6 stale, 1 obsolete, 1 correct |
| Skill `description:` lines read against their own bodies | 14 | — | 4 stale |

## Verified against the kiosk database

Every migration in `backend/migrations/` and the former root `migration_stt_tuning.sql` is
applied: each added table and column is present, each dropped one is absent, `zone_for_point()`
exists. One exception: `parcels_frontpoint_snapshot_20260828` does not exist. Either it was
cleaned up after use or the migration never ran; the database cannot say which.

**`backend/api/init_db.sql` has diverged from the live schema and nothing replays migrations.**
Compose mounts `init_db.sql` into `docker-entrypoint-initdb.d`; no script, Dockerfile, or compose
entry applies `backend/migrations/*.sql`. `init_db.sql` still defines `parcels.lat`/`lng` and
`intersections.zone_id`, both gone on the kiosk. A second hall built from `docker compose up`
starts on the 2026-08-20 schema plus whatever someone applies by hand. Deployment design is
deferred by the operator, so this is recorded in `docs/post_freeze_backlog.md` rather than fixed.

---

## Findings

### Tier 1 — misled a newcomer or broke on first run

1. **`frontend/.env.example` named the wrong variable.** It declared `VITE_API_URL`;
   `apiClient.js:5,17` reads `VITE_API_BASE_URL` and `VITE_TILE_BASE_URL`, the variables
   CLAUDE.md §1 relies on for Tailscale kiosk access. A copied example was silently ignored.
   It also declared `VITE_NTFY_TOPIC_SECRET`, which nothing reads. **Deleted**, with
   `backend/.env.example` (six keys; missing `NTFY_TOPIC`, which `docker-compose.yml:92` says
   must match the agent's env, plus `ADMIN_USERNAME`/`ADMIN_PASSWORD`, `AUDIO_DEVICE_ID`,
   `MQTT_DISPATCH_TOPIC`). Every doc and script that said "copy `.env.example`" was corrected;
   `setup_kiosk.sh` now stops with a message if `backend/.env` is absent instead of copying a
   template that no longer exists.
2. **`tools/trace_geocode_corpus.py:226` selected `dispatches.confidence_score`**,
   dropped 2026-08-29 and confirmed absent on the kiosk. The script raised on its first query.
   **Fixed**: the column and the "stored confidence on wrong streets" summary are gone.
3. **`backend/scripts/update_gis_data.py::update_hydrant_data` still wrote
   `frontend/public/data/hydrants.json`**, the browser cache retired 2026-08-22;
   `sync_hydrants.py` → `public.hydrants` is the live path. **Removed** (140 lines); the
   shapefile refresh half of the script is unchanged and still registered in
   `docs/external_calls.md` §5.
4. **32 absolute `file:///c:/Users/Curtis/...` links** across `docs/agent_onboarding.md`,
   `docs/development_freeze_summary.md`, `docs/gis_endpoints.md` and two skills. Dead on the
   kiosk and for anyone else. **Converted to relative paths.**
5. **`init_db.sql` vs live schema** — see above. **Backlog**, not fixed.

### Tier 2 — skills and agents that would misdirect a session

6. **Six of the eight agent personas were 2026-08-20 designs written in the present tense**, the
   pattern the 08-30 audit named. `dispatch-qa-engineer` described `--omit-mqtt`/`--omit-ntfy`/
   `--omit-db` flags and a simulation harness that exist nowhere and that `review_status_handoff.md`
   records as deliberately deleted (§6.5 forbids synthesised dispatches). **Deleted.**
   `call-review-analyst` triaged on `confidence_score < 90%` and "landmark additions";
   `frontend-kiosk-architect` named MapLibre (not a dependency), "72pt+ typography" and
   "24/7/365 memory longevity"; `gis-spatial-engineer` listed `Parcels.shp` and `Fire_Hydrants.shp`
   (the sources are `Cadastral.shp` + `Addresses.shp` and the City ArcGIS hydrant endpoint) and
   "apparatus-aware routing" (staged, not applied, §6.4); `kiosk-remote-operator` named systemd
   units `cfr-orchestrator` and `cfr-gateway` (only `cfr-agent` exists, `setup_kiosk.sh:74`);
   `performance-metrics-analyst` listed confidence breakdowns, GIS cache hit rates and chute-time
   reductions; `pipeline-core-engineer` stated a "<15s" Phase 1 target with no source.
   **All six rewritten** to the form `stt-mlops-evaluator` (2026-09-02) already had: point at the
   skill that is the runbook, state only what the code and CLAUDE.md say, return a decision not a
   report, and record in one line what the previous version got wrong.
7. **Four skill `description:` lines advertised something their own body retracts.** The
   description is the text that decides whether a skill loads. `emergency-routing-engine`:
   "dual-mode (online Google / offline OSRM)" — body says OSRM only. `google-imagery-streetview`:
   "high-resolution satellite aerial imagery" — body says the aerial layer is City orthophotos,
   not this skill. `hitl-log-analysis`: "low-confidence dispatches" — the column is gone.
   `road-closure-management`: "spatial collision workflows" — body marks it a specification.
   **All four corrected.**
8. `local-stack-orchestrator/SKILL.md:36` `docker compose logs -f cfr_tiles` — the service is
   `tiles`; the command failed. **Fixed.**
9. `stt-mlops-backtest/SKILL.md:12` relative link one `../` short. **Fixed.**
10. `gis-spatial-analysis/SKILL.md:209` told you to verify provenance with a script deleted
    2026-08-31 (`9017e6a`, "could not do its job"). **Reworded; `audit-ok` marker added.**
11. `kiosk-ui-audit/SKILL.md:20` and `GEMINI.md` §"Antigravity-specific" referred to a tool no
    longer used. **Removed** (`GEMINI.md` is now only the pointer to `CLAUDE.md`), along with
    `.antigravityignore`.

### Tier 3 — dead code

12. `scripts/inject_test_call.py` POSTed a fabricated dispatch (invented address and units) to the
    kiosk IP, against §6.5. Referenced nowhere since 2026-08-05. **Deleted.**
13. `backend/tests/test_variables.py` was a 2026-06-14 probe of the Join push service, not a test,
    and an unregistered outbound call (`joinjoaomgcd.appspot.com`, fired when `JOIN_API_KEY` was
    set). **Deleted; row added to `docs/external_calls.md` §1.**
14. `backend/test_device.py` (2026-07-06) duplicated `backend/scripts/debug_audio.py`. **Deleted.**
15. `frontend/src/components/hud/TacticalInfoCard.jsx` had no importer. **Deleted.**
16. `migration_stt_tuning.sql` sat at the repository root; applied on the kiosk and already in
    `init_db.sql`. **Moved** to `backend/migrations/2026-07-12_stt_tuning_columns.sql` with a
    `WHY` header.
17. `tools/analyze_historical_tones.py` is referenced only from a walkthrough bannered as
    historical. **Kept** — it imports `services/audio_analysis`, which exists, and whether the PA
    tone work superseded it is not something a scan can tell.
18. `backend/migrations/2026-08-28_snapshot_parcel_front_points.sql` creates a table that does
    not exist on the kiosk. **Kept** as the record; see the database section.

### Tier 4 — documentation rot

19. `backend/README.md:62` pointed at `cfr_dispatch/parser.py`; the parser is a package.
    `:63` said "cloud configurations"; `config/cloud.py` was deleted 2026-08-31. **Fixed.**
20. `docs/milestones.md:71` → `.agents/rules/…`, archived out 2026-08-30. **Annotated, `audit-ok`.**
21. `docs/qa_handoff_2026-08-31.md:99` → `test_tile_layer_adversarial.js`, deleted the same day the
    handoff was written. The passage records why. **`audit-ok` added.**
22. `docs/architecture/database_and_datastores.md:86` named `/api/gis/search`; the route is
    `/api/parcels/search`. **Fixed.**
23. `docs/decomposition_plan.md` (356 lines, compiled 2026-08-21) and
    `docs/briefings/skills_audit_2026-08-30.md` had no inbound link from any document.
    **The plan got a historical banner and two `audit-ok` markers; the skills audit is now linked
    from `docs/review_status_handoff.md`**, which had recorded it as unfinished. The plan is still
    unlinked; the banner makes it self-describing.
24. **Twelve punch-list files whose header table says CLOSED while the body's original
    `> **Status**:` line still says Open**: 10, 12, 31, 35b, 38, 39, 40, 41, 42, 48, 51a, 58.
    Checked #10 and #35b: the header is current and the closing analysis is at the foot of each
    file; the body line is a fossil. 33 of the other 45 closed items updated that line
    (`> **Status**: ✅ **Closed <date> — …**`). **Fixed 2026-09-04** on the operator's instruction: each body line now reads
    `✅ **Closed <date>.**` with the original opening text kept after it in italics.

### Already acknowledged before this audit (excused with `audit-ok`, listed so nobody re-finds them)

`docs/briefings/pa_tone_discriminator.md` → `test_listener.py` (deleted 2026-08-31, `5aa72e0`);
`docs/briefings/base_site_rows_decision.md` → `dispatch_corpus_snapping_benchmark.json`;
`docs/briefings/valhalla_standard_review_response.md` → `DispatchCard.tsx`, `routers/dispatch.py`
(the sentence exists to say they never existed); `docs/standards/README.md` → `evo_routing_engine.md`;
`GEMINI.md` → the three directory-local `GEMINI.md` files it records deleting;
`docs/walkthroughs/local_stack_and_dsp_calibration_walkthrough.md` → `shapefile_loader.py`.

---

## Decisions

**A. Antigravity — resolved.** Operator ruling 2026-09-03: no longer in use. Its delegation
section, ignore file and the one skill reference are gone; `GEMINI.md` remains as a pointer so a
Gemini-based tool that wanders in reads `CLAUDE.md` instead of nothing.

**B. Bannered-superseded documents — resolved 2026-09-04, pruned.** Operator ruling: a document
that describes a system no longer run is deleted, not kept with a banner. `gis_endpoints.md` and
`walkthroughs/local_stack_and_dsp_calibration_walkthrough.md` are gone (the walkthrough also
repeated the `FREQUENCY_TOLERANCE_HZ = 8` claim that `GEMINI.md` records as wrong).
`database_and_datastores.md` and `development_freeze_summary.md` stay: each has sections that
are still the current description, marked as such. `docs/README.md` now carries the rule.

**C. `ActiveDispatchPanel.jsx:145` — resolved 2026-09-04.** "Visual mock" was a hangover from
the removed simulator vocabulary. The kiosk's real replay is the review mode (`isReview`, the
REVIEW REPLAY banner with auto-dismiss paused); this panel's fallback branch is simply Street
View being unavailable, so the label now says that: "Street View is online-only and no Google
key is configured. Location:". The two runbook sections that still said "simulating", and ran
a test module deleted 2026-08-31, were rewritten to point at the review replay.

**D. Setup and deployment material — deferred by ruling.** `setup_kiosk.sh` was edited only
where it referenced the deleted templates; it documents the machine that exists.
`docs/laptop_kiosk_setup.md` and `docs/hardware_specification.md` were not reviewed.

## What this audit did not check

Prose describing behaviour the code no longer has, in files without a banner; whether the 20
open punch-list items are already fixed (§6.6 found 5 of 21 were, on 2026-08-31); whether each
skill's procedure still runs end to end on the kiosk. Those need reading, not scanning.

<!-- audit-ok: frontend/.env.example -- deleted 2026-09-03; item 1 records why -->
<!-- audit-ok: backend/.env.example -- deleted 2026-09-03; item 1 records why -->
<!-- audit-ok: scripts/inject_test_call.py -- deleted 2026-09-03; item 12 -->
<!-- audit-ok: backend/tests/test_variables.py -- deleted 2026-09-03; item 13 -->
<!-- audit-ok: backend/test_device.py -- deleted 2026-09-03; item 14 -->
<!-- audit-ok: frontend/src/components/hud/TacticalInfoCard.jsx -- deleted 2026-09-03; item 15 -->
<!-- audit-ok: .claude/agents/dispatch-qa-engineer.md -- deleted 2026-09-03; item 6 -->
<!-- audit-ok: .antigravityignore -- deleted 2026-09-03; item 11 -->
<!-- audit-ok: backend/scripts/verify_ortho_provenance.py -- deleted 2026-08-31; item 10 records the skill fix -->
<!-- audit-ok: frontend/src/components/DispatchCard.tsx -- never existed; listed under already-acknowledged -->
<!-- audit-ok: backend/api/routers/dispatch.py -- never existed; listed under already-acknowledged -->
<!-- audit-ok: backend/tests/test_listener.py -- deleted 2026-08-31; listed under already-acknowledged -->
<!-- audit-ok: docs/dispatch_corpus_snapping_benchmark.json -- deleted 2026-08-31; listed under already-acknowledged -->
<!-- audit-ok: docs/evo_routing_engine.md -- deleted 2026-08-30; listed under already-acknowledged -->
<!-- audit-ok: services/gis/src/gis_service/shapefile_loader.py -- deleted 2026-08-20; listed under already-acknowledged -->
<!-- audit-ok: backend/cfr_dispatch/parser.py -- now a package; item 19 -->
<!-- audit-ok: migration_stt_tuning.sql -- moved into backend/migrations/ 2026-09-03; item 16 -->

<!-- audit-ok: docs/gis_endpoints.md -- deleted 2026-09-04; decision B records it -->
<!-- audit-ok: docs/walkthroughs/local_stack_and_dsp_calibration_walkthrough.md -- deleted 2026-09-04; decision B records it -->
<!-- audit-ok: backend/cfr_dispatch/config/cloud.py -- renamed to runtime.py 2026-08-31; item 19 records it -->
