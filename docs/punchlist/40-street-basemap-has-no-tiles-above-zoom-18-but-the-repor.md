# Punch list #40 — Street basemap has no tiles above zoom 18 — but the reported symptom did not reproduce

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | operational |
| **Area** | 🖥️ Live Operation Batch, 2026-08-23 |
| **Blocks** | 6 |
| **Origin** | `debug_and_qa_punchlist.md` L2254–3258 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 40. Street basemap has no tiles above zoom 18 — but the reported symptom did not reproduce
> **Status**: ⚠️ **Open — partially characterized; needs the exact location from the operator.**

Reported: *"Zoom 17 and greater, on map mode in Austin's north area is showing blank."*

**Measured** against the live tile server (`http://100.95.146.94:8081`), tileset metadata:

| Layer | minzoom | maxzoom | Format |
|:--|--:|--:|:--|
| `street` | 12 | **18** | png |
| `street_nolabels` | 12 | **18** | png |
| `satellite` | 12 | 20 | jpg |
| `cadastral` | 14 | 20 | png |

Above z18 the street layers return a **116-byte empty PNG**, not a 404. Probed around Austin
Heights (49.2505, −122.86) and north of it (49.262, −122.86):

```
z17  satellite=14858b  street=7406b     <- both have content
z18  satellite=17760b  street=1744b     <- both have content
z19  satellite=14806b  street=116b      <- street empty
z20  satellite=12602b  street=116b      <- street empty
```

**I could not reproduce blank at z17.** Both layers return real tiles at z17 and z18 at the
coordinates probed. The street layers do die at **z19+**, which is a real limitation but does
not match the reported zoom.

Further, the frontend is configured correctly for it: `MapConstants.js` sets
`maxNativeZoom: 18` on `GREY`/`DARK`/`OSM`/`VOYAGER` and `20` on `SATELLITE`, and
`MapLayers.jsx:100` passes it through to the Leaflet layer — so Leaflet should **upscale** the
z18 tile past 18 rather than request an empty z19. On that configuration the symptom should be
*blurry*, not *blank*.

**Open questions for the operator**: which base layer was selected (satellite, street, grey,
dark), and roughly which coordinates? "Austin's north area" is ambiguous, and the answer
determines whether this is a tile-coverage gap in a specific spot, an overzoom bug, or the
116-byte blank tile defeating the Leaflet upscale in a way the config implies it should not.
A screenshot with the zoom indicator visible would settle it.

---

---

## 40 (revised). Street AND satellite basemaps stop at zoom 17 across western Coquitlam
> **Status**: ⚠️ **Open — REPRODUCED and localised. Wider than first characterized.**
> This supersedes the "could not reproduce" note in #40 above, which was **wrong**: the first
> probe ran against coordinates ~1.5 km east of the affected area and a `while`-loop curl
> failure printed `0b` for every layer, which masked the result. Both errors are recorded
> rather than overwritten.

The operator's screenshot shows Explore mode, **Street Map** basemap, **zoom 17.0**, around
Cottonwood Ave / Regan Ave / Marshall St (Austin Heights). Parcel outlines and address labels
render on pure black — that is the **cadastral overlay alone**, with no basemap underneath.

**Measured** at 49.2588, −122.8843 (a real parcel front point from `public.parcels`):

| Zoom | `street` | `satellite` | `cadastral` |
|--:|--:|--:|--:|
| 15 | 24,805 b | — | — |
| 16 | 16,644 b | 24,452 b | — |
| **17** | **116 b (empty)** | **116 b (empty)** | 25,761 b |
| **18** | **116 b (empty)** | — | — |

A 116-byte PNG is the tile server's empty tile. **Both the street and satellite archives stop
at z16 here, while cadastral continues** — exactly the black-with-parcels rendering reported.

**The gap is a clean vertical cut, identical in both archives.** Scanning west→east along
z17 y=44869:

```
x=20780..20801  116 b   (empty)
x=20802         8,419 b (content)   <- boundary, lng ≈ -122.8656
x=20804..20830  content
```

Identical boundary for satellite (`x≤20801` empty, `x=20802` = 20,331 b), and the same cut at
z18. A north–south scan at x=20795 is empty at every latitude tested (y = 44820…44920), so
this is a longitude clip, not a patchy hole.

**Everything west of roughly −122.866 has no basemap above zoom 16** — Austin Heights,
Maillardville and Burquitlam, i.e. a populated strip roughly 4 km wide running the full height
of the city. Crews zooming in on any west-side address see parcel outlines on black.

**The declared metadata is wrong, which is why nothing detected this.** Both archives report:

```
street     minzoom 12  maxzoom 18  bounds [-123.04, 49.15, -122.6, 49.48]
satellite  minzoom 12  maxzoom 20  bounds [-123.04, 49.15, -122.6, 49.48]
```

The declared western bound of −123.04 overstates actual z17+ coverage by ~0.17° of longitude.
Because the metadata claims the coverage exists, the frontend has no way to know it does not,
and `maxNativeZoom` cannot help — the tiles are *within* the declared range and simply empty.

**This is not a frontend defect.** `MapConstants.js` (`maxNativeZoom: 18` street / `20`
satellite) and `MapLayers.jsx:100` are correct. The fix is in the MBTiles build: re-crawl the
western extent at z17–z20 for both archives, and correct the declared bounds so the two agree.
See the `mbtiles-tile-server` skill.

**Recommend raising the priority.** Austin Heights is a dense residential area, and losing the
basemap at exactly the zoom used to identify a specific property is an operational gap, not a
cosmetic one. Cadastral coverage masks it just enough to look intentional.

---

---

## 40 (quantified). The basemap gap covers 28% of the city's parcels
> **Status**: ⚠️ **Open — extent now measured. Recommend raising priority.**

Adding numbers to the coverage cut at longitude ≈ **−122.8656** established earlier (street
*and* satellite both empty above z16 west of it, cadastral unaffected):

| | |
|:--|--:|
| Parcels with coordinates | 65,401 |
| **Parcels west of the cut** | **18,568** |
| **Share of the city** | **28.4%** |
| Distinct emergency response zones affected | **20** |

So **more than a quarter of Coquitlam's addressed properties have no basemap above zoom 16**,
spanning 20 response zones — Austin Heights, Maillardville, Burquitlam. At the zoom used to
identify a specific driveway or roofline, crews see parcel outlines on black.

This is a tile-build defect, not a frontend one: `MapConstants.js` and `MapLayers.jsx` are
configured correctly, and the archives' own declared bounds (`-123.04 … -122.6`) overstate
their real coverage, so nothing in the system can detect the gap. Fix is a re-crawl of the
western extent at z17–z20 for `satellite` and `street`/`street_nolabels`, plus corrected
metadata bounds. See the `mbtiles-tile-server` skill.

---

---

## 40 (root cause). The tile compiler narrows its bounding box above z16, and then declares the wide one anyway
> **Status**: ⚠️ **Open — ROOT CAUSE FOUND 2026-08-23. Confirmed: the measured cut matches
> the constant to four decimal places.**

`backend/scripts/compile_mbtiles.py:397-406` downloads a **different bounding box per zoom
tier**:

```python
for z in range(min_z, max_z + 1):
    if z <= 16:
        # Full regional bounds for Zooms 12-16
        z_tiles = calculate_tiles(REGIONAL_MIN_LAT, REGIONAL_MIN_LON, ...)      # west -123.04
    elif z <= 18:
        # Coquitlam operational corridor for Zooms 17-18
        z_tiles = calculate_tiles(COQUITLAM_MIN_LAT, COQUITLAM_MIN_LON, ...)    # west -122.865
    else:
        # Urban Core & Apparatus Bay Stations 1-4 Corridor for Zooms 19-20
        z_tiles = calculate_tiles(URBAN_CORE_MIN_LAT, URBAN_CORE_MIN_LON, ...)  # west -122.870
```

| Constant | West | East | South | North | Applies to |
|:--|--:|--:|--:|--:|:--|
| `REGIONAL_*` | **−123.04** | −122.60 | 49.15 | 49.48 | z12–16 |
| `COQUITLAM_*` | **−122.865** | −122.685 | 49.208 | 49.385 | z17–18 |
| `URBAN_CORE_*` | **−122.870** | −122.730 | 49.240 | 49.340 | z19–20 |

**`COQUITLAM_MIN_LON = -122.865` (`:59`) is the defect.** The measured boundary was
**−122.8656** (tile x=20801 empty, x=20802 content at z17). That is the same line to four
decimal places — it is this constant, not a crawl failure, not a corrupted archive.

Every observation now follows from it:

* z16 renders at Cottonwood Ave (−122.884) — inside `REGIONAL`. **Measured 16,644 b.** ✅
* z17 is empty there — outside `COQUITLAM`. **Measured 116 b.** ✅
* `street` and `satellite` share the **identical** boundary because they share this function,
  differing only in `max_zoom`. ✅
* `cadastral` is unaffected — it is built by a *different* script,
  `crawl_cadastral_tiles.py`, whose `DEFAULT_MIN_LON = -122.92`. That is why the operator's
  screenshot shows parcels and labels on black: the only layer with western high-zoom
  coverage is the overlay. ✅

#### The constant contradicts the project's own definition of the city

The comment at `:57` calls it *"Coquitlam Municipal Core Bounds"*, but Coquitlam extends west
to roughly **−122.93**. Two other places in this codebase already say so:

* `crawl_cadastral_tiles.py` uses **−122.92**.
* **CLAUDE.md §5** defines out-of-bounds as `lng < -122.92`, via `isWithinCoquitlam()`.

So the kiosk considers −122.90 to be **inside** the city and will happily route there and
suppress the out-of-bounds card — while having no basemap above z16 for it. The bounds check
and the tile build disagree about where Coquitlam is.

#### The declared metadata hides it

`compile_mbtiles.py:142` writes the metadata `bounds` for **every** layer as the *regional*
box:

```python
"bounds": f"{REGIONAL_MIN_LON},{REGIONAL_MIN_LAT},{REGIONAL_MAX_LON},{REGIONAL_MAX_LAT}",
```

The archive therefore advertises coverage from −123.04 while only holding −122.865 above z16.
This is the reason nothing detected the gap: the frontend's `maxNativeZoom` is correct and has
no way to know, `mbtileserver` serves a 116-byte empty tile rather than a 404, and the
metadata says everything is fine. **A layer that reports coverage it does not have is the same
defect class as §6.1** — a confident wrong answer beats a visible unknown.

#### Scope, measured against `public.parcels`

| Missing above | Parcels affected | Share of city |
|:--|--:|--:|
| **z16** (outside `COQUITLAM` box) | **18,735** | **28.6%** |
| **z18** (outside `URBAN_CORE` box) | **21,023** | **32.1%** |

So roughly **a third of the city has no basemap at the zoom used to pick out a driveway,
roofline or hydrant** — Austin Heights, Maillardville, Burquitlam, plus the northern and
eastern edges. 20 emergency response zones are affected.

#### Fix

1. **Correct the constants.** `COQUITLAM_MIN_LON` should be ≈ **−122.93** to match
   `isWithinCoquitlam()` and the cadastral crawl, and the other three `COQUITLAM_*` bounds
   should be reviewed against the real municipal boundary at the same time. Give them a
   provenance comment naming the source (§6.3) — the current values have none.
2. **Reconsider the `URBAN_CORE` tier for z19–20.** A 0.14° × 0.10° box is a small fraction of
   the city, and it excludes 32% of parcels from the highest-detail imagery. If it exists to
   bound archive size, that trade-off should be stated and sized, not implied.
3. **Write honest metadata.** The `bounds` value must describe what the archive actually
   contains. If coverage differs per zoom, the declared bounds should be the *narrowest*
   tier, not the widest — under-promising is safe, over-promising is what produced this.
4. **Re-crawl** the western extent at z17–20 for `satellite`, `street` and `street_nolabels`,
   then checkpoint to `journal_mode = DELETE` per CLAUDE.md §1 before the read-only mount.

**Worth doing regardless of the re-crawl**: give the kiosk a visible signal when a base layer
has no tile, rather than rendering black. The operator diagnosed this as "blank" and could not
tell it apart from a failed tile server.

See the `mbtiles-tile-server` skill for the compile and checkpoint procedure.

---

---

## 40 (plan). Coverage decided by the municipal polygon, not a box
> **Status**: 🔧 **Scripts updated 2026-08-26; crawl NOT yet run.**

The operator rejected a bounding box: *"pulling a square city boundary doesn't really work
either. The city is an odd shape."* Correct — Coquitlam is an L wrapped around Port Moody and
Port Coquitlam, and **fills only 44.8% of its own bounding box** (129.7 km² of 289.3 km²).

Tiles are now tested against the real boundary + 1 km buffer:

| z12–20 tiles | |
|:--|--:|
| Bounding box | 778,515 |
| **Polygon** | **430,845** |
| Saved | **44.7%** — and the saving grows with zoom (44.7% at z20) |

**Agreed coverage, 2026-08-26:**

| Layer | Area | Zooms | Tiles | Size |
|:--|:--|:--|--:|--:|
| `street` (labelled) | city polygon **+ region for context** | 12–20 city, 12–**16** region | 439,157 | 1.54 GB |
| `street_nolabels` | city polygon | 12–20 | 430,845 | 1.21 GB |
| `satellite` (+7.5 cm ortho) | city polygon | 12–20 | 430,845 | 6.29 GB |
| `cadastral` | city polygon | 14–20 | ~430k | ~0.69 GB |
| | | | **~1.73 M** | **~9.7 GB** |

Sizes use bytes/tile **measured from the existing kiosk archives** (street 3.5 KB, nolabels
2.8 KB, satellite 14.6 KB, cadastral 1.6 KB), not estimates. Kiosk has 226 GB free, so disk
is not the constraint — crawl time and CDN load are.

Regional context is deliberately a plain **box**, not the polygon: it is explicitly *not* the
city, and at z12–16 the whole region is only 10,149 tiles / 36 MB. `REGIONAL_MAX_ZOOM = 16`
because z12–20 region-wide would be 2,523,994 tiles (~8.8 GB, over a day of crawling) for
street detail in municipalities CFR does not respond to.

**Changes made:**

* `compile_mbtiles.py` — `filter_tiles_to_city()` tests each tile against the polygon.
  Uses **intersects, not contains**: a tile straddling the boundary holds real city ground,
  and contains-style strictness would carve a ragged hole around the whole perimeter (the
  same trap as #13). Falls back to the bounding box if shapely or the GeoJSON is missing —
  **over**-fetching, the safe direction.
* `backend/data/gis/coquitlam_tile_coverage.geojson` — 55-point polygon, generated.
* `backend/scripts/export_tile_coverage.py` — regenerates it from `public.city_boundary`.
  Hand-editing is what caused this defect; the script exists so nobody has to.
* `crawl_cadastral_tiles.py` — same polygon filter, and its bounds corrected from the
  hand-picked `-122.92 … -122.72` to the real extent. The old east limit stopped 0.1° short
  of the city at `-122.621`, leaving **Pinecone Burke and Minnekhada with no parcel or
  address labels at any zoom** — the wildland end of the response area.
* All layers now reach **z20 inside the city** rather than z18.

**Before crawling — unverified:** whether Carto Voyager and ArcGIS World Imagery actually
serve real z19/z20 raster tiles here, or upscale. The dev machine is sandboxed from both CDNs
(HTTP 000), so this must be checked **on the kiosk** first. If either upscales, ~322k tiles
per layer at z20 would be fetched for no added detail. Check before committing to the crawl,
not after (§7.3a).


**Runbook**: [`docs/briefings/tile_recrawl_runbook.md`](./briefings/tile_recrawl_runbook.md) —
`nohup`-launched, resumable crawl commands for a poor connection, plus the pre-crawl z19/z20
availability check, the mandatory WAL checkpoint, and the verification queries.

---

---

## 40 (resolved). Re-crawl complete — the gap is closed and verified
> **Status**: ✅ **Closed 2026-08-27.** Verified against the running tile server, not inferred.

The re-crawl ran unattended on the kiosk via a sequential chain (`/tmp/run_all_crawls.sh`).
All four layers completed `rc=0`.

**The tile that started this** — Cottonwood Ave z17, `17/20795/44869`, the exact one blank in
the operator's screenshot. It served a **116-byte empty PNG** before:

| Layer | Before | After |
|:--|--:|--:|
| `street` | **116 b** | **8,884 b** |
| `street_nolabels` | **116 b** | **7,613 b** |
| `satellite` | **116 b** | **20,745 b** |
| `cadastral` | 25,761 b | 25,761 b (was never affected) |

Deep zoom on the west side also confirmed: `street` z19 → 3,130 b, `satellite` z20 → 12,284 b.
Austin Heights, Maillardville and Burquitlam now have basemap coverage at every zoom.

**Final archives:**

| Layer | Tiles | Size | Zooms |
|:--|--:|--:|:--|
| `street` | 130,387 | 469.5 MB | 12→19 |
| `street_nolabels` | 130,387 | 428.6 MB | 12→19 |
| `satellite` | 511,118 | 7,695.2 MB | 12→20 |
| `cadastral` | 606,938 | 990.6 MB | 14→20 |

All four report `Integrity: ok` and `Journal Mode: delete`. Disk went 218 GB → 223 GB used,
222 GB free.

**The metadata now tells the truth** — the specific lie that hid this defect:

```
street           12 -> 19  bounds [-123.04,   49.15,    -122.6,     49.48]     <- regional, correct
street_nolabels  12 -> 19  bounds [-122.90723, 49.21087, -122.60729, 49.36017] <- city
satellite        12 -> 20  bounds [-122.90723, 49.21087, -122.60729, 49.36017] <- city
cadastral        14 -> 20  bounds [-122.90723, 49.21087, -122.60732, 49.36017] <- city
```

Only `street` declares the regional box, because it is the only layer that actually holds
regional tiles. Previously all four declared `-123.04` regardless of content.

#### Two things worth recording for next time

**1. `finalize_mbtiles.py` cannot convert a WAL archive while `cfr_tiles` is running.**
The chain's finalize step failed with `sqlite3.OperationalError: database is locked` on
`street.mbtiles`, which still had `-wal`/`-shm` files. `PRAGMA journal_mode = DELETE` needs an
exclusive lock, and mbtileserver holds the file open. `cadastral` and `satellite` appeared to
succeed only because they were *already* in `delete` mode, so their pragma was a no-op — the
script was one archive away from reporting success on work it had not done.

Fix applied by hand: `docker stop cfr_tiles` → finalize → `docker start cfr_tiles`. **The
runbook's step 4 is wrong as written** and needs the stop/start added.

**The chain's failure guard did its job**: it refused to restart `cfr_tiles` after the failed
finalize and exited non-zero, rather than pressing on and leaving un-checkpointed archives to
fail differently under a read-only mount.

**2. `Pillow` was missing from the kiosk venv.** `compile_mbtiles.py` imports `PIL` at module
level, so the first launch died instantly with `ModuleNotFoundError`. Installed 12.3.0. The
runbook only mentioned `shapely`.

#### Timings, measured

| Layer | Duration | Rate |
|:--|:--|:--|
| `street` | 13 min (87,502 tiles) | 112.6 tiles/s |
| `street_nolabels` | 13 min | ~112 tiles/s |
| `satellite` | 29 min | ~110 tiles/s |
| **`cadastral`** | **8 h 35 min** | **~10 tiles/s** |

**The City's ArcGIS MapServer is ~11× slower than the Carto and ArcGIS World Imagery CDNs**
and dominated the run — 8.5 of the 9.5 hours. Budget for that before scheduling any future
cadastral re-crawl; the estimate of "~2.5–3 hours total" was wrong because it assumed a
uniform rate across all four sources.

#### Correction: the slow cadastral crawl was self-inflicted

The claim above that "the City's ArcGIS MapServer is ~11× slower" is **wrong and withdrawn.**
The operator questioned it, and the config says otherwise:

```
Workers / Delay: 8 concurrent workers | 200ms delay (~5.0 req/s)
Crawl phase completed in 08:35:12 (153,094 ok, 8 failed, 5.0 tiles/s).
```

`crawl_cadastral_tiles.py` carried a global `RateLimiter` with `min_interval = 0.2s`. It
serializes every request behind a single lock, so it is a hard **5 req/s** ceiling that the
worker count does **not** multiply. The crawl finished at exactly 5.0 tiles/s — pinned to the
limiter for the whole 8½ hours. `compile_mbtiles.py` has no limiter at all (32 workers,
~110 tiles/s), which is the entire 22× difference.

**How the wrong conclusion was reached**: the "~10 tiles/s" figure was derived by dividing the
*total archive* (606,938 tiles) by elapsed time instead of the *newly downloaded* 153,094. The
real rate was 4.95/s, which would have pointed straight at the 0.2 s constant. A cause was
inferred from a mis-computed number rather than read from the config — the exact failure mode
CLAUDE.md §7 exists to prevent, and worth recording as such.

**Resolution**: `DEFAULT_DELAY_SEC = 0.05` (~20 req/s), operator decision 2026-08-27, with
provenance inline. Deliberately not unlimited — the City's MapServer is municipal
infrastructure belonging to the department's data partner and the licensor of this data, not a
commercial CDN. Expect a full cadastral re-crawl near 2 h rather than 8.5 h.

**Still open**: **8 tiles failed** in that run and have not been investigated. The crawler is
resumable and would retry them, so a short re-run would show whether they are transient or a
genuine gap.

---
