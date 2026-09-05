# `backend/scripts/`

Every script in this directory, grouped by **when you would run it** — which is the thing the
old version of this file could not tell you. It documented 8 of 51 scripts, and one of the 8
(`create_adaptation_resources.py`) had been deleted and described loading vocabulary into
Google Cloud Speech-to-Text, a dependency CLAUDE.md §1 forbids.

> [!IMPORTANT]
> **This file is checked, not trusted.** `python tools/audit_skill_references.py
> --scripts` fails if a script here has no row below, or if a row names a script that does not
> exist. A folder tells you where a file is; only a check tells you the description is still
> true. That is the same lesson as the archived skills copy and the routing standard.

**This directory is what a person runs to *operate* the system**: backups, municipal data loads,
tile archives, sound-card checks. Everything a developer runs to build, test, measure, train or
audit it lives in [`tools/`](../../tools/README.md) since 2026-09-04, including the one-shot
data fixes in `tools/oneshot/`.

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

## Audio and DSP

Run when investigating the capture pipeline or calibrating hardware.

| Script | Purpose |
|:--|:--|
| `calibrate_audio_interactive.py` | Interactive input-device selection and noise-floor calibration. |
| `debug_audio.py` | Lists PortAudio devices and properties, to find device IDs. |
| `record_test.py` | Records a sample from the configured input for inspection. |
