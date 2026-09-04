# Staleness audit 2026-09-03 — raw scan output

Scan of the working tree at `0ca507d` **before** the cleanup commit, kept as the evidence behind
[`staleness_audit_2026-09-03.md`](staleness_audit_2026-09-03.md). Every item is a mechanical
cross-reference and several are false positives (migration ordering, generic column names,
deletions already recorded with `audit-ok`); the findings document is the verified subset.
Re-run with `python backend/scripts/audit_staleness.py --out <file>`.

```text
## A. Dangling file paths referenced from markdown

Checked 731 path-like references. **35 dangling across 18 docs.**

- `GEMINI.md` (last touched 2026-08-31)
    - L15 `backend/GEMINI.md`
    - L15 `frontend/GEMINI.md`
    - L15 `services/gis/GEMINI.md`
- `docs/gis_endpoints.md` (last touched 2026-08-30)
    - L8 `data/hydrants.json`
    - L11 `data/blocks.json`
    - L12 `data/intersections.json`
- `docs/punchlist/10-three-test-modules-have-never-run-in-review.md` (last touched 2026-08-31)
    - L46 `tests/test_database_integration.py`
    - L47 `tests/test_listener.py`
    - L48 `tests/test_keyword_spotter.py`
- `docs/briefings/pa_tone_discriminator.md` (last touched 2026-08-31)
    - L137 `backend/tests/test_listener.py`
    - L150 `tests/test_listener.py`
- `docs/briefings/valhalla_standard_review_response.md` (last touched 2026-08-31)
    - L131 `frontend/src/components/DispatchCard.tsx`
    - L132 `backend/api/routers/dispatch.py`
- `docs/decomposition_plan.md` (last touched 2026-08-31)
    - L107 `frontend/src/components/DashboardHUD.jsx`
    - L245 `backend/test_capture.wav`
- `docs/development_freeze_summary.md` (last touched 2026-08-21)
    - L128 `frontend/src/components/DashboardHUD.jsx`
    - L128 `frontend/src/components/review/SatelliteMiniMap.jsx`
- `docs/walkthroughs/local_stack_and_dsp_calibration_walkthrough.md` (last touched 2026-08-31)
    - L35 `config/cloud.py`
    - L37 `services/gis/src/gis_service/shapefile_loader.py`
- `.claude/skills/gis-spatial-analysis/SKILL.md` (last touched 2026-08-31)
    - L209 `backend/scripts/verify_ortho_provenance.py`
- `.claude/skills/stt-mlops-backtest/SKILL.md` (last touched 2026-09-02)
    - L12 `../../docs/briefings/whisper_training_round1_labelling.md`
- `backend/README.md` (last touched 2026-08-31)
    - L62 `cfr_dispatch/parser.py`
- `docs/PROJECT_IDEAS.md` (last touched 2026-08-31)
    - L567 `styles/root.json`
- `docs/briefings/base_site_rows_decision.md` (last touched 2026-08-31)
    - L127 `docs/dispatch_corpus_snapping_benchmark.json`
- `docs/dispatch_integration_options.md` (last touched 2026-08-31)
    - L200 `agent/locution_ocr.py`
- `docs/milestones.md` (last touched 2026-09-02)
    - L71 `.agents/rules/local_stack_and_dsp_rules.md`
- `docs/punchlist/01-erratic-routing-loops-intra-municipal-path-preference.md` (last touched 2026-08-30)
    - L26 `osrm/profiles/emergency.lua`
- `docs/qa_handoff_2026-08-31.md` (last touched 2026-08-31)
    - L99 `frontend/test_tile_layer_adversarial.js`
- `docs/standards/README.md` (last touched 2026-08-31)
    - L50 `docs/evo_routing_engine.md`

## B. Schema objects dropped or renamed by migrations, still referenced in code

- **`custom_places`** — table — `2026-08-21_drop_custom_places.sql`: 5 code references
    - `backend/scripts/audit_skill_references.py:127` `#     <!-- audit-ok: backend/data/vocabulary/custom_places.json -- records a deletion -->`
    - `backend/scripts/audit_skill_references.py:188` `file a defect used to live in is CORRECT documentation, not rot. `custom_places.json``
    - `backend/tests/test_postgis_migration.py:140` `# Replaces test_landmarks_count. public.landmarks was renamed to custom_places in`
    - `backend/tests/test_postgis_migration.py:146` `for table in ('landmarks', 'custom_places'):`
    - `frontend/src/components/map/layerIcons.js:14` `* hardcoded school list came out of MapLayers.jsx with the custom_places removal`
- **`live_calls`** — table — `2026-08-21_recover_orphaned_live_calls.sql`: 0 code references
- **`live_calls`** — table -> dispatches — `2026-08-21_rename_live_calls_to_dispatches.sql`: 0 code references
- **`zone_id`** — column of intersections — `2026-08-22_canonical_zone_for_point.sql`: 62 code references
    - `backend/api/closure_spatial.py:79` `SELECT z.map_name AS zone_id, z.hall_id`
    - `backend/api/closure_spatial.py:85` `{str(r["zone_id"]) for r in rows if r["zone_id"] is not None},`
    - `backend/api/closure_spatial.py:96` `SELECT z.map_name AS zone_id, z.hall_id`
    - `backend/api/closure_spatial.py:104` `return affected, str(primary["zone_id"]), primary["hall_id"]`
    - `backend/api/closure_spatial.py:108` `fallback = next((r for r in rows if str(r["zone_id"]) == affected[0]), None)`
    - `backend/api/models.py:101` `zone_id = Column(String(16), index=True, nullable=True)`
    - `backend/api/models.py:170` `zone_id = Column(String(16), index=True, nullable=True)`
    - `backend/api/road_closure_service.py:81` `enriches with zone_id and affected_zones array, and upserts into PostgreSQL road_closures table.`
    - … 54 more
- **`parcels_frontpoint_snapshot_20260828`** — table — `2026-08-28_snapshot_parcel_front_points.sql`: 0 code references
- **`confidence_score`** — column of dispatches — `2026-08-29_drop_confidence_score.sql`: 20 code references
    - `backend/api/models.py:31` `# confidence_score was removed 2026-08-29 (punch-list #45). It was a`
    - `backend/cfr_dispatch/pipeline/models.py:34` `# Count of named review flags. Replaced confidence_score 2026-08-29`
    - `backend/cfr_dispatch/pipeline/models.py:50` `# Count of named review flags. Replaced confidence_score 2026-08-29`
    - `backend/cfr_dispatch/pipeline/phase2.py:278` `# the old "confidence_score": 100.0 here silently erased those.`
    - `backend/cfr_dispatch/pipeline/review_flags.py:3` `Replaces `confidence_score` (punch-list #45). That was a metadata-completeness score`
    - `backend/scripts/trace_geocode_corpus.py:11` ``confidence_score`) alongside what a human confirmed was true (`verified_*`). That`
    - `backend/scripts/trace_geocode_corpus.py:226` `"SELECT dispatch_id, confidence_score, raw_transcript, verified_address, "`
    - `backend/scripts/trace_geocode_corpus.py:263` `if kind == "wrong-street" and r["confidence_score"] is not None:`
    - … 12 more
- **`access_far_corner_m`** — column of parcels — `2026-08-31_drop_access_far_corner.sql`: 1 code references
    - `backend/scripts/import_parcels.py:353` `# access_far_corner_m column -- metres from the arrival point to the furthest corner`
- **`centroid_lat`** — column of parcels — `2026-08-31_drop_duplicate_centroid_columns.sql`: 32 code references
    - `backend/api/models.py:166` `centroid_lat = Column(Float, nullable=True)`
    - `backend/api/routers/parcels.py:75` `"lat": p.centroid_lat,`
    - `backend/api/routers/parcels.py:145` `"lat": p.centroid_lat,`
    - `backend/api/routers/parcels.py:147` `"front_lat": p.front_lat or p.centroid_lat,`
    - `backend/api/routers/parcels.py:166` `ParcelModel.centroid_lat >= min_lat,`
    - `backend/api/routers/parcels.py:167` `ParcelModel.centroid_lat <= max_lat,`
    - `backend/api/routers/streetview.py:32` `# 2026-08-31: the columns were renamed to centroid_lat/centroid_lng and this`
    - `backend/api/routers/streetview.py:35` `"lat": r.front_lat or r.centroid_lat,`
    - … 24 more
- **`centroid_lng`** — column of parcels — `2026-08-31_drop_duplicate_centroid_columns.sql`: 29 code references
    - `backend/api/models.py:167` `centroid_lng = Column(Float, nullable=True)`
    - `backend/api/routers/parcels.py:76` `"lng": p.centroid_lng,`
    - `backend/api/routers/parcels.py:146` `"lng": p.centroid_lng,`
    - `backend/api/routers/parcels.py:148` `"front_lng": p.front_lng or p.centroid_lng,`
    - `backend/api/routers/parcels.py:168` `ParcelModel.centroid_lng >= min_lng,`
    - `backend/api/routers/parcels.py:169` `ParcelModel.centroid_lng <= max_lng`
    - `backend/api/routers/streetview.py:32` `# 2026-08-31: the columns were renamed to centroid_lat/centroid_lng and this`
    - `backend/api/routers/streetview.py:36` `"lng": r.front_lng or r.centroid_lng,`
    - … 21 more
- **`lat`** — column of parcels -> centroid_lat — `2026-08-31_rename_parcels_lat_to_centroid.sql`: 337 code references (generic name, expect noise)
    - `backend/api/closure_spatial.py:21` `"""Builds a GeoJSON geometry from [lat, lng] points.`
    - `backend/api/closure_spatial.py:36` `lat, lng = usable[0][0], usable[0][1]`
    - `backend/api/closure_spatial.py:37` `return {"type": "Point", "coordinates": [lng, lat]}`
    - `backend/api/models.py:164` `# Renamed from lat/lng 2026-08-31 so the name says what it holds; the API still`
    - `backend/api/models.py:165` `# publishes it as "lat"/"lng".`
    - `backend/api/road_closure_service.py:128` `lat, lng = all_pts[mid][0], all_pts[mid][1]`
    - `backend/api/road_closure_service.py:172` `"coordinates": [lat, lng],`
    - `backend/api/road_closure_service.py:221` `lat, lng = path_pts[mid][0], path_pts[mid][1]`
    - … 329 more
- **`lng`** — column of parcels -> centroid_lng — `2026-08-31_rename_parcels_lat_to_centroid.sql`: 314 code references (generic name, expect noise)
    - `backend/api/closure_spatial.py:21` `"""Builds a GeoJSON geometry from [lat, lng] points.`
    - `backend/api/closure_spatial.py:36` `lat, lng = usable[0][0], usable[0][1]`
    - `backend/api/closure_spatial.py:37` `return {"type": "Point", "coordinates": [lng, lat]}`
    - `backend/api/models.py:164` `# Renamed from lat/lng 2026-08-31 so the name says what it holds; the API still`
    - `backend/api/models.py:165` `# publishes it as "lat"/"lng".`
    - `backend/api/road_closure_service.py:128` `lat, lng = all_pts[mid][0], all_pts[mid][1]`
    - `backend/api/road_closure_service.py:172` `"coordinates": [lat, lng],`
    - `backend/api/road_closure_service.py:221` `lat, lng = path_pts[mid][0], path_pts[mid][1]`
    - … 306 more

**init_db.sql still defines objects a later migration removed or renamed:**
- `zone_id` (column of intersections) appears in init_db.sql; migration `2026-08-22_canonical_zone_for_point.sql` changed it
- `centroid_lat` (column of parcels) appears in init_db.sql; migration `2026-08-31_drop_duplicate_centroid_columns.sql` changed it
- `centroid_lng` (column of parcels) appears in init_db.sql; migration `2026-08-31_drop_duplicate_centroid_columns.sql` changed it
- `lat` (column of parcels -> centroid_lat) appears in init_db.sql; migration `2026-08-31_rename_parcels_lat_to_centroid.sql` changed it
- `lng` (column of parcels -> centroid_lng) appears in init_db.sql; migration `2026-08-31_rename_parcels_lat_to_centroid.sql` changed it

## C. Python modules nothing imports

**2 modules with no importer and no non-doc reference (compose, Dockerfile, shell):**
- `scripts/analyze_historical_tones.py` (last touched 2026-08-05) — mentioned only in docs: docs/walkthroughs/local_stack_and_dsp_calibration_walkthrough.md
- `scripts/inject_test_call.py` (last touched 2026-08-05) — mentioned nowhere

**0 modules with no importer but referenced from compose/Dockerfile/shell (probably entrypoints):**

## D. Scripts, tests, and shell/PS files referenced from nothing

- `backend/scripts/oneshot/fix_tahsis_spelling.py` (last touched 2026-08-31)
- `backend/scripts/oneshot/migrate_streetview_to_parcels.py` (last touched 2026-08-31)
- `backend/scripts/oneshot/normalize_call_type_vocabulary.py` (last touched 2026-08-31)
- `backend/test_device.py` (last touched 2026-07-06)
- `backend/tests/test_address_resolver_matching.py` (last touched 2026-08-30)
- `backend/tests/test_api_routers.py` (last touched 2026-08-31)
- `backend/tests/test_geocoder_orchestrator.py` (last touched 2026-08-30)
- `backend/tests/test_parcels_and_streetview_api.py` (last touched 2026-08-31)
- `backend/tests/test_parser_subaddress.py` (last touched 2026-09-02)
- `backend/tests/test_review_flags.py` (last touched 2026-08-30)
- `backend/tests/test_road_closures_cache.py` (last touched 2026-08-17)
- `backend/tests/test_variables.py` (last touched 2026-06-14)
- `scripts/inject_test_call.py` (last touched 2026-08-05)

## E. Frontend source files nothing imports

- `frontend/src/components/hud/TacticalInfoCard.jsx` (last touched 2026-08-17)

## F. API endpoints: frontend and pipeline calls vs backend routes

Backend routes found: 45. Distinct call paths found in frontend + pipeline: 23.

**Calls with no matching backend route:**
- `/api/audio/` ← backend/scripts/oneshot/backfill_audio_urls.py
- `/api/messaging/v1/sendPush` ← backend/tests/test_variables.py
- `/api/v3/datasets/109ad5fa4cb149ab93a1f9a2de88f34d_0/downloads/data` ← backend/scripts/update_gis_data.py
- `/api/v3/datasets/3df0090289aa4503bd8d234d7ee0c182_0/downloads/data` ← backend/scripts/update_gis_data.py

**Backend routes no frontend or pipeline code calls (may be curl/ops-only; informational):**
- `GET /` — `backend/api/server.py`
- `POST /api/auth/logout` — `backend/api/routers/auth.py`
- `GET /api/auth/me` — `backend/api/routers/auth.py`
- `POST /api/dispatches/{dispatch_id}/feedback` — `backend/api/routers/dispatches.py`
- `GET /api/health` — `backend/api/server.py`
- `GET /api/hydrants/stats` — `backend/api/routers/hydrants.py`
- `GET /api/parcels/bbox` — `backend/api/routers/parcels.py`
- `POST /api/road-closures/sync` — `backend/api/routers/road_closures.py`
- `GET /api/streetview/override` — `backend/api/routers/streetview.py`
- `POST /api/streetview/override` — `backend/api/routers/streetview.py`
- `GET /api/streetview/override/{address}` — `backend/api/routers/streetview.py`
- `GET /api/tiles/{layer}/{z}/{x}/{y}` — `backend/api/routers/tiles.py`
- `GET /api/tiles/{layer}/{z}/{x}/{y}.jpeg` — `backend/api/routers/tiles.py`
- `GET /api/tiles/{layer}/{z}/{x}/{y}.jpg` — `backend/api/routers/tiles.py`
- `GET /api/tiles/{layer}/{z}/{x}/{y}.png` — `backend/api/routers/tiles.py`
- `GET /services/{layer}/tiles/{z}/{x}/{y}.{ext}` — `backend/api/routers/tiles.py`

## G. `/api/...` paths mentioned in docs and skills that match no backend route

- `/api/` ← CLAUDE.md:47
- `/api/Dockerfile` ← docs/punchlist/46b-the-api-image-was-22-gb-because-it-baked-in-10-7-gb-of.md:21
- `/api/audio` ← docs/decomposition_plan.md:234
- `/api/closure_spatial.py` ← docs/decomposition_plan.md:30
- `/api/database.py` ← docs/walkthroughs/local_stack_and_dsp_calibration_walkthrough.md:24
- `/api/directions/json` ← .claude/skills/emergency-routing-engine/SKILL.md:78
- `/api/dispatch` ← docs/dispatch_integration_options.md:272
- `/api/gis/search` ← docs/architecture/database_and_datastores.md:86, docs/gis_endpoints.md:53
- `/api/init_db.sql` ← .claude/skills/local-stack-orchestrator/SKILL.md:55, docs/walkthroughs/local_stack_and_dsp_calibration_walkthrough.md:17
- `/api/js` ← docs/punchlist/35a-google-street-view-panel-still-not-working.md:32
- `/api/models/Systran/faster-whisper-base/revision/main` ← docs/external_calls.md:33, docs/punchlist/53-the-dispatch-agent-makes-a-wan-call-to-huggingface-co-o.md:24, docs/punchlist/53-the-dispatch-agent-makes-a-wan-call-to-huggingface-co-o.md:77
- `/api/road_closure_service.py` ← docs/decomposition_plan.md:25, docs/punchlist/06-verify-first-live-ingest-through-the-new-postgis-path.md:38
- `/api/road_closure_service.py{p}` ← docs/external_calls.md:44
- `/api/routers/audio.py` ← docs/development_freeze_summary.md:86
- `/api/routers/auth.py` ← docs/development_freeze_summary.md:79
- `/api/routers/dispatch.py` ← docs/briefings/valhalla_standard_review_response.md:132, docs/briefings/valhalla_standard_review_response.md:278
- `/api/routers/dispatches.py` ← docs/development_freeze_summary.md:80
- `/api/routers/evaluations.py` ← docs/development_freeze_summary.md:85
- `/api/routers/parcels.py` ← docs/development_freeze_summary.md:81
- `/api/routers/road_closures.py` ← docs/development_freeze_summary.md:84
- `/api/routers/routing.py` ← docs/PROJECT_IDEAS.md:274, docs/development_freeze_summary.md:83
- `/api/routers/streetview.py` ← docs/development_freeze_summary.md:82, docs/punchlist/35a-google-street-view-panel-still-not-working.md:122
- `/api/routers/tiles.py` ← docs/development_freeze_summary.md:87
- `/api/routers/tiles.py{p}` ← docs/external_calls.md:135
- `/api/server.py` ← docs/development_freeze_summary.md:78, docs/walkthroughs/local_stack_and_dsp_calibration_walkthrough.md:23
- `/api/server.py{p}` ← docs/external_calls.md:45

## H. Docker service / container names in docs and skills vs docker-compose.yml

compose services: ['api', 'mosquitto', 'ntfy', 'osrm', 'postgres', 'postgres_data', 'tiles']; container names: ['cfr_api', 'cfr_mosquitto', 'cfr_ntfy', 'cfr_osrm', 'cfr_postgres', 'cfr_tiles']

- `cfr-agent` ← .claude/skills/kiosk-remote-ops/SKILL.md, .claude/skills/stt-mlops-backtest/SKILL.md, docs/agent_onboarding.md, docs/briefings/pa_tone_discriminator.md, docs/briefings/tile_recrawl_runbook.md
- `cfr-audio` ← backend/scripts/pull_audio.ps1
- `cfr-backups` ← .claude/skills/stt-mlops-backtest/SKILL.md, backend/scripts/backup_db.sh, backend/scripts/pull_backups.ps1, docs/agent_onboarding.md, docs/arrival_point_handoff.md
- `cfr-critical` ← backend/scripts/backup_db.sh, backend/scripts/pull_backups.ps1, docs/briefings/database_backup_runbook.md
- `cfr-critical-` ← docs/briefings/database_backup_runbook.md, docs/punchlist/45b-retire-confidence-score-replace-it-with-named-review-fl.md, docs/punchlist/48-one-civic-address-many-parcels-the-import-keeps-whichev.md, docs/qa_handoff_2026-08-30.md
- `cfr-full` ← backend/scripts/backup_db.sh, backend/scripts/pull_backups.ps1, docs/briefings/database_backup_runbook.md
- `cfr-full-` ← docs/arrival_point_handoff.md, docs/punchlist/48-one-civic-address-many-parcels-the-import-keeps-whichev.md
- `cfr-gateway` ← .claude/agents/kiosk-remote-operator.md
- `cfr-kiosk` ← docs/hardware_specification.md
- `cfr-model` ← .claude/skills/stt-mlops-backtest/SKILL.md, backend/scripts/pull_backups.ps1
- `cfr-model-whisper-base-cfr-` ← .claude/skills/stt-mlops-backtest/SKILL.md, docs/briefings/database_backup_runbook.md
- `cfr-orchestrator` ← .claude/agents/kiosk-remote-operator.md
- `cfr_curated` ← docs/punchlist/43a-call-type-vocabulary-carries-locale-variants-as-duplica.md
- `cfr_kiosk` ← docs/emergency_routing_gis_parcels_standard.md
- `cfr_sv_override_` ← .claude/skills/google-imagery-streetview/SKILL.md
- `cfr_user` ← .claude/skills/kiosk-remote-ops/SKILL.md, .claude/skills/local-stack-orchestrator/SKILL.md, docs/agent_onboarding.md
- `cfr_valhalla` ← docs/emergency_routing_gis_parcels_standard.md
- `cfr_whisper_colab_fine_tuning` ← docs/agent_onboarding.md
- `compose svc: -v` ← backend/scripts/backup_db.sh, backend/scripts/pull_backups.ps1, docs/PROJECT_IDEAS.md, docs/briefings/database_backup_runbook.md
- `compose svc: cfr_tiles` ← .claude/skills/local-stack-orchestrator/SKILL.md

## I. Environment variables: code vs .env.example vs compose

**Read by code, declared in no .env.example and not in compose:**
- `ADDRESS_DATA_URL` ← backend/scripts/update_gis_data.py
- `ADMIN_PASSWORD` ← backend/api/routers/auth.py
- `ADMIN_USERNAME` ← backend/api/routers/auth.py
- `AUDIO_DEVICE_ID` ← backend/cfr_dispatch/config/hardware.py
- `BASE_URL` ← frontend/src/components/MapBoard.jsx, frontend/src/components/MapLayers.jsx, frontend/src/components/map/layerIcons.js
- `DB_HOST` ← backend/scripts/oneshot/backfill_routing_metrics.py
- `HF_HUB_DISABLE_SYMLINKS_WARNING` ← backend/cfr_dispatch/__init__.py
- `JOIN_API_KEY` ← backend/tests/test_variables.py
- `MQTT_DISPATCH_TOPIC` ← backend/api/mqtt.py, services/dispatch_notifications/src/notification_service/mqtt_broker.py
- `OSRM_ROUTER_URL` ← backend/scripts/verify_snapping_corpus.py
- `OSRM_URL` ← backend/scripts/verify_snapping_corpus.py
- `PORT` ← backend/api/server.py
- `POSTGRES_PORT` ← backend/scripts/oneshot/backfill_routing_metrics.py
- `TILES_DIR` ← backend/api/routers/tiles.py
- `VITE_API_BASE_URL` ← frontend/src/apiClient.js
- `VITE_DISABLE_WAN_FALLBACK` ← frontend/src/components/MapLayers.jsx
- `VITE_MQTT_BROKER_URL` ← frontend/src/hooks/useMqttListener.js
- `VITE_TILE_BASE_URL` ← frontend/src/apiClient.js
- `WHISPER_CT2_OUT` ← backend/scripts/train_whisper_lora.py
- `ZONES_DATA_URL` ← backend/scripts/update_gis_data.py

**Declared in .env.example or compose, read by no code:**
- `VITE_API_URL` ← frontend/.env.example
- `VITE_NTFY_TOPIC_SECRET` ← frontend/.env.example

## J. SQL files referenced from no doc, script, or compose

- `backend/migrations/2026-08-21_drop_custom_places.sql` (last touched 2026-08-21)
- `backend/migrations/2026-08-21_hydrants_table.sql` (last touched 2026-08-21)
- `backend/migrations/2026-08-21_recover_orphaned_live_calls.sql` (last touched 2026-08-21)
- `backend/migrations/2026-08-21_zones_unit_assignment_and_closure_geom.sql` (last touched 2026-08-21)
- `backend/migrations/2026-08-22_dispatch_sessions.sql` (last touched 2026-08-22)
- `backend/migrations/2026-08-22_intersections_provenance.sql` (last touched 2026-08-22)
- `backend/migrations/2026-08-22_manual_lougheed_mariner_interchange.sql` (last touched 2026-08-22)
- `backend/migrations/2026-08-23_street_centroid_annotation_backfill.sql` (last touched 2026-08-23)
- `backend/migrations/2026-08-23_xstreet_descriptor_vocabulary.sql` (last touched 2026-08-24)
- `backend/migrations/2026-08-28_correct_front_points_to_addressed_street.sql` (last touched 2026-08-28)
- `backend/migrations/2026-08-28_snapshot_parcel_front_points.sql` (last touched 2026-08-28)
- `backend/migrations/2026-08-29_entrance_point_operator_override.sql` (last touched 2026-08-29)
- `backend/migrations/2026-08-30_x_streets_two_variables.sql` (last touched 2026-08-30)
- `backend/migrations/2026-08-31_base_site_rows.sql` (last touched 2026-08-31)
- `backend/migrations/2026-08-31_promote_verified_fields_to_columns.sql` (last touched 2026-08-30)
- `backend/migrations/2026-08-31_rename_parcels_lat_to_centroid.sql` (last touched 2026-08-30)
- `migration_stt_tuning.sql` (last touched 2026-08-21)

`migration_stt_tuning.sql` at repo root, first lines:
-- Migration: Add model_updated and quality_rating to dispatches for STT feedback tracking
ALTER TABLE public.dispatches ADD COLUMN IF NOT EXISTS model_updated BOOLEAN DEFAULT FALSE;
ALTER TABLE public.dispatches ADD COLUMN IF NOT EXISTS quality_rating TEXT DEFAULT 'PENDING';


## K. Punch list: header status vs body status, and index coverage

Header status counts: {'OPEN': 20, 'CLOSED': 45, 'DEFERRED': 2, 'FIXED': 2, 'EXTERNAL': 1, 'SUPERSEDED': 1, '?': 2}

**12 items where the header table and the body status line disagree:**
- `docs/punchlist/10-three-test-modules-have-never-run-in-review.md`: header **CLOSED** / body `⚠️ **Open — unchanged 2026-08-21.** No attempt was made to run them this pass;`
- `docs/punchlist/12-street-centroid-reports-the-requested-address-as-though.md`: header **CLOSED** / body `⚠️ **Open — re-confirmed in the working tree 2026-08-21.** Both overwrites are`
- `docs/punchlist/31-response-type-never-reaches-the-kiosk-every-call-render.md`: header **CLOSED** / body `⚠️ **Open — found 2026-08-23 while investigating #30.** **Confirmed** against`
- `docs/punchlist/35b-near-roads-stopped-being-recorded-on-2026-08-21-phase-2.md`: header **CLOSED** / body `🔴 **Open — live regression, found 2026-08-23.** Reported by the operator`
- `docs/punchlist/38-disp-2026-accf6d-routed-to-the-wrong-street-the-parcel.md`: header **CLOSED** / body `⚠️ **Open — confirmed by spatial query. Likely systemic; see the estimate.**`
- `docs/punchlist/39-review-table-restore-the-verified-value-in-the-row-drop.md`: header **CLOSED** / body `⚠️ **Open — operator wants the earlier behaviour back, with a caveat below.**`
- `docs/punchlist/40-street-basemap-has-no-tiles-above-zoom-18-but-the-repor.md`: header **CLOSED** / body `⚠️ **Open — partially characterized; needs the exact location from the operator.**`
- `docs/punchlist/41-629-cottonwood-ave-is-absent-from-public-parcels.md`: header **CLOSED** / body `⚠️ **Open — confirmed. A data gap, not a search bug.**`
- `docs/punchlist/42-the-roads-import-silently-discards-242-road-segments-in.md`: header **CLOSED** / body `⚠️ **Open — confirmed against source and database. This is the answer to the`
- `docs/punchlist/48-one-civic-address-many-parcels-the-import-keeps-whichev.md`: header **CLOSED** / body `⚠️ **Open — measured 2026-08-28. Ours, not a City data gap.**`
- `docs/punchlist/51a-add-cross-street-1-and-cross-street-2-to-the-review-pan.md`: header **CLOSED** / body `?? **Open — Feature request logged.**`
- `docs/punchlist/58-parcels-whose-street-has-no-road-keep-a-stale-front-po.md`: header **CLOSED** / body `⚠️ **Open — found and measured 2026-08-31 against the running database.**`

**Punch-list files not linked from `docs/debug_and_qa_punchlist.md`:**
- `docs/punchlist/02-intersection-geocoding-hardcoded-port-moody-fallback-di.md`
- `docs/punchlist/03-missing-responding-units-in-replayed-dispatches.md`
- `docs/punchlist/04-remove-satellite-view-from-call-review-panel.md`
- `docs/punchlist/05-audio-player-simplification-in-call-review-panel.md`
- `docs/punchlist/06-verify-first-live-ingest-through-the-new-postgis-path.md`
- `docs/punchlist/07-custom-places-json-coordinates-are-hand-entered-and-som.md`
- `docs/punchlist/08-the-11-test-failures-are-not-environmental-correcting-t.md`
- `docs/punchlist/09-false-intersection-david-ave-panorama-dr.md`
- `docs/punchlist/10-three-test-modules-have-never-run-in-review.md`
- `docs/punchlist/11-private-hydrants-defaulted-to-nfpa-291-class-aa-fabrica.md`
- `docs/punchlist/12-street-centroid-reports-the-requested-address-as-though.md`
- `docs/punchlist/13-public-intersections-needs-the-same-data-integrity-pass.md`
- `docs/punchlist/15-fuzzy-matching-silently-substituted-a-different-interse.md`
- `docs/punchlist/16-street-and-street-is-a-cad-artifact-not-a-self-intersec.md`
- `docs/punchlist/18-96-of-the-whisper-hotword-list-is-silently-discarded.md`
- `docs/punchlist/19b-audio-player-loading-inconsistency-auto-play-removal.md`
- `docs/punchlist/22-next-24h-next-7d-closure-filters-matched-nothing.md`
- `docs/punchlist/23-live-dispatches-lost-their-street-section-fields-on-the.md`
- `docs/punchlist/24-the-kiosk-displayed-an-invented-hydrant-on-every-dispat.md`
- `docs/punchlist/25-a-corrected-re-broadcast-queued-itself-as-a-second-call.md`
- `docs/punchlist/26-the-dispatch-pipelines-info-logging-is-discarded.md`
- `docs/punchlist/27-the-worker-process-is-unsupervised.md`
- `docs/punchlist/28-a-stalled-worker-could-block-the-audio-listener-fixed.md`
- `docs/punchlist/29-phase-1-session-state-lives-only-in-worker-memory.md`
- `docs/punchlist/31-response-type-never-reaches-the-kiosk-every-call-render.md`
- `docs/punchlist/33-legacy-worked-example-placeholders-in-the-review-form-o.md`
- `docs/punchlist/34c-the-phantom-updated-badge.md`
- `docs/punchlist/35b-near-roads-stopped-being-recorded-on-2026-08-21-phase-2.md`
- `docs/punchlist/36-double-click-to-autofill-removed-from-the-review-form.md`
- `docs/punchlist/38-disp-2026-accf6d-routed-to-the-wrong-street-the-parcel.md`
- `docs/punchlist/39-review-table-restore-the-verified-value-in-the-row-drop.md`
- `docs/punchlist/40-street-basemap-has-no-tiles-above-zoom-18-but-the-repor.md`
- `docs/punchlist/41-629-cottonwood-ave-is-absent-from-public-parcels.md`
- `docs/punchlist/42-the-roads-import-silently-discards-242-road-segments-in.md`
- `docs/punchlist/43a-call-type-vocabulary-carries-locale-variants-as-duplica.md`
- `docs/punchlist/43b-the-8-failed-cadastral-tiles-and-what-the-blank-tiles-a.md`
- `docs/punchlist/44b-kiosk-crashed-on-a-live-dispatch-stale-chunk-after-a-fr.md`
- `docs/punchlist/45b-retire-confidence-score-replace-it-with-named-review-fl.md`
- `docs/punchlist/46b-the-api-image-was-22-gb-because-it-baked-in-10-7-gb-of.md`
- `docs/punchlist/47b-basemap-tile-licensing-has-never-been-checked-carto-and.md`
- `docs/punchlist/48-one-civic-address-many-parcels-the-import-keeps-whichev.md`
- `docs/punchlist/50-the-parcel-import-seeds-entrance-lat-lng-with-the-centr.md`
- `docs/punchlist/51a-add-cross-street-1-and-cross-street-2-to-the-review-pan.md`
- `docs/punchlist/52b-an-ampersand-in-the-near-clause-silently-discarded-the.md`
- `docs/punchlist/53-the-dispatch-agent-makes-a-wan-call-to-huggingface-co-o.md`
- `docs/punchlist/58-parcels-whose-street-has-no-road-keep-a-stale-front-po.md`
- `docs/punchlist/59-phase-2-crashed-after-saving-audio-before-recording-its.md`

**Index links to punch-list files that do not exist:**

## L. Docs no other doc links to (orphan documents)

**2 of 144 markdown files have no inbound link from another doc:**
- `docs/briefings/skills_audit_2026-08-30.md` (last touched 2026-08-30, 141 lines)
- `docs/decomposition_plan.md` (last touched 2026-08-31, 356 lines)

## M. Skill and agent names referenced that do not exist

- `skill: e2e-dispatch-testing` ← docs/review_status_handoff.md

## N. Known-eliminated concepts still mentioned (CLAUDE.md §1, memory)

| term | docs | .claude | code | sample |
|:--|--:|--:|--:|:--|
| `shapefile_loader` | 4 | 0 | 0 | `GEMINI.md` |
| `Supabase` | 6 | 0 | 1 | `frontend/src/hooks/useMqttListener.js` |
| `Firebase` | 2 | 0 | 0 | `CLAUDE.md` |
| `config/cloud` | 1 | 0 | 1 | `backend/cfr_dispatch/config/runtime.py` |
| `DashboardHUD` | 3 | 0 | 0 | `docs/PROJECT_IDEAS.md` |
| `hydrants.json` | 7 | 1 | 6 | `backend/api/routers/hydrants.py` |
| `blocks.json` | 3 | 1 | 0 | `.claude/skills/gis-pipeline-sync/SKILL.md` |
| `intersections.json` | 3 | 0 | 3 | `backend/scripts/derive_intersections.py` |
| `zones.json` | 4 | 0 | 6 | `backend/api/closure_spatial.py` |
| `addresses.json` | 2 | 1 | 0 | `.claude/skills/gis-pipeline-sync/SKILL.md` |
| `cfr_dispatch/parser.py` | 2 | 0 | 0 | `backend/README.md` |
| `training mode` | 4 | 0 | 0 | `docs/PROJECT_IDEAS.md` |
| `live_calls` | 1 | 0 | 3 | `backend/migrations/2026-08-21_recover_orphaned_live_calls.sql` |
| `custom_places.json` | 2 | 0 | 2 | `backend/migrations/2026-08-21_drop_custom_places.sql` |
| `confidence_score` | 11 | 2 | 13 | `backend/api/models.py` |
| `access_far_corner` | 3 | 0 | 3 | `backend/migrations/2026-08-29_flag_sites_needing_access_review.sql` |
| `Google Maps` | 5 | 3 | 4 | `docs/architecture/database_map.html` |
| `googleapis` | 2 | 1 | 2 | `frontend/src/components/hud/ActiveDispatchPanel.jsx` |
| `Antigravity` | 2 | 1 | 0 | `.claude/skills/kiosk-ui-audit/SKILL.md` |
| `Gemini` | 6 | 0 | 0 | `GEMINI.md` |

## O. Documentation age

Last-touched month distribution: {'2026-08': 134, '2026-09': 10}

**Oldest 20 docs by last commit:**
- 2026-08-10 `docs/PROJECT_PURPOSE_AND_HISTORY.md`
- 2026-08-11 `docs/privacy.md`
- 2026-08-14 `PROJECT.md`
- 2026-08-20 `.claude/agents/call-review-analyst.md`
- 2026-08-20 `.claude/agents/frontend-kiosk-architect.md`
- 2026-08-20 `.claude/agents/gis-spatial-engineer.md`
- 2026-08-20 `.claude/agents/kiosk-remote-operator.md`
- 2026-08-20 `.claude/agents/pipeline-core-engineer.md`
- 2026-08-20 `.claude/skills/kiosk-remote-ops/SKILL.md`
- 2026-08-20 `.claude/skills/kiosk-ui-audit/SKILL.md`
- 2026-08-21 `.claude/agents/dispatch-qa-engineer.md`
- 2026-08-21 `.claude/agents/performance-metrics-analyst.md`
- 2026-08-21 `README.md`
- 2026-08-21 `docs/development_freeze_summary.md`
- 2026-08-22 `.claude/skills/kiosk-responsive-ergonomics/SKILL.md`
- 2026-08-22 `docs/architecture/unified_map_surface.md`
- 2026-08-23 `docs/briefings/response_type_persistence.md`
- 2026-08-24 `docs/briefings/roads_status_filter.md`
- 2026-08-26 `docs/qa_harnesses.md`
- 2026-08-30 `.claude/skills/emergency-routing-engine/SKILL.md`
```
