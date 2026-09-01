# Punch list — session notes and reconciliation history

Narrative context lifted out of the punch list index. Not tracked work; read for provenance only.

[← punch list index](../debug_and_qa_punchlist.md)

---

## Status reconciliation preamble (as written 2026-08-21)

> [!NOTE]
> **Status key (reconciled 2026-08-21, commit `0db0b75`)**: ✅ = verified against the
> current working tree *and*, where the item touches data, the running kiosk database.
> ⚠️ = confirmed still open. Each status line states what was checked, so a later reader
> can tell **reported** from **confirmed** (CLAUDE.md §6.6).
>
> Items closed at the 2026-08-21 reconciliation: **#7** (obsolete — the cascade step was
> removed), **#11** (fixed and re-synced). Item **#2** was reopened, then closed the same
> day once both surviving coordinate fallbacks were removed.
>
> Closed 2026-08-22 by the intersection rebuild: **#8** (test suite), **#9** and **#13**
> (`public.intersections` derived from road geometry), plus new items **#15** (fuzzy
> substitution) and **#16** (`<street> and <street>` CAD artifact) found and fixed in the
> same pass.
>
> Still open: **#1**, **#10**, **#12**, **#14**, **#17**, **#19**, **#20**, **#21**,
> **#22**.
>
> **Found from live operation 2026-08-22**, none of them reachable from the test corpus —
> all three came from one operator screenshot of a real dispatch: **#24** (an invented
> hydrant shown on every call, closed), **#25** (a corrected re-broadcast queueing itself
> as a second call, closed on the kiosk side with a latent backend ordering defect
> recorded), **#26** (the pipeline's INFO logging is discarded, closed — and the reason #25
> could not be diagnosed from logs).
>
> Closed 2026-08-22 during decomposition: **#22** (closure timeframe filters matched nothing).

---

## Method note

`Addresses.shp` and `road_centre_lines.geojson` are git-ignored and were read **locally**, as
standalone scratch checks (CLAUDE.md §3.2). GDAL/fiona are not installed on the dev machine,
so the DBF was parsed directly with a ~40-line reader rather than geopandas — worth knowing
before anyone plans shapefile work here. Tailscale SSH lapsed mid-session and needs browser
re-auth, so kiosk-side checks in this batch were done over HTTP to the tile server and via the
`cfr-postgres` MCP connection instead.

---

---

## Status sync, 2026-08-27

* **#38 (parcel front points on the wrong street)** — ⏳ **being handled by another agent.**
  Not to be worked here; see the roads/GIS thread. The measurement stands as recorded:
  `1178 Heffley Cres` sits 0.0 m from Pinetree Way and 109.2 m from Heffley Crescent, with a
  sampled ~11.5% of parcels more than 60 m from their own named street.

* **#42 (roads `STATUS` filter)** — ✅ **Closed by another agent** in `302af14`
  *"fix(gis): import roads of every status, and repair the import script itself"*, which took
  the recommended shape rather than deleting the filter. Verified against the kiosk database:

  | | Before | Now |
  |:--|--:|--:|
  | `public.roads` rows | 3,214 | **3,451** |
  | Distinct `status` values | `OPERATING` only | **`METRO, MOT, OPERATING, PRIVATE`** |
  | Parcel streets with no matching road | 45 | **17** |

  So 28 of the 45 missing streets are resolvable again, and jurisdiction is preserved rather
  than flattened. **17 remain** — worth a look in that thread, since they are now a different
  and smaller problem than the `STATUS` filter (likely name-form mismatches rather than absent
  geometry, given `Highway #1` and the strata roads are back).

* **#41 (parcel import / `629 Cottonwood Ave`)** — partly overtaken by `e0466df`
  *"account for the 4,307-row parcel gap — reconciled, but selection is arbitrary"*. The
  remaining action from this thread is unchanged and independent: **`Addresses.shp` is dated
  2025-06-22, over a year old.** Re-pull and re-import; the upsert preserves pre-plans, lockbox
  notes and Street View headings.


---

---

## Shipped and verified

| Commit | Defect | Verification |
|:--|:--|:--|
| `703173c` | **Intersections read back alphabetically.** `public.intersections` stores the pair sorted (`street_a < street_b` on all 1,995 rows), so the answer ignored the announced order on **10 of 12** resolved intersection dispatches. `lookup()` now records which leg was spoken first and `_payload` leads with it; spellings stay municipal, only the order comes from the announcement. Safe because `spoken_first` is set only on an exact key match, where both legs are already the same pair — no fuzzy matching. | live geocode on kiosk, both orders |
| `703173c` | **XStreets never reached the reconstructed transcript.** Both `DispatchData` copies in `phase2.py` omitted `cross_street_1/2`. This is what the operator was rating as "missing xstreets" — see #51. | live re-parse |
| `55b6c4a` | **`sanitize_transcript` deleted `&`.** Stripped as punctuation, leaving `"anson avenue lincoln ave"` with no separator, so `clean_location_text` correctly removed the second street as trailing junk. Now rewritten to `" and "` before the strip. See #52. | real call `DISP-2026-AAFDB8` |
| `53a74e5` | **XStreets and subaddress did not coalesce across rounds** — taken from the first candidate carrying an address, so anything round 1 dropped was lost even when round 2 had it. `_coalesce_across_rounds` now mirrors how `map_grid` and `radio_channel` already resolve. Partially advances #44. | 5 unit tests + live |
| `faa9c8c` | **Street suffix doubling.** `fuzzy_correct_street`'s docstring said it matched "known Coquitlam **base** street names"; the list holds **full** names. It scored the base against full names then re-appended the caller's suffix — `"Christmas Way"` → `"Christmas Way Way"`. Ten of the 23 unmatched cross streets were this, all real streets. Now scores base against base, returns the municipal name, and breaks ties on suffix agreement so `"Pinetree Way"` cannot be answered with `"Pinetree Close"`. | **0 of 1,320** re-derived values now double |
| `922e582` | **Cross-round comparator + backtest harness** (`round_comparison.py`, `backtest_round_comparison.py`). Built and corpus-scored; **wired into nothing**, deliberately. | 19 tests |

---

## Also recorded, no separate entry

* **`is_ambiguous` is never persisted.** 0 of 510 records carry the key in `target`, while
  `requested_address` reaches 12. The geocoder computes ambiguity and it is dropped before
  storage, so the §5 candidate-selector banner cannot fire from a stored record. Detail in #54.
* **Punch-list numbers are colliding across concurrent sessions.** There are two **#51**s, and a
  #55 written in this session had to be renumbered to **#56**. Agree a convention before
  several agents append here.

---

## Session batch, 2026-08-31 — basemap licensing, imagery provenance, and a day of my own corrections

Full narrative: [`qa_handoff_2026-08-31.md`](../qa_handoff_2026-08-31.md).

| Commit | Change | Verification |
|:--|:--|:--|
| `158c1c4` | **The 7.5cm orthos had never been ingested.** Every tile in `satellite.mbtiles` measured byte-identical to live Esri at five locations, z19 and z20, while `MapConstants` attributed the layer to the City. The runbook was the cause: `gis-pipeline-sync` §4.1 said to run `compile_mbtiles.py --layer satellite` to ingest them, and that command crawls Esri. | MD5 vs live Esri, 5 sites |
| `158c1c4` | **Carto watermarks every unauthenticated tile.** z14–z20 verified live from the kiosk. The 2026-08-27 re-crawl fetched 81,032 z19 tiles per street layer after the change. | live probe, all zooms |
| `ae26ec1` | **`SatelliteMiniMap` and `PropertySatellitePanel` were still on Esri** after the aerial layer moved — each hardcoded its own URL and zoom. The property panel is where crews read rooflines. Both now read `BASE_LAYERS.SATELLITE`. | bundle grep |
| `d4a04fc` | **Pivot to crawling the City's own imagery service.** Measured at z20: City 1344, best local MrSID build 954, Esri 664, the MrSID archive we shipped 540. Esri layer and the whole MrSID/GDAL path retired; `RateLimiter` added for municipal sources. | edge-energy, same ground |
| `465dd3c` | **Deep sweep of the retired processes.** Found two live defects: `verify_ortho_provenance.py` passed on a premise that had become false, and `test_tile_layer_adversarial.js` hand-copied the code it tested and stayed green through a real URL change. | both re-run |
| `9017e6a` | Both deleted. Also records that the City source is **self-limiting** — it 404s outside the boundary, so the crawl cannot over-reach, where Carto and Esri are global and the coverage polygon was the only guard. | 13,699 failures = 14,061 predicted |
| `60fe7d8` | **Reverted to Esri on operator judgement.** The City's cache is sharper but reads harsh on the bay display; the raw MrSID is blocky at native for the same reason. Attribution corrected to name both parties: City photographs, Esri rendering. | operator, bay display |
| `0552c11` | **#47 closed as accepted risk.** Not resolved — the terms were never read. The gap is stated in the item: City provenance says nothing about Esri's redistribution rights. | — |

### Corrections to my own claims, recorded rather than overwritten

* **z21 is 4.87 cm/px, not 7.46.** I omitted `cos(latitude)` and built a 22 GB archive on the
  wrong number. Then over-corrected to "z21 adds nothing", which was also wrong.
* **`satellite.mbtiles` is not "Esri, not City data".** The photographs are the City's, proven
  by a difference test where every vehicle cancelled out. Wrong on provenance, right on licence.
* **lanczos was the wrong recommendation.** The operator's eye was right; my test had been a
  downsample and the pipeline was upsampling.
* **A monitor raised a false crawl-failure alarm** — `grep -c` prints `0` and exits non-zero,
  so the fallback duplicated a line and shifted every field.

### Also recorded, no separate entry

* **The City's `export` endpoint renders from source, not the cache** — 113× the high-frequency
  content of an upscaled z20 tile. Explains why QtheMap looks good at deep zoom. Unexplored.
* **"Coquitlam Light Grey" is not City data** — Esri Canada's `Canada_Topographic` under an
  ~80 KB City colour theme. Recorded in `PROJECT_IDEAS.md` #11.
* **Two `cfr_tiles` outages, ~6 minutes each, both mine** — long jobs held on an SSH session
  that timed out. Detached, the same operation took 47 seconds.
