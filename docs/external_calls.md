# External Call Register

**CLAUDE.md §1 requires total offline survival: STT, geocoding, routing, spatial queries,
tile serving and WebSocket dispatch must all work with no internet.**

This file is the register of every code path that reaches outside the LAN, why it is there,
and what a crew sees when the link is down.

> [!IMPORTANT]
> **Operator ruling 2026-08-31: no new external call without explicit permission.**
> If a change adds a network call to any host that is not `localhost`, the kiosk's own
> Tailscale address, or a container on the compose network, stop and ask. If one is found,
> add a row here rather than fixing it silently — the register is the point.

**The kiosk has WAN today.** Every call below currently succeeds, which is exactly why they
went unnoticed. Their cost is paid only during an outage — the one time the system matters
most. Nothing here fails in normal testing.

Audit command (re-run after any dependency or component change):

```bash
grep -rnoE "https?://[A-Za-z0-9._-]+" backend/ services/ frontend/src/ \
  | grep -vE '\.venv|node_modules|__pycache__|localhost|127\.0\.0\.1|100\.95|w3\.org'
```

---

## 1. Removed

| Host | Where | Resolution |
|:--|:--|:--|
| `raw.githubusercontent.com`, `cdnjs.cloudflare.com` | `BlockParcelPanel`, `PropertySatellitePanel`, `RouteOverviewPanel` | **Fixed 2026-08-31.** Six Leaflet marker fetches, including the gold *incident* pin. Vendored to local SVG in `frontend/src/assets/`, shared from `components/map/mapIcons.js`. Vite inlines both (419/431 B, under the 4096 B `assetsInlineLimit`) as data URIs, and the shadow now comes from the installed `leaflet` package — so the markers cost **no** request at all. See §3.1. |
| `huggingface.co` | `backend/cfr_dispatch/stt/transcriber.py` | **Fixed 2026-08-31.** `WhisperModel(...)` took `local_files_only` at its `False` default, so every `cfr-agent` cold start called `huggingface.co/api/models/Systran/faster-whisper-base/revision/main` to check the model revision — observed live in `journalctl` at 18:35:09. The weights were already cached (142 MB). Now `local_files_only=True`; an absent cache raises with seeding instructions instead of downloading. |
| `joinjoaomgcd.appspot.com` | `backend/tests/test_variables.py` | **Deleted 2026-09-03.** A 2026-06-14 push-notification probe for the Join service, never registered here, that fired only when `JOIN_API_KEY` was set. It was not a test; removed with the staleness audit (`docs/briefings/staleness_audit_2026-09-03.md`). |

Verified against the installed `faster_whisper` **1.2.1** on the kiosk, not from memory (§7.3):
the parameter is passed straight to `huggingface_hub.snapshot_download`.

---

## 2. Live, unattended, on the dispatch path

### 2.1 Road closure sync — `open511.gov.bc.ca`, `bc.municipal511.ca`

* `backend/api/road_closure_service.py:89,184,194`
* Started as a daemon thread at `backend/api/server.py:129` → `run_periodic_road_closure_sync()`
* **Wakes every hour**, syncs when local data is older than 24 h (`max_age_seconds=86400`).

Nobody triggers it and nothing surfaces its failure. It is wrapped in `try/except` that logs
and continues, so an outage degrades silently: road closures simply stop updating, and the
map keeps drawing the last known set with no staleness indicator.

**Open question for the operator:** is a stale-but-present closure list better or worse than a
visibly empty one? This is §6.1 territory — right now the kiosk cannot tell a crew that what
it is showing is two weeks old. Not actioned.

---

## 3. Was live, crew-visible, offline-breaking

### 3.1 Leaflet marker icons — ✅ RESOLVED 2026-08-31

| File | Line | Asset |
|:--|:--|:--|
| `frontend/src/components/kiosk/BlockParcelPanel.jsx` | 33, 34 | gold target icon + shadow |
| `frontend/src/components/kiosk/PropertySatellitePanel.jsx` | 52, 53 | gold target icon + shadow |
| `frontend/src/components/kiosk/RouteOverviewPanel.jsx` | 66, 67, 76, 77 | gold **and** blue icons + shadow |

The gold marker is **the incident location**. The blue markers are the alternate address
candidates from §5 ambiguity handling.

With no WAN these fetches fail and Leaflet renders a broken or absent image. The map still
draws, the route still draws, and the pin marking where the crew is going does not — with no
error, because a failed `<img>` is not a JavaScript error. This is the §6.1 failure mode in
its most literal form: the display looks fine and the critical element is missing.

It is also a third-party CDN dependency of exactly the kind the §1 Carto caution covers.

**Resolved.** The two coloured pins are now local SVGs in `frontend/src/assets/`, and the
shadow comes from the installed `leaflet` package. All three components import them from
`frontend/src/components/map/mapIcons.js` — one definition where there were three copies.

Vendored as SVG rather than copies of the upstream PNGs: no third-party asset licence to
carry (the §1 Carto caution is the same problem), and vector holds up on a 10-foot display.
Geometry is unchanged — 25×41, anchored at the point `[12, 41]` — so placement did not move.

Imported rather than served from `public/` deliberately: a missing file now fails
`npm run build` instead of 404-ing silently on the kiosk, which is the failure mode this
change exists to remove. Verified in the built bundle: no external host, both pins present
as inline data URIs.

---

## 4. Live, by design, degrades visibly

### 4.1 Google Street View & Maps — `maps.googleapis.com`, `www.google.com`

| File | Line | Use |
|:--|:--|:--|
| `frontend/src/components/kiosk/StreetViewPanel.jsx` | 325, 461, 462 | Maps JS API, Street View embed |
| `frontend/src/components/hud/ActiveDispatchPanel.jsx` | 21, 158 | static Street View thumbnail, pano link |
| `frontend/src/components/hud/LeftSidebar.jsx` | 324 | external directions link |

Street View is inherently an online feature; it cannot be made offline and is not claimed to
be. Distinct from §3 because the panel is *about* the remote imagery — when it fails, the
absence is legible to the crew rather than disguised as a working map.

See the **`google-imagery-streetview`** skill for the caching and persistence workflow.

**Not a defect. Recorded so the register is complete**, and so nobody "fixes" §3 by copying
this pattern.

---

## 5. Operator-run maintenance scripts

Deliberately online, run by hand on a networked machine, never on the dispatch path. Correct
as they are.

| Script | Hosts |
|:--|:--|
| `backend/scripts/download_gis_data.py`, `update_gis_data.py` | `opendata.arcgis.com`, `geodata.coquitlam.ca` |
| `backend/scripts/sync_hydrants.py` | City ArcGIS endpoint |
| `backend/scripts/crawl_cadastral_tiles.py`, `compile_mbtiles.py` | `basemaps.cartocdn.com` — see the §1 licence caution before touching |
| `tools/extract_training_data.py`, `backtest_regression.py`, `clean_old_dispatches.py` | local API only |

---

## 6. Verified local — not external despite matching a naive grep

Checked so the next audit does not re-open them:

| Site | Actually |
|:--|:--|
| `backend/cfr_dispatch/stt/bias_prompt.py:74` | `LOCAL_API_URL`, default `http://localhost:8000` |
| `backend/api/routers/tiles.py:40,59` | `TILE_SERVER_URL` → the `cfr_tiles` container |
| `backend/main.py:25` | `http://localhost:8000` self-check |
| `backend/cfr_dispatch/health_watchdog.py:40` | configurable target — **and the module is never invoked in production** |
| `frontend/src/components/DriverStationSetup.jsx` | `ntfy.sh` appears in a historical comment only; the server is local (punch-list #60) |
| `backend/dispatch.log.2026-06-*` | `supabase.co` URLs are in **rotated historical logs**, not code. Supabase is gone. |

---

## 7. Orphaned credential

`backend/.env:13` sets `GOOGLE_APPLICATION_CREDENTIALS=backend/cfr-dispatch-mapping-69537f853073.json`
— a Google Cloud **service-account key including a live `private_key`**, for project
`cfr-dispatch-mapping`.

**No code reads it.** It is a leftover of the removed cloud-STT path.

* Not in git: never committed, ignored by `.gitignore:209` (`backend/*.json`). Verified.
* The key is still valid at Google until revoked. Revoking it is a console action, outside
  this repo — same category as the Supabase keys retired the same day.

---

## Why this register exists

The Whisper call had been on the boot path of an offline-only dispatch system for as long as
faster-whisper had been in it, through a review that produced this project's §1. It survived
because it is invisible while the link is up, and because nothing in the repo listed what was
supposed to be reachable.

An unknown dependency is tracked the same way an unknown value is (§6.1, §7.5): **visibly.**

<!-- audit-ok: backend/tests/test_variables.py -- deleted 2026-09-03; the row in section 1 records the removal -->
