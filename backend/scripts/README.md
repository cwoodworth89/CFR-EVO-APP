# `backend/scripts/`

Every script in this directory, grouped by **when you would run it** — which is the thing the
old version of this file could not tell you. It documented 8 of 51 scripts, and one of the 8
(`create_adaptation_resources.py`) had been deleted and described loading vocabulary into
Google Cloud Speech-to-Text, a dependency CLAUDE.md §1 forbids.

> [!IMPORTANT]
> **This file is checked, not trusted.** `python backend/scripts/audit_skill_references.py
> --scripts` fails if a script here has no row below, or if a row names a script that does not
> exist. A folder tells you where a file is; only a check tells you the description is still
> true. That is the same lesson as the archived skills copy and the routing standard.

**Already-run scripts live in [`oneshot/`](oneshot/).** They ran once against a specific
problem and will not run again. They are kept for provenance, not for use.

---

## Scheduled and routine

Run on a timer or as a standing procedure.

| Script | Purpose |
|:--|:--|
| `backup_db.sh` | Scheduled PostgreSQL backup. **Pinned in the kiosk crontab at an absolute path (`15 3 * * *`) — moving or renaming it silently stops all backups.** Runbook: `docs/briefings/database_backup_runbook.md`. |
| `pull_backups.ps1` | Copies backup archives from the kiosk to the laptop. Run on the developer machine. |
| `pull_audio.ps1` | Copies the dispatch audio corpus from the kiosk to the laptop. The audio and the `verified_*` columns are one dataset in two stores. |
| `update_gis_data.py` | Monthly municipal data refresh from Coquitlam Open Data. Checks a timestamp file so it will not re-run within the same week. |

## Municipal data ingest

Run when City data is refreshed. Order matters: roads before parcels, parcels before intersections.

| Script | Purpose |
|:--|:--|
| `download_gis_data.py` | Downloads raw layers from the Coquitlam ArcGIS REST API. |
| `fix_shapefiles.py` | Repairs geometry winding order after download. |
| `read_dbf.py` | Streaming DBF reader — audits `Addresses.dbf` without GDAL or fiona. |
| `import_gis_data.py` | Roads, intersections, zones, city boundary and vocabulary into PostGIS. |
| `import_parcels.py` | All 69,708 `Addresses.shp` records, plus the derived `base_site` rows (#48) and road-facing front points. |
| `sync_hydrants.py` | Municipal hydrant inventory into `public.hydrants`, NFPA 291 classified. |
| `derive_intersections.py` | Rebuilds `public.intersections` from road centreline geometry. |

## Tiles

The offline basemap pipeline. See the `mbtiles-tile-server` skill before touching an archive.

| Script | Purpose |
|:--|:--|
| `compile_mbtiles.py` | Builds the MBTiles archives served by `cfr_tiles`. |
| `crawl_cadastral_tiles.py` | Pre-caches the City cadastral overlay. |
| `finalize_mbtiles.py` | Checkpoints WAL and sets `journal_mode = DELETE`. **Required** — the tile volume is mounted read-only and will not open a WAL archive. |
| `calc_tile_counts.py` | Estimates tile counts for a bounding box and zoom range before a crawl. |
| `export_tile_coverage.py` | Regenerates `coquitlam_tile_coverage.geojson`. |
| `inspect_loose_tiles.py` | Inspects loose tile directories under `backend/data/tiles/`. |
| `verify_mbtiles_endpoints.py` | Checks sample tile requests against `mbtileserver` on 8081. |
| `verify_ortho_coverage.py` | Diffs `ortho.mbtiles` against the expected tile grid and classifies every missing tile as outside the City's published imagery extent (expected — our polygon carries a 1 km mutual-aid buffer) or inside it (a real gap worth re-crawling). A bare failure count cannot tell scattered network noise from a systematic hole over one neighbourhood. |
| `test_mbtiles_setup.py` | Builds a minimal archive and verifies the server reads it. **Not a pytest test** despite the name. |
| `test_tile_sources.py` | Probes tile source URLs for availability. **Not a pytest test** despite the name. |

## Audio and DSP

Run when investigating the capture pipeline or calibrating hardware.

| Script | Purpose |
|:--|:--|
| `calibrate_audio_interactive.py` | Interactive input-device selection and noise-floor calibration. |
| `debug_audio.py` | Lists PortAudio devices and properties, to find device IDs. |
| `analyze_wav.py` | Frequency and level analysis of a WAV file at 50 ms blocks. |
| `record_test.py` | Records a sample from the configured input for inspection. |
| `live_monitor.py` | Live RMS monitor on the capture device. |
| `fingerprint_source.py` | Extracts dominant tone frequencies with sub-Hz precision, for building tone profiles. |
| `backfill_tone_spectra.py` | Reconstructs tone peak data from archived recordings. Re-runnable as the archive grows. |

## QA harnesses and measurement

Produce numbers. None of them modify operational data.

| Script | Purpose |
|:--|:--|
| `backtest_parser.py` | Production parser against the sequential destructive parser, on ground truth. |
| `backtest_parser_corpus.py` | Replays verified dispatches through the current parser, scoring each field. |
| `backtest_regression.py` | WER / Levenshtein regression for STT output. |
| `backtest_round_comparison.py` | Scores cross-round disagreement as a warning signal. |
| `trace_geocode_corpus.py` | Scores the geocoder against the human-verified corpus. |
| `verify_snapping_corpus.py` | Parcel arrival-point benchmark: boundary-to-arrival distance and OSRM ETA. |
| `audit_skill_references.py` | Finds identifiers a `SKILL.md` names that exist nowhere in the code. `--scripts` checks this README. |
| `export_complex_sites_for_review.sql` | Sites where a crew arriving at the computed point still has property to search — the `#49` review queue. |

## STT / MLOps

| Script | Purpose |
|:--|:--|
| `extract_training_data.py` | Builds the training set from HITL-verified dispatches; adds verified incident types to `public.vocabulary`. |
| `check_verified_transcripts.py` | Spell- and street-checks the operator's verified transcripts against `public.roads`, `public.vocabulary`, `public.parcels` and the corpus before they become training labels; exits 1 on blocking issues. Run by `prepare_training_clips.py`. |
| `prepare_training_clips.py` | Builds the round-1 clip dataset for fine-tuning: measures speech onset per call, cuts at the round boundary, drops rounds over Whisper's 30s window. |
| `train_whisper_lora.py` | LoRA fine-tune of the local Whisper model, on the round-1 clips. |
| `eval_round1_holdout.py` | Scores models on the held-out round-1 clips the fine-tune never saw; prints stock `base` against the fine-tuned model. |

## Ad-hoc inspection

Reach for these while debugging something specific.

| Script | Purpose |
|:--|:--|
| `inspect_dispatch.py` | Dumps one dispatch record by id. |
| `clean_old_dispatches.py` | Lists old dispatches for review. **Deletion requires manual confirmation.** |
| `update_streetview.py` | Refreshes Street View heading/pitch/fov for parcels. |
| `test_dual_push.py` | Exercises the MQTT and Ntfy push paths. **Not a pytest test** despite the name. |
