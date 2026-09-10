"""Generate the project's street basemap style from the vendored OSM Bright style.

    python tools/build_basemap_style.py            # writes frontend/public/basemap/street.style.json
    python tools/build_basemap_style.py --check    # exit 1 if the committed file is stale

The style is a committed artefact; this script is its provenance. Every departure from
upstream below carries the ruling it came from, all from the operator on the trial page,
2026-09-09 (docs/briefings/vector_basemap_trial_2026-09-09.md). Upstream is
frontend/public/basemap/upstream/osm-bright.style.json (openmaptiles/osm-bright-gl-style,
BSD 3-Clause code, CC-BY 4.0 design; docs/standards/basemap/README.md).

The output carries two placeholders the app fills at load time
(frontend/src/components/map/vectorBasemap.js): {{TILEJSON_URL}} for the tile server's
TileJSON and {{ASSETS_URL}} for the directory this style, its sprite and the glyphs are
served from. Nothing in the file names a host.
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPSTREAM = os.path.join(ROOT, 'frontend', 'public', 'basemap', 'upstream', 'osm-bright.style.json')
OUTPUT = os.path.join(ROOT, 'frontend', 'public', 'basemap', 'street.style.json')
VALIDATOR = os.path.join(ROOT, 'frontend', 'node_modules', '@maplibre', 'maplibre-gl-style-spec', 'dist', 'gl-style-validate.mjs')

# --- Rulings -------------------------------------------------------------------------------

# Operator, 2026-09-09, choosing on the trial page: "it looks like I'm going to want OSM
# Bright." Positron (the crews' current light look), Dark Matter, Fiord Color and Toner out.

# Symbol layers, from the operator's screenshot of the trial page's layer panel (2026-09-09).
# Ticked: waterway-name, water-name-other, road_oneway, road_oneway_opposite, poi-level-1/2/3,
# highway-name-path, highway-name-minor, highway-name-major. Everything else off. The three
# place layers below the screenshot's edge (country-2, country-1, continent) are assumed off
# with the rest of the place-* group; every place layer that was visible was unticked.
SYMBOL_LAYERS_OFF = [
    'water-name-lakeline', 'water-name-ocean', 'poi-railway',
    'highway-shield', 'highway-shield-us-interstate', 'highway-shield-us-other',
    'airport-label-major',
    'place-other', 'place-village', 'place-town', 'place-state', 'place-city',
    'place-city-capital', 'place-country-other', 'place-country-3', 'place-country-2',
    'place-country-1', 'place-continent',
]

# POI classes the operator listed (2026-09-09): "Bus Bay #'s (but only at zoom 16 and
# nearer), Library, Ice_hockey, fire_station, hospital, swimming_pool, police". Each entry is
# a MapLibre expression over the feature; the class names are the OpenMapTiles `poi` layer's,
# counted over the whole extract by the trial's catalogue (poi_classes.py, 190,505 points):
#   library 354 (subclass library 179, books 175)      -> bookshops excluded
#   hospital 818 (clinic 772, hospital 40, nursing_home 6) -> clinics excluded
#   swimming_pool 9,390 (only 23 named)               -> the unnamed are private backyard pools
#   ice_rink 69, ice_hockey 2                          -> both kept for "Ice_hockey"
#   fire_station 208, police 134                       -> as they are
# The three narrowings are the author's reading of "clutter", not a ruling; each is one line.
NAME = ['coalesce', ['get', 'name'], '']
POI_CLASS_RULES = [
    ['all', ['==', ['get', 'class'], 'library'], ['==', ['get', 'subclass'], 'library']],
    ['all', ['==', ['get', 'class'], 'hospital'], ['in', ['get', 'subclass'], ['literal', ['hospital', 'nursing_home']]]],
    ['all', ['==', ['get', 'class'], 'swimming_pool'], ['!=', NAME, '']],
    ['==', ['get', 'class'], 'ice_rink'],
    ['==', ['get', 'class'], 'ice_hockey'],
    ['==', ['get', 'class'], 'fire_station'],
    ['==', ['get', 'class'], 'police'],
]

# The bus-loop bays. Operator: "I don't want bus stops, but the bus loop at coquitlam centre
# bus loop has the Bay numbers, and that's extremely useful" and "I would probably accept any
# bus stop with the name 'Bay' in it" -- only at zoom 16 and nearer. The extract holds 967
# bus stops with "Bay" in the name, and "Bay" alone also admits "Nelson Ave (SB) at Bay St",
# "Horseshoe Bay Ferry Terminal" and every Bayswater stop (poi_names.py census); "Bay" followed
# by a digit keeps the numbered bays at Coquitlam Central, Lincoln, Lafarge Lake-Douglas and
# Inlet Centre and nothing else. The style language has no regular expressions, hence ten tests.
BAY_MIN_ZOOM = 16
BAY_RULE = ['all', ['==', ['get', 'class'], 'bus'],
            ['any', *[['>=', ['index-of', f'Bay {d}', NAME], 0] for d in range(10)]]]
# "Coquitlam Central Station Bay 9" -> "Bay 9": the station is already named on the map.
BAY_AT = ['index-of', 'Bay ', NAME]
BAY_TEXT = ['case', ['>=', BAY_AT, 0], ['slice', NAME, BAY_AT], NAME]

# Icons: Bright's sprite names icons "<class>_11" and lacks three of ours (checked against
# sprite.json 2026-09-09). swimming_pool draws the sprite's swimming icon; the two rink
# classes draw the stadium icon until the project has a sprite of its own.
ICON = ['match', ['get', 'class'],
        'swimming_pool', 'swimming_11',
        'ice_rink', 'stadium_11',
        'ice_hockey', 'stadium_11',
        ['concat', ['get', 'class'], '_11']]

# Only Noto Sans Regular, Bold and Italic are vendored (SIL OFL 1.1); Bright names only those.
FONTS = {'Noto Sans Regular', 'Noto Sans Bold', 'Noto Sans Italic'}


# --- Legacy filter syntax -> expressions ---------------------------------------------------
# Bright's filters are legacy syntax, which cannot share an "all" with expression tests.
# The forms converted here are every form the Bright POI layers use.

def key(k):
    return ['geometry-type'] if k == '$type' else ['id'] if k == '$id' else ['get', k]


def legacy_to_expr(f):
    op = f[0]
    if op in ('all', 'any'):
        return [op, *(legacy_to_expr(g) for g in f[1:])]
    if op == 'none':
        return ['!', ['any', *(legacy_to_expr(g) for g in f[1:])]]
    if op in ('==', '!=', '<', '<=', '>', '>=') and len(f) == 3 and isinstance(f[1], str):
        return [op, key(f[1]), f[2]]
    if op == 'has' and len(f) == 2:
        return ['has', f[1]]
    if op == '!has' and len(f) == 2:
        return ['!', ['has', f[1]]]
    if op == 'in' and isinstance(f[1], str):
        return ['in', key(f[1]), ['literal', list(f[2:])]]
    if op == '!in' and isinstance(f[1], str):
        return ['!', ['in', key(f[1]), ['literal', list(f[2:])]]]
    raise ValueError(f'legacy filter form not handled: {json.dumps(f)[:80]}')


# --- Build ---------------------------------------------------------------------------------

def build() -> dict:
    style = json.load(open(UPSTREAM, encoding='utf-8'))
    style['name'] = 'CFR EVO street'
    style['sources'] = {'openmaptiles': {'type': 'vector', 'url': '{{TILEJSON_URL}}'}}
    style['glyphs'] = '{{ASSETS_URL}}/fonts/{fontstack}/{range}.pbf'
    style['sprite'] = '{{ASSETS_URL}}/sprite'

    background = next(l for l in style['layers'] if l['type'] == 'background')
    style['layers'] = [l for l in style['layers'] if l['type'] != 'background']

    for layer in style['layers']:
        fonts = layer.get('layout', {}).get('text-font')
        if fonts is not None:
            unknown = set(fonts) - FONTS
            if unknown:
                raise SystemExit(f'{layer["id"]}: font not vendored: {unknown}')
        if layer['type'] == 'symbol' and layer['id'] in SYMBOL_LAYERS_OFF:
            layer.setdefault('layout', {})['visibility'] = 'none'

    poi_layers = [l for l in style['layers'] if l.get('source-layer') == 'poi' and l['type'] == 'symbol']
    template = next(l for l in poi_layers if l['id'] == 'poi-level-1')
    for layer in poi_layers:
        if layer['id'] in SYMBOL_LAYERS_OFF:
            continue
        base = legacy_to_expr(layer['filter'])
        layer['filter'] = ['all', base, ['any', *POI_CLASS_RULES]]
        layer['layout']['icon-image'] = ICON

    bay = copy.deepcopy(template)
    bay['id'] = 'poi-bus-bay'
    bay['minzoom'] = BAY_MIN_ZOOM
    bay['filter'] = ['all', ['==', ['geometry-type'], 'Point'], BAY_RULE]
    bay['layout']['text-field'] = BAY_TEXT
    bay['layout']['icon-image'] = 'bus_11'
    top = max(i for i, l in enumerate(style['layers']) if l in poi_layers)
    style['layers'].insert(top + 1, bay)

    road_names = [l['id'] for l in style['layers']
                  if l['type'] == 'symbol' and l.get('source-layer') == 'transportation_name'
                  and l.get('layout', {}).get('visibility') != 'none']
    labels_on = [l['id'] for l in style['layers']
                 if l['type'] == 'symbol' and l.get('layout', {}).get('visibility') != 'none']
    style['metadata'] = {
        'cfr:generated-by': 'tools/build_basemap_style.py',
        'cfr:upstream': 'openmaptiles/osm-bright-gl-style style.json (BSD-3 code, CC-BY 4.0 design), fonts Noto Sans (OFL)',
        'cfr:rulings': 'operator, 2026-09-09; docs/briefings/vector_basemap_trial_2026-09-09.md',
        # The app paints this colour over the tileset's own bounds and nothing outside them,
        # so a zoom or place with no tile shows the "no map data" hatch (punch-list #40).
        'cfr:background': background['paint']['background-color'],
        # Layers the cadastral overlay duplicates from zoom 14 (its tiles carry road names and
        # civic numbers); the app caps these at CADASTRAL_MIN_ZOOM while that overlay is on.
        'cfr:road-name-layers': road_names,
        # Every label the operator left on; the app's labels-off state hides exactly these.
        'cfr:labels-on': labels_on,
    }
    return style


def validate(path: str) -> None:
    node = shutil.which('node')
    if not node or not os.path.exists(VALIDATOR):
        print('validator not available (node or frontend/node_modules missing); not validated')
        return
    # The placeholders are not URLs; validate a copy with them filled in.
    filled = open(path, encoding='utf-8').read().replace('{{TILEJSON_URL}}', 'http://tiles/services/street_vector').replace('{{ASSETS_URL}}', 'http://app/basemap')
    tmp = path + '.validate.json'
    open(tmp, 'w', encoding='utf-8').write(filled)
    try:
        r = subprocess.run([node, VALIDATOR, tmp], capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f'style does not validate:\n{r.stdout}{r.stderr}')
        print('validates against the MapLibre style spec')
    finally:
        os.remove(tmp)


def main() -> int:
    style = build()
    text = json.dumps(style, indent=1, ensure_ascii=False) + '\n'
    if '--check' in sys.argv:
        current = open(OUTPUT, encoding='utf-8').read() if os.path.exists(OUTPUT) else ''
        if current != text:
            print(f'{os.path.relpath(OUTPUT, ROOT)} is stale: run tools/build_basemap_style.py')
            return 1
        print('street.style.json is current')
        return 0
    open(OUTPUT, 'w', encoding='utf-8', newline='\n').write(text)
    n_sym = sum(1 for l in style['layers'] if l['type'] == 'symbol')
    n_off = sum(1 for l in style['layers'] if l['type'] == 'symbol' and l.get('layout', {}).get('visibility') == 'none')
    print(f'wrote {os.path.relpath(OUTPUT, ROOT)}: {len(style["layers"])} layers, {n_sym} symbol layers of which {n_off} off, '
          f'{len(style["metadata"]["cfr:road-name-layers"])} road-name layers capped under the cadastral overlay')
    validate(OUTPUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
