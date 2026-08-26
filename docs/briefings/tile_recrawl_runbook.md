# Runbook: re-crawling the offline tile archives over a bad connection

**Written 2026-08-26.** Punch-list **#40**. Every long job here is launched with `nohup` so it
survives a dropped SSH session — the connection is only used to *start* and *check* work, never
to hold it open.

**All of these are resumable.** Both crawlers read the existing MBTiles archive first and skip
tiles already present, so a killed run loses nothing but the tile in flight. If a job dies,
re-run the identical command.

---

## 0. First, one check that decides the plan

The dev machine is sandboxed from both CDNs, so this could not be verified locally. **Run it
before committing to the full crawl** — if either source upscales rather than serving real
z19/z20, that is ~322,000 wasted tile fetches per layer.

```bash
ssh tcfire@100.95.146.94 'for z in 17 18 19 20; do s=$((20-z)); printf "z%-3s carto=%-8s arcgis=%s\n" "$z" "$(curl -s -o /dev/null -w %{size_download}b --max-time 15 "https://a.basemaps.cartocdn.com/rastertiles/voyager/$z/$((166432>>s))/$((358988>>s)).png")" "$(curl -s -o /dev/null -w %{size_download}b --max-time 15 "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/$z/$((358988>>s))/$((166432>>s))")"; done'
```

**Reading the result:** byte sizes that keep changing through z20 mean real tiles. Sizes that
go flat, or identical bytes at z19 and z20, mean upscaling — in which case drop the street
styles to `max_zoom: 19` in `LAYER_CONFIGS` and save ~1.6 GB and several hours. The 7.5 cm
orthophotos are genuinely z20-native either way, so `satellite` stays at 20 regardless.

---

## 1. Deploy the code and regenerate the coverage polygon

Fast, safe to run in the foreground.

```bash
ssh tcfire@100.95.146.94 'cd /home/tcfire/CFR-EVO-APP && git pull && .venv/bin/pip install shapely 2>&1 | tail -2'
```

```bash
ssh tcfire@100.95.146.94 'cd /home/tcfire/CFR-EVO-APP && export DATABASE_URL=$(docker exec cfr_api printenv DATABASE_URL | sed "s/@postgres:/@localhost:/") && .venv/bin/python backend/scripts/export_tile_coverage.py'
```

Expect roughly: `55 points, 199.4 km2 (68.9% of its 289.3 km2 bounding box)`.

> The polygon is committed, so this step only matters if the municipal boundary changed.
> **There is no bounding-box fallback** — if shapely is missing or the GeoJSON is unreadable,
> the crawlers stop with an error rather than silently crawling the wrong area.

---

## 2. Launch the crawls (nohup — safe to disconnect)

One layer at a time, so a failure is isolated and the logs stay readable. Each returns
immediately; the work continues on the kiosk.

**Street, labelled** — city to z20 plus regional context to z16 (~439k tiles, ~1.5 GB):

```bash
ssh tcfire@100.95.146.94 'cd /home/tcfire/CFR-EVO-APP && nohup .venv/bin/python backend/scripts/compile_mbtiles.py --layer street > /tmp/crawl_street.log 2>&1 & echo "started pid $!"'
```

**Street, no labels** — city only, z12–20 (~431k tiles, ~1.2 GB):

```bash
ssh tcfire@100.95.146.94 'cd /home/tcfire/CFR-EVO-APP && nohup .venv/bin/python backend/scripts/compile_mbtiles.py --layer street_nolabels > /tmp/crawl_nolabels.log 2>&1 & echo "started pid $!"'
```

**Satellite + 7.5 cm ortho** — the big one (~431k tiles, ~6.3 GB):

```bash
ssh tcfire@100.95.146.94 'cd /home/tcfire/CFR-EVO-APP && nohup .venv/bin/python backend/scripts/compile_mbtiles.py --layer satellite > /tmp/crawl_satellite.log 2>&1 & echo "started pid $!"'
```

**Cadastral** — City ArcGIS overlay, now including the eastern city (~431k tiles, ~0.7 GB):

```bash
ssh tcfire@100.95.146.94 'cd /home/tcfire/CFR-EVO-APP && nohup .venv/bin/python backend/scripts/crawl_cadastral_tiles.py > /tmp/crawl_cadastral.log 2>&1 & echo "started pid $!"'
```

> **Run them one at a time, not in parallel.** Four concurrent crawlers against the same two
> CDNs is both slower and rude. `satellite` is the long pole.

---

## 3. Check progress (a few seconds of connection)

```bash
ssh tcfire@100.95.146.94 'for f in /tmp/crawl_*.log; do echo "=== $f"; tail -3 $f; done; echo "=== still running:"; pgrep -af "compile_mbtiles|crawl_cadastral" || echo "  none"'
```

Disk and archive sizes as they grow:

```bash
ssh tcfire@100.95.146.94 'df -h /home | tail -1; ls -lh /home/tcfire/CFR-EVO-APP/backend/data/tiles/*.mbtiles | awk "{print \$9, \$5}"'
```

Stop a run (it will resume cleanly from where it stopped):

```bash
ssh tcfire@100.95.146.94 'pkill -f compile_mbtiles && echo stopped'
```

---

## 4. Finalize — REQUIRED before the tile server can read the archives

`cfr_tiles` mounts `backend/data/tiles/` **read-only**, so any archive still in SQLite WAL mode
fails with `SQLITE_CANTOPEN`. Checkpoint to `journal_mode = DELETE` (CLAUDE.md §1):

```bash
ssh tcfire@100.95.146.94 'cd /home/tcfire/CFR-EVO-APP && .venv/bin/python backend/scripts/finalize_mbtiles.py && docker restart cfr_tiles && sleep 4 && docker ps --filter name=cfr_tiles --format "{{.Status}}"'
```

---

## 5. Verify the gap is actually closed

The exact tile that was blank in the operator's screenshot — Cottonwood Ave, z17. It returned
**116 bytes** (the empty-tile placeholder) before the fix:

```bash
ssh tcfire@100.95.146.94 'for l in street street_nolabels; do printf "%-16s " $l; curl -s -o /dev/null -w "%{http_code} %{size_download}b\n" "http://localhost:8081/services/$l/tiles/17/20795/44869.png"; done; printf "%-16s " satellite; curl -s -o /dev/null -w "%{http_code} %{size_download}b\n" "http://localhost:8081/services/satellite/tiles/17/20795/44869.jpg"'
```

**Pass:** all three well above 116 bytes. **Fail:** still 116 — the crawl did not reach there;
check the log for that layer.

Confirm the declared metadata now matches reality:

```bash
ssh tcfire@100.95.146.94 'for l in street street_nolabels satellite cadastral; do printf "%-16s " $l; curl -s "http://localhost:8081/services/$l" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get(\"minzoom\"),d.get(\"maxzoom\"),d.get(\"bounds\"))"; done'
```

`street` should declare the regional bounds; the others the city bounds. **If a layer still
declares `-123.04` while holding only city tiles, stop** — that is the exact lie that hid this
defect for as long as it did.

---

## 6. Rebuild the frontend

Picks up the "no map data" hatch, so any remaining gap is visibly labelled rather than black.

```bash
ssh tcfire@100.95.146.94 'cd /home/tcfire/CFR-EVO-APP/frontend && nohup npm run build > /tmp/build.log 2>&1 & echo "building"'
```

Then **hard-reload the kiosk browser** (`Ctrl+Shift+R`) — it caches the old bundle.

---

## Notes

* **Nothing here restarts `cfr-agent`,** so the audio listener is untouched and no live call is
  missed. Only `cfr_tiles` restarts, in step 4.
* Budget roughly **9.7 GB** across all four archives, against 226 GB free.
* If Tailscale SSH stalls silently, the session has lapsed and needs browser re-auth — that is
  the usual cause, not a hung command. Prefix with `timeout 30` when checking status so a lapse
  fails fast instead of hanging.
