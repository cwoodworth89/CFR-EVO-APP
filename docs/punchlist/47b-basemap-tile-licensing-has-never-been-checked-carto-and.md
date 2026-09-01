# Punch list #47b — Basemap tile licensing has never been checked — Carto and Esri

| | |
|:--|:--|
| **Status** | CLOSED — accepted risk, 2026-08-31 |
| **Severity** | operational |
| **Area** | 🧷 Parcel Import Integrity |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L4432 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 47. Basemap tile licensing has never been checked — Carto and Esri
> **Status**: ✅ **CLOSED 2026-08-31 as ACCEPTED RISK — operator decision.**
> Not resolved. The terms were never read; the exposure was weighed and accepted.
> See *Closure* at the foot of this item for what was accepted and what would reopen it.

Raised by the operator asking whether pre-crawled tiles need API keys and whether anything was
watermarked. **Neither.** Checked against `compile_mbtiles.py`:

| Layer | Source | API key |
|:--|:--|:--|
| `street`, `street_nolabels` | `basemaps.cartocdn.com` (Carto Voyager / light, OSM-derived) | **none** |
| `satellite` | `server.arcgisonline.com` Esri World Imagery (Maxar-sourced) | **none** |
| `cadastral` | City of Coquitlam ArcGIS MapServer | none |
| 7.5 cm orthophotos | City of Coquitlam S3 | none |

Every source is unauthenticated. Once crawled, the tiles are static PNG/JPG inside SQLite
MBTiles served locally by `mbtileserver` — **nothing phones home at runtime**, which is the
offline architecture working as designed. These endpoints either serve a real tile or serve
nothing; there is no degraded or watermarked tier to fall into, so the archives hold genuine
imagery.

**The real exposure is licensing.** The project has bulk-downloaded roughly **789,000 tiles
from Carto** and **431,000 from Esri** and stored them permanently for offline redistribution
on municipal equipment. Neither provider's terms have been read. Bulk pre-caching for
redistribution is the use such terms most commonly restrict, and the Esri imagery is
Maxar-sourced with its own conditions on top.

**The City layers are not in question** — orthophotos and cadastral are covered by the Open
Government Licence, which is exactly why they can be cached indefinitely.

#### Options, roughly in order of soundness

1. **Read the two sets of terms.** This may well be permitted; nobody knows yet, and that is
   the whole problem (§7.2 — do not improvise a domain model, and licensing is a domain).
2. **Self-host the street basemap from raw OSM** (Protomaps / OpenMapTiles). OSM data is ODbL,
   so rendering and caching your own tiles removes Carto from the picture entirely. Highest
   effort, lowest ongoing risk, and it fits the offline-first architecture better than
   depending on a third-party CDN's goodwill.
3. **Licence Esri imagery for offline use**, or drop regional satellite and rely on the City
   7.5 cm orthophotos inside the municipal boundary — which is where crews actually operate.
   The orthos are already the higher-resolution source there.
4. **Status quo, recorded as an accepted risk** with a decision and a date, the way the Street
   View exemption now is.

Recorded as a gap in [`docs/standards/README.md`](../standards/README.md) per §7.5.

#### Resolved in direction, 2026-08-30

**Carto answered the licensing question itself.** It now stamps every unauthenticated tile
`API KEY REQUIRED` — verified live from the kiosk, z14 through z20. The 2026-08-27 re-crawl
fetched 81,032 z19 tiles per street layer after that change; all watermarked, as is the
western z17/z18 fill from the #40 gap closure.

The map-source review the operator asked for, with what was decided:

| Layer | Source | Outcome |
|:--|:--|:--|
| `street`, `street_nolabels` | Carto CDN | **Replace** — self-hosted OSM vector, `PROJECT_IDEAS.md` #11 |
| `satellite` | Esri World Imagery | **Superseded inside the city** by the 7.5cm orthos |
| `ortho` | City of Coquitlam `Imagery_2025` service | **Crawled 2026-08-31** — OGL. The MrSID ingest of 2026-08-30 was replaced: the City's own tiles are sharper than anything built locally from the raw SID. |
| `cadastral` | City ArcGIS | unchanged, OGL |

The City hosts its own cached tile services at `geodata.coquitlam.ca` (`Imagery_1963`
through `Imagery_2025`, `Topographic`, EPSG:3857, `© City of Coquitlam`). `Imagery_2025` is
the **same capture** as the 7.5cm zip — confirmed by identical vehicles and shadows in the
same parking stalls — and is a legal alternative source for the aerial layer.
`Topographic` is contour linework, **not** a street basemap, so it cannot replace Carto.

**Interim exposure**: z19 has been dropped from both street layers (operator decision,
they were specified z12–18 and never wanted deeper), removing ~162,000 watermarked tiles.
Roughly **5,600 watermarked z18 tiles per layer remain** in the western strip until the
OSM migration lands. Recorded, not hidden.

**Still unread**: Carto's and Esri's actual terms, and ODbL. The conclusions above follow
from how OGL works and from Carto's own enforcement behaviour, not from the licence text.

---

## 🧾 Session batch, 2026-08-29/30 — XStreets, rounds, and the confidence ruling

Recorded so the fixes below are findable by symptom, not only by commit. Every one was
measured against the live kiosk or the corpus before and after (§6.6).

---

## Closure — accepted risk, operator decision 2026-08-31

**This item is closed as an accepted risk, not as a resolved question.** Neither Carto's nor
Esri's terms of service were ever read. What changed is that the exposure was measured,
reduced where it was cheap to reduce, and then knowingly accepted where it was not.

### What was actually resolved

**Carto is gone from the deep zooms, and that part is genuinely fixed.** Carto now stamps
every unauthenticated tile `API KEY REQUIRED` — verified live from the kiosk across z14–z20.
The 2026-08-27 re-crawl had pulled 81,032 z19 tiles per street layer after that policy change.
**All 162,064 were deleted 2026-08-31**, `max_zoom` was returned to 18, and each archive's
metadata `maxzoom` was corrected so it no longer describes content that is absent.

Residual: roughly **5,600 watermarked tiles per layer at z18** and **1,400 at z17**, in the
western strip added by that re-crawl. Deliberately retained — deleting them would blank the
basemap over Austin Heights, Maillardville and Burquitlam at working zoom, reopening the #40
gap. A visible hole over a third of the city is worse than the residue, and
`PROJECT_IDEAS.md` #11 replaces the layer wholesale.

### What is being accepted

The aerial layer (`ortho.mbtiles`, 511,118 tiles) is **Esri World Imagery, crawled and stored
offline on municipal hardware.** Esri's terms govern that redistribution and have not been
read.

The reasoning the operator accepted it on, stated so it can be re-examined:

* **The photographs are the City's own.** Proven 2026-08-31 by differencing a car park against
  the City's `Imagery_2025` service: every vehicle cancelled out, mean absolute difference
  12.5/255, not one car-shaped ghost. Esri's World Imagery over Coquitlam is the City's 2025
  7.5cm capture, contributed through Esri's community programme — not an independent survey.
* The City participates in that programme, and its data is published under the Open Government
  Licence.
* Esri serves these tiles **unauthenticated and unwatermarked**, which is a materially
  different posture from Carto's active enforcement.
* Bleed beyond the municipal polygon (this archive was crawled to the bounding box, so it
  covers Port Moody, Belcarra and Anmore) is accepted on the same reasoning and is useful for
  mutual aid.

**The gap in that reasoning, recorded honestly:** the City producing the source does not speak
to Esri's rights over *their* redistribution of it. That is the unread part, and it is what is
being accepted rather than answered.

### What would reopen this

* Esri beginning to watermark, key-gate or rate-limit the imagery — the signal Carto gave.
* A licence review that reaches a different conclusion.
* `PROJECT_IDEAS.md` #11 landing, which removes Carto entirely and would make revisiting the
  aerial layer cheap.
* The City publishing `Imagery_2026`, since a fresh crawl is a fresh decision.

**A cleaner alternative exists and was rejected on visual grounds, not licensing.** The City's
own `Imagery_2025` cache is unambiguously OGL, self-limiting at the municipal boundary, and
measurably sharper (1344 vs 664 edge energy at z20). It was crawled, deployed, and rejected
because its sharpening reads as harsh on the bay display and adds no detail a crew can act on.
`compile_mbtiles.py --layer ortho` still points at it; the archive is ~6 hours to rebuild.
