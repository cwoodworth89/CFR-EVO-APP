# Street basemap licences — the self-hosted vector map

**Obtained 2026-09-09 for the vector basemap stream**
([`../../briefs/vector_basemap_agent.md`](../../briefs/vector_basemap_agent.md)). Every text in
this directory was fetched from the project it governs on that date and is vendored here
because the kiosk has no WAN at 3 am (`../README.md`, *How to use this*). Punch-list #47b is
what happens when this step is skipped: the Carto street layers were crawled under terms
nobody had read, and Carto answered by watermarking the tiles.

The map is built from four inputs, rendered by two libraries, and drawn with a style
derived from one of two published designs. Each row names what it is, the licence text
held here, and what the licence asks of a map shown on a fire-hall display.

## Register

| Component | What it is | Licence (text held) | What it requires of us | Met where |
|:--|:--|:--|:--|:--|
| OpenStreetMap data | `vancouver.osm.pbf`, the extract the kiosk already routes on (kiosk `backend/data/osrm/`, replication time 2026-08-07 per the tile metadata) | ODbL 1.0 — [`odbl-1.0.txt`](odbl-1.0.txt) | Visible credit to OpenStreetMap; make clear the data is ODbL (OSMF attribution guideline §1.4, excerpt below). A derivative *database* redistributed to others must carry the ODbL (licence §4.4); tiles served inside the department to its own displays are not distributed to a third party | The map's corner credit, *Credit line* below |
| Water polygons | Ocean and sea polygons derived from OSM `natural=coastline`, downloaded by Planetiler from osmdata.openstreetmap.de | ODbL 1.0 (same text) — the source page states *"Data is copyright OpenStreetMap contributors and available under the ODbL"* (read 2026-09-09) | Covered by the OSM credit | Same |
| Lake centrelines | `lake_centerline.shp.zip`, derived from OSM (lukasmartinelli/osm-lakelines) | Code MIT — [`osm-lakelines-LICENSE-mit.txt`](osm-lakelines-LICENSE-mit.txt); data ODbL | Covered by the OSM credit | Same |
| Natural Earth | `natural_earth_vector.sqlite.zip`, used for the z0–z7 layers only | Public domain — the terms-of-use page states *"All versions of Natural Earth raster + vector map data found on this website are in the public domain … No permission is needed to use Natural Earth. Crediting the authors is unnecessary."* (read 2026-09-09) | Nothing | — |
| Planetiler | The tile generator, run as `ghcr.io/onthegomap/planetiler:latest` (build 0.10.3-SNAPSHOT, git `9af0823`, 2026-08-05) | Apache 2.0 — [`planetiler-LICENSE-apache-2.0.txt`](planetiler-LICENSE-apache-2.0.txt) | Nothing for the output; the notice stays with the software | Not redistributed |
| OpenMapTiles schema, via the Planetiler OpenMapTiles profile | The layer names and attributes inside every tile (`transportation`, `building`, `place` …), schema version 3.16.0 | Code BSD 3-Clause, **design CC-BY 4.0** — [`planetiler-openmaptiles-LICENSE.md`](planetiler-openmaptiles-LICENSE.md) (byte-identical to the schema repository's own LICENSE.md, checked 2026-09-09) | Planetiler prints the obligation at the end of every build: *"Maps made with these vector tiles must display a visible credit: © OpenMapTiles © OpenStreetMap contributors"* | The corner credit |
| Positron style (starting point) | `positron-gl-style/style.json`, the vector re-implementation of the Carto *light* design the crews see today | Code BSD 3-Clause, **design CC-BY 4.0** — [`positron-gl-style-LICENSE.md`](positron-gl-style-LICENSE.md) | The visual design is attributed to *MapTiler.com & OpenMapTiles contributors*; a derivative must say it was changed (CC-BY 4.0 §3(a)(1)(B)) | The corner credit names OpenMapTiles; the full notice is this file. **An in-app "Data licences" view is not built** (post-freeze) |
| OSM Bright style (alternative) | `osm-bright-gl-style/style.json`, the Voyager-like design | Same terms — [`osm-bright-gl-style-LICENSE.md`](osm-bright-gl-style-LICENSE.md); derived from Mapbox Open Styles (BSD-3, 2014) | As above | As above |
| Six more candidate designs, vendored 2026-09-09 for the trial gallery so the operator can choose over the same tiles | MapTiler Basic, Dark Matter, Fiord Color, Toner and MapTiler 3D from `github.com/openmaptiles`; OSM Liberty from `github.com/maputnik`. MapTiler 3D was tried and dropped the same day: it draws black blobs on these tiles, being built for MapTiler's own; its licence stays here as the record. **Operator ruling 2026-09-09: Positron, Dark Matter, Fiord Color and Toner are out; OSM Bright, MapTiler Basic and OSM Liberty stay in play.** The licences of the rejected designs stay vendored as the record of what was looked at | Same terms as Positron: BSD 3-Clause code, CC-BY 4.0 design — [`maptiler-basic-gl-style-LICENSE.md`](maptiler-basic-gl-style-LICENSE.md), [`dark-matter-gl-style-LICENSE.md`](dark-matter-gl-style-LICENSE.md), [`fiord-color-gl-style-LICENSE.md`](fiord-color-gl-style-LICENSE.md), [`maptiler-toner-gl-style-LICENSE.md`](maptiler-toner-gl-style-LICENSE.md) (design derived from Stamen Toner, ISC), [`maptiler-3d-gl-style-LICENSE.md`](maptiler-3d-gl-style-LICENSE.md), [`osm-liberty-LICENSE.md`](osm-liberty-LICENSE.md) (BSD code; design CC-BY 3.0 via Mapbox OSM Bright; Maki icons CC0; its Roboto fonts are **not** vendored, Noto Sans stands in) | As for Positron; whichever is chosen becomes the one credited | The corner credit. The others are deleted from the kiosk once the operator has chosen |
| Noto Sans glyphs | `openmaptiles/fonts` release v2.0, `noto-sans.zip`: Regular, Bold, Italic as signed-distance-field PBF ranges (768 files, 102 MB) | SIL OFL 1.1 — [`noto-sans-OFL-1.1.txt`](noto-sans-OFL-1.1.txt) | The font may be bundled and served; it may not be sold on its own; the notice stays with it | Served from the kiosk; notice held here |
| MapLibre GL JS | The renderer, already in `frontend/node_modules` at 4.7.1 as a dependency of `esri-leaflet-vector` (which nothing imports) | BSD 3-Clause — [`maplibre-gl-js-LICENSE-bsd-3.txt`](maplibre-gl-js-LICENSE-bsd-3.txt) | Keep the notice in the distribution | `node_modules`, and here |
| `@maplibre/maplibre-gl-leaflet` | The Leaflet plugin that hosts a MapLibre map under the existing Leaflet layers; 0.1.4, peers `maplibre-gl ^4.3.2` and `leaflet ^1.9.3` | ISC — [`maplibre-gl-leaflet-LICENSE-isc.txt`](maplibre-gl-leaflet-LICENSE-isc.txt) | Keep the notice | Not yet installed |
| mbtileserver | Serves the archive; already the project's tile server | ISC (Conservation Biology Institute, 2014–2024) | Keep the notice | Unchanged |

Metropolis, the font Positron lists first, is also OFL 1.1 (Chris Simpson, 2015) but is
**not vendored**: the trial style keeps only the Noto Sans fallback each layer already names,
so one font family carries the licence. If the operator wants the Metropolis look, fetch it
from the same fonts repository and add its OFL text here.

## Credit line

What the map must show, assembled from the obligations above, in the corner of every map
surface that draws these tiles (OSMF guideline §1.5.2: *"the credit should typically appear
in a corner of the map"*; the hall display has no pointer, so the credit stays visible rather
than collapsing behind an (i)):

```
© OpenMapTiles · © OpenStreetMap contributors (ODbL)
```

* *OpenStreetMap contributors* — the ODbL credit (§1.4: *"The historical forms of attribution
  '© OpenStreetMap contributors' or '© OpenStreetMap' are acceptable"*).
* *(ODbL)* — §1.4 also requires making clear that the data is under the ODbL; an offline
  kiosk cannot link to `openstreetmap.org/copyright`, so the licence is named in the text.
* *OpenMapTiles* — the CC-BY credit Planetiler's own build output asks for, covering the
  schema and the style's design.

## Excerpts, verbatim, read 2026-09-09

**openstreetmap.org/copyright** — *"OpenStreetMap is open data, licensed under the Open Data
Commons Open Database License (ODbL) by the OpenStreetMap Foundation (OSMF). In summary: You
are free to copy, distribute, transmit and adapt our data, as long as you credit OpenStreetMap
and its contributors. If you alter or build upon our data, you may distribute the result only
under the same license."* And under *How to credit OpenStreetMap*: *"Where you use
OpenStreetMap data, you are required to do the following two things: Provide credit to
OpenStreetMap by displaying our attribution notice. Make clear that the data is available
under the Open Database License."*

**OSMF Licence/Attribution Guidelines** (osmfoundation.org/wiki/Licence/Attribution_Guidelines)

* §1.3 *Requirements to fit within OSMF's safe harbour*: *"Attribution must be presented to
  anyone who uses, views, accesses, interacts with, or is otherwise exposed to the map or
  produced work. The attribution format should not require individuals to interact with the
  map or produced work to see the attribution. Attribution must be placed in the vicinity of
  the produced work or in a location where customarily attribution would be expected by the
  users of the produced work. Attribution must be legible and understandable."*
* §1.4 *Attribution text*: *"Attribution must be to 'OpenStreetMap'. Attribution must also
  make it clear that the data is available under the Open Database License. … The text must
  be easily readable and understandable, taking into consideration the font, size, colour,
  contrast, positioning and amount of time that it is visible. … The historical forms of
  attribution '© OpenStreetMap contributors' or '© OpenStreetMap' are acceptable."*
* §1.5.2 *Interactive maps*: *"For a browsable map (e.g., embedded in a web page or
  application), the credit should typically appear in a corner of the map. While the lower
  right corner is traditional, any corner of the map is acceptable. … If the attribution has
  been collapsed, the user must still be able to find the licence information if they look
  for it, for example from an '(i)' button in the corner of the map or an 'About' option in a
  menu."*

**osmdata.openstreetmap.de, water polygons** — *"Data is copyright OpenStreetMap contributors
and available under the ODbL."*

**naturalearthdata.com, Terms of Use** — *"All versions of Natural Earth raster + vector map
data found on this website are in the public domain. You may use the maps in any manner,
including modifying the content and design, electronic dissemination, and offset printing.
… No permission is needed to use Natural Earth. Crediting the authors is unnecessary."*

**Planetiler, printed at the end of every build** —

```
Acknowledgments
Generated vector tiles are produced work of OpenStreetMap data.
Such tiles are reusable under CC-BY license granted by OpenMapTiles team:
- https://github.com/openmaptiles/openmaptiles/#license
Maps made with these vector tiles must display a visible credit:
- © OpenMapTiles © OpenStreetMap contributors
```

## Not covered here

* **The aerial layer** (`ortho.mbtiles`) is Esri's redistribution of the City's 2025 capture
  and stays the accepted risk recorded in punch-list #47b. This directory does not change it.
* **The cadastral overlay** is City data under the Open Government Licence, whose text is
  still a `NOT HELD` row in `../README.md`.
* **Carto** remains the source of `street.mbtiles` and `street_nolabels.mbtiles` until the
  operator says the vector map stays; those archives are unchanged by this stream.
