# Punch list #47b — Basemap tile licensing has never been checked — Carto and Esri

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | operational |
| **Area** | 🧷 Parcel Import Integrity |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L4432 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 47. Basemap tile licensing has never been checked — Carto and Esri
> **Status**: ⚠️ **Open — operator decision required. No code defect; this is a terms question.**

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
