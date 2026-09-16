# External Call Register

This file is the register of every code path that reaches outside the LAN, why it is there,
and what it costs when the link is down.

**It is in two parts, because two different things were being counted as one.** A Geofabrik
download that produces a file on disk is not the same kind of risk as a call on the dispatch
path, and reading them off one undifferentiated list made the second look as ordinary as the
first.

> [!IMPORTANT]
> **The test — who makes the call?**
>
> 1. **A process in the running kiosk** (a container in the compose stack, or the browser on
>    the display) → **Part A, the production surface.** CLAUDE.md §1 governs it, and the row
>    must say what a crew sees when the link drops.
> 2. **A person at a desk**, running a script or a command to produce an artifact → **Part B,
>    the bench.** §1 does not govern it. The row must say what artifact it produced and
>    whether it can be fetched again.
>
> The test sorts on **who**, not on where: a script run by hand *on the kiosk* is still the
> bench, because nothing in service waits on it.
>
> **Anything that cannot be sorted by that test goes to the operator, not into a column.**
> Operator ruling 2026-09-16.

Two rules that apply to **both** parts:

* **Operator ruling 2026-08-31: no new external call without explicit permission.** If a
  change adds a network call to any host that is not `localhost`, the kiosk's own Tailscale
  address, or a container on the compose network, stop and ask. If one is found, add a row
  here rather than fixing it silently — the register is the point.
* **Licensing is a separate axis and is not folded into this split.** A bench call can create
  a rights problem exactly as a production one can — punch-list #47b and #82 are both bench
  rows with live rights questions. **Moving a row into Part B does not downgrade its
  licensing risk, and never has.** Rights live in
  [`standards/data_sources.md`](standards/data_sources.md) and the punch list.

**The kiosk has WAN today.** Every Part A call below currently succeeds, which is exactly why
they went unnoticed. Their cost is paid only during an outage — the one time the system
matters most. Nothing here fails in normal testing.

Audit command (re-run after any dependency or component change):

```bash
grep -rnoE "https?://[A-Za-z0-9._-]+" backend/ services/ frontend/src/ tools/ | grep -vE '\.venv|node_modules|__pycache__|localhost|127\.0\.0\.1|100\.95|w3\.org'
```

`tools/` was added to that command on 2026-09-16: the bench scripts living there were being
registered by hand, so the audit could not have found an unregistered one.

---

## Part A — The production surface

**What the kiosk reaches for while it is in service.** CLAUDE.md §1's offline survival
requirement governs this part in full: nothing a crew needs to get to an address or read
critical information may depend on a link. Every row says what a crew sees when it drops.

"Does a crew wait on it?" is **not** the boundary — it is the severity ranking inside this
part. The road closure sync is the proof: nobody waits on it, and it is still production,
because the kiosk makes the call and the map draws its result.

### 1. Removed from the production surface

| Host | Where | Resolution |
|:--|:--|:--|
| `raw.githubusercontent.com`, `cdnjs.cloudflare.com` | `BlockParcelPanel`, `PropertySatellitePanel`, `RouteOverviewPanel` | **Fixed 2026-08-31.** Six Leaflet marker fetches, including the gold *incident* pin. Vendored to local SVG in `frontend/src/assets/`, shared from `components/map/mapIcons.js`. Vite inlines both (419/431 B, under the 4096 B `assetsInlineLimit`) as data URIs, and the shadow now comes from the installed `leaflet` package — so the markers cost **no** request at all. See §3.1. |
| `huggingface.co` | `backend/cfr_dispatch/stt/transcriber.py` | **Fixed 2026-08-31.** `WhisperModel(...)` took `local_files_only` at its `False` default, so every `cfr-agent` cold start called `huggingface.co/api/models/Systran/faster-whisper-base/revision/main` to check the model revision — observed live in `journalctl` at 18:35:09. The weights were already cached (142 MB). Now `local_files_only=True`; an absent cache raises with seeding instructions instead of downloading. |
| `joinjoaomgcd.appspot.com` | `backend/tests/test_variables.py` | **Deleted 2026-09-03.** A 2026-06-14 push-notification probe for the Join service, never registered here, that fired only when `JOIN_API_KEY` was set. It was not a test; removed with the staleness audit (`docs/briefings/staleness_audit_2026-09-03.md`). |

Verified against the installed `faster_whisper` **1.2.1** on the kiosk, not from memory (§7.3):
the parameter is passed straight to `huggingface_hub.snapshot_download`.

---

### 2. Live, unattended, on the dispatch path

#### 2.1 Road closure sync — `open511.gov.bc.ca`, `bc.municipal511.ca`

* `backend/api/road_closure_service.py:89,184,194`
* Started as a daemon thread at `backend/api/server.py:129` → `run_periodic_road_closure_sync()`
* **Wakes every hour**, syncs when local data is older than 24 h (`max_age_seconds=86400`).

Nobody triggers it and nothing surfaces its failure. It is wrapped in `try/except` that logs
and continues, so an outage degrades silently: road closures simply stop updating, and the
map keeps drawing the last known set with no staleness indicator.

**Operator ruling 2026-09-16: this stays in Part A.** Nobody waits on it, and closures are a
bonus rather than something a crew needs in order to reach an address — but the kiosk makes
the call and the map draws its result, so §1 governs it. The candidate boundary "does a crew
ever wait on it?" sorted this row onto the bench, which is why the register sorts on *who
makes the call* instead.

**Still open.** The kiosk cannot tell a crew that what it is showing is two weeks old. The
operator raised a staleness indicator or a warning banner in the closure sidebar on
2026-09-16 as likely needed; he has not picked the element and nothing is built.

**Measured 2026-09-16, before anything is built on it (§7.6):** nothing records the last
*successful contact* with the source. `check_and_sync_if_stale`
(`backend/api/road_closure_service.py:369`) reads `max(RoadClosureModel.updated_at)`, and
`updated_at` is stamped on every row a sync touches (`:308`), so it tracks contact only while
at least one closure comes back. A sync that succeeds and returns **zero** closures leaves
that timestamp untouched, so "no closures in the City" and "we never got through" look
identical — the same §6.1 ambiguity the indicator is meant to remove, one level down. A
truthful indicator needs the sync to record its own last-success time and
`GET /api/road-closures` to return it; today it returns the list alone.

---

### 3. Was live, crew-visible, offline-breaking

#### 3.1 Leaflet marker icons — ✅ RESOLVED 2026-08-31

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

It is also a third-party CDN dependency of exactly the kind the §1 licence caution covers.

**Resolved.** The two coloured pins are now local SVGs in `frontend/src/assets/`, and the
shadow comes from the installed `leaflet` package. All three components import them from
`frontend/src/components/map/mapIcons.js` — one definition where there were three copies.

Vendored as SVG rather than copies of the upstream PNGs: no third-party asset licence to
carry (the §1 licence caution), and vector holds up on a 10-foot display.
Geometry is unchanged — 25×41, anchored at the point `[12, 41]` — so placement did not move.

Imported rather than served from `public/` deliberately: a missing file now fails
`npm run build` instead of 404-ing silently on the kiosk, which is the failure mode this
change exists to remove. Verified in the built bundle: no external host, both pins present
as inline data URIs.

---

### 4. Live, by design, degrades visibly

#### 4.1 Google Street View & Maps — `maps.googleapis.com`, `www.google.com`

| File | Line | Use |
|:--|:--|:--|
| `frontend/src/components/kiosk/StreetViewPanel.jsx` | SDK script, embed iframe, **Static API image** | Maps JS API (interactive, behind Expand), Maps Embed API (fallback), and since 2026-09-06 `maps.googleapis.com/maps/api/streetview` for the compact tile: one JPEG at the saved view per call, no interaction. Added on the operator's word ("I thought the PiP mode was going to be static serve"); needs *Street View Static API* on the key's API restrictions, else the tile falls back to the interactive view and says so. |
| `frontend/src/components/hud/ActiveDispatchPanel.jsx` | 21, 158 | static Street View thumbnail, pano link |
| `frontend/src/components/hud/LeftSidebar.jsx` | 324 | external directions link |

Street View is inherently an online feature; it cannot be made offline and is not claimed to
be. Distinct from §3 because the panel is *about* the remote imagery — when it fails, the
absence is legible to the crew rather than disguised as a working map.

See the **`google-imagery-streetview`** skill for the caching and persistence workflow.

**Not a defect. Recorded so the register is complete**, and so nobody "fixes" §3 by copying
this pattern.

---

## Part B — The bench

**What a person at a desk reaches for to produce an artifact.** None of it is on the
dispatch path; all of it ships its output to the kiosk's disk, and all of it can be repeated
by hand. CLAUDE.md §1 does not govern this part — the 2026-08-31 permission ruling and the
licensing axis above do.

### 5. Maintenance scripts and one-off pulls

Deliberately online, run by hand, never on the dispatch path. Correct as they are.

| Script | Hosts |
|:--|:--|
| `backend/scripts/download_gis_data.py`, `update_gis_data.py` | `opendata.arcgis.com`, `geodata.coquitlam.ca` |
| `backend/scripts/sync_hydrants.py` | City ArcGIS endpoint |
| One-off pull of the City's live address layer, 2026-09-13, operator's permission the same day (no script; run by hand from the dev laptop) | `geodata.coquitlam.ca` — `DynamicServices/AddressSearch/MapServer/1/query` (`Parcel_Addresses`), paged 1,000 records at a time, GeoJSON in EPSG:4326, saved to `backend/data/staging/` on the kiosk for comparison with `public.parcels`. Nothing imported. Context: [`standards/data_sources.md`](standards/data_sources.md) §3. |
| One-off pull of the City's **Buildings** layer, 2026-09-13, operator's permission the same day (*"Pull whatever you think we should from the city, and world geocoding to figure out if we need to change sources"*; no script, run by hand from the dev laptop) | `geodata.coquitlam.ca` — `DynamicServices/Cadastral/MapServer/17/query` (service layer 17, `Buildings`, polygons), `where=OBJECTID > n` in `OBJECTID` order, 1,000 records a request, all fields, GeoJSON in EPSG:4326, one-second pause between requests: 34 requests, 33,766 features, equal to the service's own count. Saved to `backend/data/staging/Buildings_2026-09-13/` on the kiosk. Nothing imported. |
| One-off pull of the City's **engineering Address Labels** layer, same day, same permission, same method | `geodata.coquitlam.ca` — `EPW/EPW_Service_Connections/MapServer/1/query` (service layer 1, `Address Labels`, points; fields `OBJECTID, SHAPE, LABEL`): 30 requests, 29,111 features, equal to the service's count. Saved to `backend/data/staging/EPW_Address_Labels_2026-09-13/` on the kiosk. Nothing imported. |
| The other one-off requests of the 2026-09-13 address-source evaluation, same day, each with the operator's permission in the conversation (no script, dev laptop) | `geodata.coquitlam.ca`: the service directory (`/arcgis/rest/services?f=json`, then one `?f=json` read per folder and per map service, to find layers by name); the layer descriptions of `DynamicServices/Cadastral/MapServer/1` and `/17`, `DynamicServices/AddressSearch/MapServer` and `/1`, `EPW/EPW_Service_Connections/MapServer/1` and `EPW/EPW_Annotation/MapServer/2`, with a count-only query on each; two `Parcel_Addresses` lookups (`2973` and `2963 Glen`); 23 small range queries isolating `Parcel_Addresses` record 39,699, which fails as GeoJSON, and that record as Esri JSON; one envelope query on `EPW/EPW_Annotation/MapServer/2` around 2963 Glen Dr; and 131 address lookups on the City's own locator, `Geocode/CoquitlamLocator/GeocodeServer/findAddressCandidates`. `opendata.arcgis.com/api/v3/datasets` for the portal metadata of `Coquitlam::address-labels-1` and `Coquitlam::cadastral-1`. Later the same day, with the operator's permission again: one read of `DynamicServices/Cadastral/MapServer?f=json` (the layer list, no data), recorded in [`standards/data_sources.md`](standards/data_sources.md) §1. **`geocode.arcgis.com`** — Esri's World Geocoder, `World/GeocodeServer/findAddressCandidates`, 130 address lookups without a token, **Esri's terms not read**; results kept in scratch files only, never in the system. Findings: [`standards/data_sources.md`](standards/data_sources.md) §3, punch-list #82. |
| `backend/scripts/crawl_cadastral_tiles.py`, `compile_mbtiles.py` | `geodata.coquitlam.ca`: the City's Cadastral MapServer `export` (road labels, address labels, parcels) for the first, the `CachedServices/Imagery_2025` tile cache for the second, both held to ~20 requests a second. |
| `tools/extract_training_data.py`, `backtest_regression.py`, `clean_old_dispatches.py` | local API only |
| `tools/train_whisper_lora.py` | `huggingface.co` — `transformers` loading `openai/whisper-base` sends `HEAD` revision checks for the cached files at the start of a run (seen in `/tmp/round2.log` 2026-09-05 21:38, three requests, all answered from the cache afterwards). Training only, never the agent. **Fixed 2026-09-06** on the operator's word: the script sets `HF_HUB_OFFLINE=1` before importing `transformers`, verified on the kiosk (all four loads from the cache, no request); seed a new machine once with `HF_HUB_OFFLINE=0`. |
| The OSM extract itself (by hand on the kiosk, 2026-09-09, operator ruling "fill the scroll area with our vector maps") | `download.geofabrik.de` for `british-columbia-latest.osm.pbf` (about 600 MB, MD5 checked against Geofabrik's published sum), clipped on the kiosk with osmium-tool in a container (`stefda/osmium-tool`, pulled from Docker Hub) to `backend/data/osrm/coquitlam_region.osm.pbf`, the box `-123.31,48.99,-122.45,49.52` that covers the workstation's scroll limits (`OPERATIONAL_BOUNDS`) with a margin. The previous file was a BBBike city extract whose service takes a web form and an email, which cannot be scripted. One deliberate event, shared with the routing stream (both briefs). `vancouver.osm.pbf`, the extract this replaced, stays on disk because BBBike's service takes a web form and an email and cannot be re-fetched by script; no prebuilt rollback graph is kept, and `apparatus.osrm.*` and `vancouver.osrm.*` were deleted from the kiosk on 2026-09-15 (operator ruling, `dd70dcc9`). |
| `backend/scripts/build_vector_basemap.sh` (the Planetiler vector-tile build; run by hand on the kiosk) | `ghcr.io` for the image, then with `--download`: `osmdata.openstreetmap.de` (water polygons, 929 MB), `naturalearthdata.com` (434 MB), `github.com` (lake centrelines, 81 MB, and the Noto Sans glyph release, 62 MB). **Once**: the sources are kept in `backend/data/planetiler_sources/` on the kiosk and every rebuild reads them from disk; the OSM extract itself is the one routing already holds. Never on the dispatch path; the kiosk serves the finished archive offline like every other layer. Licences in `standards/basemap/README.md`. |

#### Can it be fetched again?

The bench's failure mode is not an outage — it is a source that will not hand the artifact
over a second time. Everything above can be re-run as it stands except where noted:

| | |
|:--|:--|
| `vancouver.osm.pbf` | **No, not by script.** BBBike's extract service takes a web form and an email. It is kept on the kiosk for that reason: it is the seed for any pre-penalty OSRM rebuild, and nothing can re-fetch it unattended. |
| The City's `Imagery_2025` tile cache | Available, but **availability is not the constraint** — the rights question is punch-list #47b, unresolved. Do not treat "we can crawl it again" as permission to. |
| `geocode.arcgis.com` (Esri World Geocoder) | Reachable, **terms never read** (punch-list #82). Results were kept in scratch files and never entered the system. Not to be re-run without the operator. |
| Planetiler's sources (water polygons, Natural Earth, lake centrelines, glyphs) | Yes, about 1.5 GB. Kept in `backend/data/planetiler_sources/` on the kiosk so a rebuild needs no link at all. |
| The City's ArcGIS layers | Yes. The staged copies are dated snapshots; which copy we hold and when it was taken is [`standards/data_sources.md`](standards/data_sources.md), not this file. |


---

## Neither part — not a call at all

Recorded here because an audit turns them up and someone has to decide the same thing twice
otherwise.

### 6. Verified local — not external despite matching a naive grep

Checked so the next audit does not re-open them:

| Site | Actually |
|:--|:--|
| `backend/cfr_dispatch/stt/bias_prompt.py:74` | `LOCAL_API_URL`, default `http://localhost:8000` |
| `backend/api/routers/tiles.py:40,59` | `TILE_SERVER_URL` → the `cfr_tiles` container |
| `backend/main.py:25` | `http://localhost:8000` self-check |
| `backend/cfr_dispatch/health_watchdog.py:40` | configurable target — **and the module is never invoked in production** |
| `frontend/src/components/DriverStationSetup.jsx` | `ntfy.sh` appears in a historical comment only; the server is local (punch-list #60) |
| `backend/dispatch.log.2026-06-*` | `supabase.co` URLs are in **rotated historical logs**, not code. Supabase is gone. |
| `tools/build_basemap_style.py:191` | `http://tiles/...` and `http://app/...` are **not fetched**. `tiles` is the compose service; both strings only fill the style's placeholders so a copy can be handed to the MapLibre style validator, which is then deleted. Turned up by the `tools/` pass added 2026-09-16. |

---

### 7. Orphaned credential

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

<!-- audit-ok: frontend/src/components/kiosk/BlockParcelPanel.jsx -- named as history; the kiosk's cadastral tile was removed 2026-09-08 -->
