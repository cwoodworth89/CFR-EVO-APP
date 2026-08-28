# Runbook: re-crawling the offline tile archives over a bad connection

**Written 2026-08-26.** Punch-list **#40**. Every long job here is launched with `nohup` so it
survives a dropped SSH session — the connection is only used to *start* and *check* work, never
to hold it open.

**All of these are resumable.** Both crawlers read the existing MBTiles archive first and skip
tiles already present, so a killed run loses nothing but the tile in flight. If a job dies,
re-run the identical command.

---

## 0. Zoom depths, as configured

Settled 2026-08-26. **Street styles stop at z19**, satellite goes to z20.

| Layer | Area | Zooms | Tiles | Size |
|:--|:--|:--|--:|--:|
| `street` (labelled) | city **+ region to z16** | 12–19 | 118,702 | ~0.4 GB |
| `street_nolabels` | city only | 12–19 | 108,553 | ~0.3 GB |
| `satellite` + 7.5 cm ortho | city only | 12–**20** | 430,845 | ~6.3 GB |
| `cadastral` | city only | 14–20 | 430,801 | ~0.7 GB |
| **Total** | | | **1,088,901** | **~7.7 GB** |

Against 226 GB free, so disk is not a constraint — crawl time is.

> **Measured 2026-08-27.** The three CDN-backed layers ran at ~110 tiles/s (13 min, 13 min and
> 29 min). **`cadastral` took 8 h 35 min at ~10 tiles/s** — the City's ArcGIS MapServer is
> roughly 11× slower than the Carto and Esri CDNs and dominates the whole run. Budget about
> **9.5 hours**, essentially all of it cadastral. Assuming a uniform rate across sources gave
> a "2.5–3 hour" estimate that was badly wrong.

**Why the street styles stop at 19.** Carto's raster basemaps are vector-derived and gain
little between z19 and z20, while z20 alone is roughly 4× every other zoom combined. Stopping
at 19 saves **644,584 tiles (~2.0 GB)** across the two styles. Leaflet still zooms past
`maxNativeZoom` by upscaling, so the map goes just as deep — it stops fetching *new* detail,
not zooming. Raising it later is a one-line change to `max_zoom` in `LAYER_CONFIGS` plus a
re-run; the crawlers are resumable, so only the z20 tiles would be fetched.

**Satellite stays at 20** because the City's 7.5 cm orthophotos are genuinely z20-native, and
roofline/driveway detail is the operational reason that layer exists.

---

## 1. Deploy the code and regenerate the coverage polygon

Fast, safe to run in the foreground.

```bash
ssh tcfire@100.95.146.94 'cd /home/tcfire/CFR-EVO-APP && git pull && .venv/bin/pip install shapely Pillow 2>&1 | tail -2'
```

> **Both** are required. `compile_mbtiles.py` imports `PIL` at module level, so a missing
> Pillow kills the run instantly with `ModuleNotFoundError` — found the hard way 2026-08-27.

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

**Street, labelled** — city to z19 plus regional context to z16 (~119k tiles, ~0.4 GB):

```bash
ssh tcfire@100.95.146.94 'cd /home/tcfire/CFR-EVO-APP && nohup .venv/bin/python backend/scripts/compile_mbtiles.py --layer street > /tmp/crawl_street.log 2>&1 & echo "started pid $!"'
```

**Street, no labels** — city only, z12–19 (~109k tiles, ~0.3 GB):

```bash
ssh tcfire@100.95.146.94 'cd /home/tcfire/CFR-EVO-APP && nohup .venv/bin/python backend/scripts/compile_mbtiles.py --layer street_nolabels > /tmp/crawl_nolabels.log 2>&1 & echo "started pid $!"'
```

**Satellite + 7.5 cm ortho** — the big one, and the only layer going to z20 (~431k tiles, ~6.3 GB):

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

## 4. Finalize — REQUIRED, and `cfr_tiles` MUST be stopped first

`cfr_tiles` mounts `backend/data/tiles/` **read-only**, so any archive still in SQLite WAL mode
fails with `SQLITE_CANTOPEN`. Checkpoint to `journal_mode = DELETE` (CLAUDE.md §1).

> **Corrected 2026-08-27 after this step failed in the real run.** `PRAGMA journal_mode =
> DELETE` needs an **exclusive** lock, and mbtileserver holds every archive open — so
> finalizing while `cfr_tiles` runs dies with
> `sqlite3.OperationalError: database is locked`.
>
> Worse, it can *look* like it worked: archives already in `delete` mode finalize fine because
> the pragma is a no-op, so the script reported two successes before hitting the one archive
> that actually needed converting. **Stop the container first.**

```bash
ssh tcfire@100.95.146.94 'cd /home/tcfire/CFR-EVO-APP && docker stop cfr_tiles && sleep 2 && .venv/bin/python backend/scripts/finalize_mbtiles.py 2>&1 | tail -25 && docker start cfr_tiles && sleep 5 && docker ps --filter name=cfr_tiles --format "{{.Status}}"'
```

Every archive should report `Integrity: ok` and `Journal Mode: delete`. Allow a couple of
minutes — checkpointing the 7.6 GB satellite archive is not instant.

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

Expect `street`/`street_nolabels` maxzoom **19**, `satellite`/`cadastral` **20**. `street`
should declare the regional bounds; the others the city bounds. **If a layer still declares
`-123.04` while holding only city tiles, stop** — that is the exact lie that hid this
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
* Budget roughly **7.7 GB** / 1.09M tiles across all four archives, against 226 GB free.
* If Tailscale SSH stalls silently, the session has lapsed and needs browser re-auth — that is
  the usual cause, not a hung command. Prefix with `timeout 30` when checking status so a lapse
  fails fast instead of hanging.
