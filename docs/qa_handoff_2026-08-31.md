# QA Handoff — 2026-08-31

**Read this first if you are picking up the mapping/tile thread.** Companion to
[`qa_handoff_2026-08-30.md`](./qa_handoff_2026-08-30.md), which is still correct on the
dispatch pipeline; this covers a single day spent entirely on basemap and imagery layers.

The live work queue is [`debug_and_qa_punchlist.md`](./debug_and_qa_punchlist.md), now at
**24 open** (15 crew-visible).

---

## Where the tiles ended up

```
ortho.mbtiles        8.07 GB   511,118 tiles  z12-20   City photographs, Esri rendering
cadastral.mbtiles    1.04 GB                  z14-20   City ArcGIS, OGL
street.mbtiles       0.21 GB                  z12-18   Carto, watermark-free
street_nolabels      0.17 GB                  z12-18   Carto, watermark-free
```

Four services. `satellite` is gone as a name; the aerial layer is `ortho`. Disk 404 GB free.

**The day ended roughly where it started on the aerial layer** — Esri tiles, served offline —
but not unchanged. It is now correctly named, honestly attributed, and its provenance is
established by measurement rather than assumption. Two things are genuinely better:
162,064 watermarked Carto tiles are gone, and the pipeline can crawl the City directly if
that call is ever revisited.

---

## The one fact that reframes everything

**Esri World Imagery over Coquitlam *is* the City's own 2025 7.5cm capture.**

Proven by differencing the two at a car park: every vehicle cancelled out, mean absolute
difference 12.5/255, not one car-shaped ghost. Two flights days apart cannot put the same
cars in the same stalls. The City contributes to Esri's community programme, Esri ingests it,
and both then publish the same photographs with different processing.

This kills the framing the whole day started with — "third-party Esri imagery versus
authoritative City orthos." **There was never a content difference.** What differs is
processing quality and which licence you hold it under. Everything downstream of that
misunderstanding cost time.

The operator reached this by inspection (ArcGIS, Google and QtheMap screenshots side by side)
before it was measured. Google is a genuinely different capture — different season, different
vehicles — which is what made the ArcGIS/QtheMap match conspicuous.

---

## What shipped

| | |
|:--|:--|
| **Carto watermarking found** | Carto now stamps every unauthenticated tile `API KEY REQUIRED`, z14–z20, verified live |
| **162,064 watermarked tiles deleted** | the entire z19 level from both street layers; `max_zoom` back to 18; 536 MB reclaimed |
| **Metadata corrected** | both street archives declared `maxzoom 19` for content they no longer held |
| **Orthos found never ingested** | `satellite.mbtiles` was Esri end to end while the UI attributed it to the City |
| **MrSID pipeline retired** | `ingest_coquitlam_orthos.py`, `precache_satellite_tiles.py`, `ingest_tms_ortho_tiles()`, `--raw-ortho-dir` all deleted |
| **City imagery crawl built** | `compile_mbtiles.py --layer ortho` crawls `CachedServices/Imagery_2025`, rate-limited to ~20 req/s |
| **#47 closed** | as **accepted risk**, not resolved — see below |
| **~69 GB reclaimed** | MrSID staging, GDAL images, and the two parked archives |

**Rejected after being built and deployed:** the City's own imagery cache. It is measurably
sharper (1344 vs Esri's 664 edge energy at z20) but the operator judged the sharpening harsh
on the bay display and adding no detail a crew can act on. Rejected on visual grounds, not
licensing. `compile_mbtiles.py --layer ortho` still points at it; ~6 hours to rebuild.

---

## Corrections — five of my own claims were wrong

The 08-30 handoff opened with the same kind of table. It should be a standing feature.

| I claimed | It actually was |
|:--|:--|
| z21 is 7.46 cm/px, "pixel-for-pixel with the 7.5 cm source" | **4.87 cm/px.** I used EPSG:3857 units and omitted `cos(latitude)`. z21 *upsamples*. A 22 GB archive was built on that number |
| Then: "z21 adds nothing over z20" | Over-corrected. z21 preserves detail z20 discards — but only with a kernel that does not blur it away |
| The City's tile is sharper than ours | True, but I said it from byte size and a side-by-side whose panels did not cover the same ground |
| lanczos is the crispest resampling | The operator's eye disagreed and was right. That test was a *downsample*; the pipeline was *upsampling*. Different operation, result does not transfer |
| `satellite.mbtiles` is Esri, **not City data** | The photographs are the City's. Wrong on provenance, right on licence |

Also: a monitor I wrote raised a false "crawl died" alarm. `grep -c` prints `0` *and* exits
non-zero, so a `|| echo 0` fallback emitted a duplicate line and shifted every field. It read
exactly like a real failure.

**The pattern in all of these is the same** — a plausible number accepted without checking the
operation it described. §7.3a, applied to arithmetic rather than to a library.

---

## Two checks that were worse than useless, now deleted

**`verify_ortho_provenance.py`** passed when a tile *differed* from Esri, on the premise that
this proved City provenance. Once Esri was shown to serve the same photographs, difference
proved only different processing — so it returned a confident PASS on a question it could not
decide. Written and deleted within 48 hours.

**`frontend/test_tile_layer_adversarial.js`** hand-copied `getTileUrl` instead of importing it,
because `apiClient.js` is an ES module reading `import.meta.env`. When the aerial layer moved
to `/services/ortho` across three files, **all 23 assertions stayed green against the old
URL.** There is no test runner in the frontend and nothing referenced the file.

Both are the same failure: a check that cannot fail when the thing it guards breaks.

---

## #47 closed as accepted risk — read the distinction

**Neither Carto's nor Esri's terms were ever read.** The exposure was measured, cut where
cheap, and knowingly accepted where not.

**Accepted:** the aerial layer is Esri World Imagery stored offline on municipal hardware. The
reasoning — photographs are demonstrably the City's, Esri serves them unauthenticated and
unwatermarked, City data is OGL. **The gap, stated in the item:** the City producing the source
says nothing about Esri's rights over *their* redistribution of it.

**Still present:** ~5,600 watermarked Carto tiles per layer at z18 and ~1,400 at z17, in the
western strip. Kept deliberately — deleting them blanks the basemap over Austin Heights,
Maillardville and Burquitlam at working zoom, reopening #40.

Reopens on: Esri watermarking or key-gating, a licence review, `PROJECT_IDEAS.md` #11 landing,
or the City publishing `Imagery_2026`.

---

## Things that will bite you

**Ground resolution is `156543.03 / 2**z * cos(latitude)`.** Dropping the cosine gives a number
that looks right and is wrong by 1.5×. This cost a day.

**Never hold a long kiosk job on an SSH session.** I took `cfr_tiles` down twice — six minutes
each — because a finalize outran a two-minute SSH timeout. Detached with `setsid nohup` and a
`trap` for the restart, the same operation took 47 seconds. Every long job here should be
detached from the start.

**`pkill -f <pattern>` matches your own SSH command line.** `pkill -f ortho_build.sh` killed
the wrapper *and* the session that issued it. Use a bracket trick: `pgrep -f 'compile_mbtile[s]'`.

**`mbtileserver` lists archives by their metadata `name`, not the filename.** A renamed archive
served correctly at the new path while the catalogue still advertised the old name. Same class
as #40: metadata outliving its content.

**`finalize_mbtiles.py` is hardened now** — it used to abort the whole run on one `chmod`
failure, silently skipping later archives. An archive written by a container is owned by root,
which is exactly what triggered it.

**A frontend deploy is not finished until the kiosk tab is hard-reloaded** (`Ctrl+Shift+R`).
Unchanged from yesterday, still true, still #44b.

**Other agents commit this worktree.** My work was swept into three other agents' commits
today. Stage by explicit path, never `git add -A`.

---

## Open

* **`PROJECT_IDEAS.md` #11** — self-hosted OSM vector basemap, high priority, frozen. Now
  carries a cheaper path: dropping tilt and 3D removes the renderer migration entirely, leaving
  a Planetiler build rendered to raster into the existing archive filenames. Roughly a day.
  Open question recorded: whether roads and places need independent toggles.
* **"Coquitlam Light Grey" investigated and rejected** — it is Esri Canada's
  `Canada_Topographic` with an ~80 KB City colour theme over it. No City geometry. Recorded in
  #11 along with the useful part: render City `public.roads` and `public.parcels` inside the
  boundary, OSM only beyond it.
* **The City `export` endpoint renders from source, not the cache** — measured 113× the
  high-frequency content of an upscaled z20 tile. That is why QtheMap looks good at deep zoom
  and a z20 archive does not. Unexplored; it is the answer if stair-stepping past z20 ever
  becomes the complaint.

---

## Verified state at handoff

```
Tile services      ortho, cadastral, street, street_nolabels  (all journal=delete, no WAL)
ortho.mbtiles      8.07 GB   511,118 tiles   z12-20
Disk free          404 GB
cfr_tiles          Up, healthy
Punch list         24 open (15 crew-visible), 47 closed
Frontend           rebuilt on kiosk -- HARD RELOAD REQUIRED
```

The aerial archive carries bleed into Port Moody, Belcarra and Anmore — it was crawled to the
bounding box rather than the municipal polygon. **Accepted deliberately** and useful for mutual
aid, recorded here so it is not later mistaken for a filter bug.
