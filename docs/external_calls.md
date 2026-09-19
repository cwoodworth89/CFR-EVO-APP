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

* `backend/api/road_closure_service.py` (`DRIVEBC_EVENTS_URL`, `MUNICIPAL511_PUBLISHERS`, `_ingest_road_closures`)
* Started as a daemon thread at `backend/api/server.py:129` → `run_periodic_road_closure_sync()`
* **Wakes every hour**, syncs when local data is older than 24 h (`max_age_seconds=86400`).
* **How each feed is asked, since 2026-09-16 (punch-list #92, operator: "why not ask DriveBC what do you have in Coquitlam?"):**
  * **DriveBC:** `api.open511.gov.bc.ca/events?format=json&status=ACTIVE&bbox=<min lon>,<min lat>,<max lon>,<max lat>`,
    the box being `public.city_boundary` grown 100 m, computed from the table at every sync
    (`closure_spatial.closure_city_bbox`), following the response's `pagination.next_url`. No
    `limit`. It replaced `?format=json&limit=100`, which returned 100 province-wide events and
    missed the in-city one. Measured with the new form: 3 events, 5 KB, 0.22 s. If the box
    cannot be computed, DriveBC is not asked and the attempt is FAILED (#89).
  * **Municipal 511:** unchanged requests (the Coquitlam page, then every data file it lists:
    14 on 2026-09-16, holding every Transnomis client). The page is fetched first; **the data
    files are then fetched concurrently**, up to `MUNICIPAL511_FETCH_WORKERS` = 13 at once, each
    with the same 5 s timeout, and processed in the page's order (operator 2026-09-16: "We can
    parallel if it's easy"). One failed file still marks the feed not reached. Measured on the
    kiosk, same moment, same 15 requests: files 2.31 s wall concurrently against 9.17 s summed. The feed offers no area filter, so the
    sync keeps only issues whose `Source` is `City of Coquitlam` before any spatial query.
    `BC MOTI Gateway` is excluded: its issues copy DriveBC (272 of 303 descriptions identical
    to active DriveBC events), and DriveBC is now asked for the area directly. Operator ruling
    2026-09-16.

Nobody triggers it and nothing surfaces its failure. It is wrapped in `try/except` that logs
and continues, so an outage degrades silently: road closures simply stop updating, and the
map keeps drawing the last known set with no staleness indicator.

**Licensing, 2026-09-16:** DriveBC's feed is Open Government Licence – British Columbia (BC's OpenAPI spec, `license`). **Municipal 511 (`bc.municipal511.ca`, Transnomis) states no data licence** — its site carries Terms of Use for permit applicants and nothing for feed consumers, and publishes no API documentation. As far as any reachable document says, this production call consumes an unlicensed feed. Recorded on the licensing axis, not folded into the split; the operator decides whether it is a punch-list item.

**Operator ruling 2026-09-16: this stays in Part A.** Nobody waits on it, and closures are a
bonus rather than something a crew needs in order to reach an address — but the kiosk makes
the call and the map draws its result, so §1 governs it. The candidate boundary "does a crew
ever wait on it?" sorted this row onto the bench, which is why the register sorts on *who
makes the call* instead.

**Operator ruling 2026-09-16 — the flag is the failed sync, not the age of the data.** Raise
a warning when the previous attempt to sync failed; clear it the next time one succeeds.

This is deliberately not a staleness indicator, and it is the better answer for a reason worth
keeping: **it makes an empty closure list readable.** No flag and no closures means the source
was reached and the City has none; a flag and no closures means we could not reach it. That is
the §6.1 ambiguity closed, with no derived value and no threshold to tune.

The measurement that ruled out the other approach, kept because it is what a staleness
indicator would have been built on: `check_and_sync_if_stale`
(`backend/api/road_closure_service.py:369`) reads `max(RoadClosureModel.updated_at)`, and
`updated_at` is stamped on every row a sync touches (`:308`), so it tracks contact only while
at least one closure comes back. A sync that succeeds and returns **zero** closures leaves
that timestamp untouched — so age alone cannot tell the two cases apart.

**Backend built 2026-09-16 (`ad339fec`), not yet deployed.** The sync records its outcome in
`public.road_closure_sync_status` — one row, three states — and `GET /api/road-closures`
returns it beside the list. The measurement above turned out to be only half of it: neither
feed's failure raises, each `urlopen` is caught and logged, so an outage looks byte-for-byte
like a quiet day and reachability had to be recorded per feed rather than inferred. The flag
is **a banner in the closure sidebar, shown only while the last attempt failed** (operator,
2026-09-16); the frontend half is in progress and both deploy together. Punch-list #89.

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
| `frontend/src/components/kiosk/StreetViewPanel.jsx` | SDK script, embed iframe, **Static API image**, **Static API metadata** | Maps JS API (interactive, behind Expand), Maps Embed API (fallback), and since 2026-09-06 `maps.googleapis.com/maps/api/streetview` for the compact tile: one JPEG at the saved view per call, no interaction. Added on the operator's word ("I thought the PiP mode was going to be static serve"); needs *Street View Static API* on the key's API restrictions, else the tile falls back to the interactive view and says so. **Since 2026-09-16 (punch list #93, operator: "Let's get A going because it's a crew facing issue"):** `maps.googleapis.com/maps/api/streetview/metadata?location=<call point>&radius=100&source=outdoor&key=<key>` — **one request per call that has no saved view**, made after the saved-view lookup answers, before the image. Its `location` and `pano_id` place the camera at the panorama Google found and aim it at the lot centre (`target.rings`, else the call's point); the image is then requested by `pano=`. Same key and same API restriction as the image. **Cost: none** — Google, *Street View Image Metadata*: "Street View Static API metadata requests are available at no charge. No quota is consumed when you request metadata" (pricing list: SKU *Street View Metadata*, free usage cap *Unlimited*; both read 2026-09-16). The endpoint answers browsers (`Access-Control-Allow-Origin: *`, checked 2026-09-16). **When it drops:** offline, the tile shows "Street View needs the internet" and no request is made; `ZERO_RESULTS`, the tile shows "No Street View available"; any other answer (`REQUEST_DENIED`, `OVER_QUERY_LIMIT`, `UNKNOWN_ERROR`, a failed fetch), the tile falls back to the location request aimed from the call's point to the lot centre, and the browser console logs an ERROR with the status; with no direction to face at all (no parcel outline and no panorama position), the tile says "Street View not aimed" instead of facing north. A saved view makes no metadata request while its stored `pano_id` still serves an image, and is never re-aimed. **Since 2026-09-19** (Google: "Panoramas may change IDs over time, so don't persist this ID"): if a saved view's image fails, the tile makes **one** metadata request by the saved camera position (`location=<streetview_lat>,<streetview_lng>&radius=50&source=outdoor`, the same endpoint and key) and, if a different panorama is there now, requests the image by that id with the saved heading, pitch and fov unchanged. The stored `pano_id` is a hint, tried first because it costs nothing extra; the request budget changes only in that re-issued case, by one free metadata call. When the retry finds the same id or cannot answer, the tile falls back to the interactive view as before; `ZERO_RESULTS` shows "No Street View available". The database row is not rewritten; saving again from Expand records the new id. Logic: `resolveStreetView` in `frontend/src/utils/streetViewGeometry.js`. |
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
| Open511 / DriveBC documentation read, 2026-09-16, operator's permission the same day ("Go ahead with the DriveBC fetch"; no script, lead's chat from the dev laptop, four requests) | `api.open511.gov.bc.ca/` (the API root: jurisdiction `drivebc.ca`, services `/events` and `/areas`) and `api.open511.gov.bc.ca/help` (the documentation, twice, second from cache) — the DriveBC `severity` and `event_type` enumerations and the supported `roads[]` fields, now in [`standards/README.md`](standards/README.md). `www.open511.org/documentation/` **refused**: self-signed certificate, nothing read. `github.com/open511/open511-spec` **404**, a guessed mirror. Then, on the operator's link: `ouvert.canada.ca` (the Government of Canada open data record for the DriveBC API, one read), `raw.githubusercontent.com/bcgov/api-specs/master/open511/open511_OAS3.json` and `…/open511.json` (BC's own OpenAPI specs, one read each — query parameters only, no response schema; the spec's `license` names **Open Government Licence – British Columbia**, the feed's licence, not previously recorded anywhere in the project). Finally **one request to `api.open511.gov.bc.ca/events?status=ACTIVE&limit=500`** (306 events, all of them) to measure the `severity`, `event_type` and `roads[].state` values actually in use — a measurement, not an import; nothing stored. Then, on five more links from the operator: `datastandards.directory/standards/open511` (one read; it named the maintainer's repository), `github.com/open511/open511API` (three directory reads and one `raw.githubusercontent.com` read of `documentation/1.0/event.html` — **the Open511 v1.0 Events specification itself**, verbatim enumerations now in the standards index), `www.municipal511.ca` (two reads, the legend and the terms), `www.coquitlam.ca/198/Traffic-Hotspots` (one read; nothing about the feed). Not read then: a 2015 TranBC blog post. Results in [`standards/README.md`](standards/README.md). Purpose: punch-list #91 ruling 5. |
| Municipal 511 Coquitlam pull, 2026-09-16 20:39 UTC, operator's permission in `gis-spatial-engineer`'s chat ("Yes, one pull", then "Yes, read the 2 bundles"; no script in the repo, dev laptop, **16 requests**) | `bc.municipal511.ca`: `/?municipality=coquitlam` (1), then every data file that page lists, `/Dynamic/jsonData0..12-<hash>.txt` (13; about 12 MB, and every Transnomis client's issues, not Coquitlam's alone). These are the same URLs the production sync (§2.1) calls hourly. Then the site's script bundles `/bundles/TIPS/Framework.min.js` and `/bundles/TIPS/Configurations.min.js` (2), which hold the vendor's `RoadClosureType` value → label switch. The estimate given before the pull was 2–4 requests; the page listed 13 files. Raw responses kept in the session scratchpad only; nothing imported, nothing on the kiosk's disk. Spatial filtering by one read-only query against the kiosk's PostGIS. Output: [`briefings/municipal511_coquitlam_records_2026-09-16.md`](briefings/municipal511_coquitlam_records_2026-09-16.md) and the value table in [`standards/README.md`](standards/README.md). Purpose: punch-list #91, piece B. |
| DriveBC events re-measured for punch-list #92, 2026-09-16 23:11 UTC, operator's permission in `gis-spatial-engineer`'s chat ("Yes, one request"; no script in the repo, dev laptop, **1 request**) | `api.open511.gov.bc.ca/events?status=ACTIVE&limit=500&format=json` — 286 active events. Only the two whose geometry falls near Coquitlam's boundary extent were tested, by one read-only query against the kiosk's PostGIS, with the old and the 100 m buffered closure tests. Raw response kept in the session scratchpad only; nothing imported. Result reported to lead for punch-list #92. Then, with the operator's permission again ("Yes, one request"), **1 request with the production sync's exact URL**, `api.open511.gov.bc.ca/events?format=json&limit=100` at 23:31 UTC, to see which events the sync actually receives: 100 of the 286 active, province-wide, and not the one event inside the city. A third, with the operator's permission again ("Yes, one request", 23:41 UTC), tested the fix before the kiosk relied on it: `events?format=json&status=ACTIVE&bbox=-122.89492,49.2184,-122.6197,49.35263` (the box computed from `public.city_boundary` + 100 m) — 3 events, 5,096 bytes, 0.22 s, RIDE-100086 included. |
| Road closure sync timed on the kiosk for punch-list #92, 2026-09-17 ~00:2x UTC, operator's permission in `gis-spatial-engineer`'s chat ("Yes, on the kiosk"; asked as ~15 requests) | A read-only timing copy of the deployed sync run inside `cfr_api` (`docker exec`, database session `default_transaction_read_only=on`, nothing written, nothing restarted), asking the feeds exactly as the sync does: DriveBC `events?format=json&status=ACTIVE&bbox=…` (1) and Municipal 511's Coquitlam page plus the 13 data files it lists (14). **Run twice — 30 requests, not 15** — because the first run's output was truncated in the terminal. Result: network 7.29 s of 8.76 s to the first write; Westwood St issue `78323174` no longer in the feed. |
| Parallel Municipal 511 fetch timed on the kiosk for punch-list #92, 2026-09-17, operator's permission in `gis-spatial-engineer`'s chat ("Yes, two runs (30 requests)") | The same read-only timing copy inside `cfr_api`, twice: the deployed (sequential) sync, then the new code loaded into the script (nothing deployed or restarted). **30 requests**, 15 per run, as a sync asks. Before: 16.51 s to the first write, data files 14.48 s one after another. After: 4.23 s, data files 2.31 s wall (9.17 s summed). |
| Feasibility reads for the operator's future-work question, 2026-09-16, his permission in the question itself ("could we hook Waze API… what about the DriveBC webcam api?"; lead's chat, dev laptop) | `www.openwebninja.com/api/waze` and `wazeapi.com` (one read each — both third-party resellers of Waze live-map data, neither states its rights to it), `www.waze.com/wazeforcities` (one read — the official partner programme, free, emergency services eligible), `github.com/bcgov/drivebc-webcam-api` (one read of the README; images are OGL-BC) and its `code/` path (**404**), `images.drivebc.ca/webcam/api/v1/webcams` (a recollected endpoint; **connection reset**, not verified). Second pass on the operator's further links: `open.canada.ca` (the DriveBC HighwayCams record, one read) and `catalogue.data.gov.bc.ca` (the `webcams.csv` it points to, one read — ~335 cameras, OGL-BC; read, not stored), `images.drivebc.ca/bchighwaycam/pub/cameras/292.jpg` (one HEAD, one GET — **nothing returned, no error**, not diagnosed), `www.drivebc.ca/cameras/292` (one read; a JavaScript shell), `developers.google.com/waze/data-feed` (a recollected path, **404**), `support.google.com/waze/partners/` (the help centre, three reads: the index, the data-sharing topic, and the two articles "Waze Data Feed specifications" `answer/13458165` and "How to give Waze attribution" `answer/10618825`). Nothing pulled beyond the pages; nothing stored. Findings: [`briefings/waze_and_webcam_feasibility_2026-09-16.md`](briefings/waze_and_webcam_feasibility_2026-09-16.md). **No call was added**; the operator's permission would be needed for one. |
| Google Maps Platform documentation read and one endpoint probe for punch-list #93, 2026-09-16, operator's permission relayed by lead ("Let's get A going"; lead's job named the billing read; `frontend-kiosk-architect`'s chat, dev laptop) | `developers.google.com`: `/maps/documentation/streetview/usage-and-billing`, `/maps/billing-and-pricing/pricing` (the *Street View Metadata* row), `/maps/documentation/streetview/metadata` (response fields and status codes), `/maps/documentation/javascript/reference/street-view-service` (`StreetViewLocation.latLng`) — four page reads in the app's browser pane. `maps.googleapis.com/maps/api/streetview/metadata?location=49.28,-122.80&radius=100&source=outdoor` **without a key**, twice (`curl`, once for headers with an `Origin`, once for the body): `REQUEST_DENIED`, HTTP 200, `Access-Control-Allow-Origin: *`. No key sent, no imagery or panorama data returned, nothing stored. Findings in the §4.1 row above. |
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
