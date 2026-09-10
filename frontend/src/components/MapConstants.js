// Map & Layer Constants
import { TILE_BASE_URL, API_BASE_URL } from '../apiClient';

// 🏙️ CITY CENTER & SYMMETRIC OPERATIONAL BOUNDS (Centered at Hall 1 - Town Centre Fire Hall: -122.7907)
export const COQUITLAM_CENTER = [49.2838, -122.7907];

export const OPERATIONAL_BOUNDS = [
  [49.0838, -123.0507], // Southwest: Symmetric regional boundary
  [49.4838, -122.5307]  // Northeast: Symmetric regional boundary
];

// 🗺️ BASE LAYERS (100% Offline Local Pre-Cached Basemaps via mbtileserver on port 8081)
// Serves directly from containerized local MBTiles server (cfr_tiles) with zero WAN dependencies
// Where the cadastral tile set begins: read from the tile server's own metadata
// (`/services/cadastral`: minzoom 14, maxzoom 20, checked 2026-09-08), not chosen. Below
// it there are no parcel lines on the map, so the target parcel's soft shading, which is
// meant to sit inside those lines, is not drawn either (operator, 2026-09-08: "the soft
// shading should only appear when the cadastral layer kicks on. That looks messy").
export const CADASTRAL_MIN_ZOOM = 14;

export const BASE_LAYERS = {
  // THE street basemap. There is one, and this is it.
  //
  // There were five names for two tile sets: GREY and DARK both pointed at
  // street_nolabels, OSM and VOYAGER both at street. Callers picked a name and
  // inherited a labels decision they were not making on purpose, and the labels
  // decision is the only thing that ever actually differed. It is now a boolean --
  // BaseMap's `useLabelsFallback` swaps the `_nolabels` segment out of the URL below --
  // so switching what "street" means is this one entry (operator, 2026-09-08).
  STREET: {
    type: 'tile',
    url: `${TILE_BASE_URL}/services/street_nolabels/tiles/{z}/{x}/{y}.png`,
    fallbackUrl: null, // 100% pure offline local pre-cached tiles
    attribution: '© OpenStreetMap contributors & Carto (100% Offline Local Cache)',
    subdomains: ['a', 'b', 'c'],
    // z18: the deepest zoom crawled for the Carto street styles (operator
    // decision 2026-08-30, punch-list #47). Leaflet upscales past this, so the
    // map still zooms to maxZoom 22 -- it just stops requesting new tiles. Must
    // match "max_zoom" for street/street_nolabels in compile_mbtiles.py.
    maxNativeZoom: 18,
    maxZoom: 22,
  },
  // Aerial imagery, served from `ortho.mbtiles` at /services/ortho.
  //
  // The PHOTOGRAPHS are the City of Coquitlam's 2025 7.5cm orthophotography.
  // The RENDERING is Esri's. Proven 2026-08-31 by differencing a car park: every
  // vehicle cancelled out, mean absolute difference 12.5/255, so Esri's World
  // Imagery over Coquitlam is the City's own capture contributed through Esri's
  // community programme -- not an independent survey.
  //
  // The City also publishes its own tile cache of the same capture, and it is
  // measurably sharper. It was crawled, deployed and then rejected: its
  // sharpening reads as harsh on the bay display and adds no detail a crew can
  // use (operator decision 2026-08-31). Esri's gentler processing was preferred
  // on the display that matters. That archive has been deleted; it is
  // reproducible in ~6 h with `compile_mbtiles.py --layer ortho`, which still
  // points at the City service -- see gis-pipeline-sync 4.1.
  //
  // Licensing is NOT settled: Esri's terms govern Esri's redistribution and have
  // not been read. Accepted as a known risk, not resolved -- punch-list #47.
  SATELLITE: {
    type: 'tile',
    url: `${TILE_BASE_URL}/services/ortho/tiles/{z}/{x}/{y}.jpg`,
    fallbackUrl: null, // 100% pure offline local pre-cached tiles
    attribution: 'Imagery © City of Coquitlam 2025 (7.5cm ortho), served via Esri World Imagery — Offline Local Cache',
    subdomains: ['a', 'b', 'c'],
    // z20 is the deepest level held. Leaflet upscales past it to maxZoom 22.
    maxNativeZoom: 20,
    maxZoom: 22
  },
  CADASTRAL: {
    type: 'tile',
    url: `${TILE_BASE_URL}/services/cadastral/tiles/{z}/{x}/{y}.png`,
    fallbackUrl: null, // 100% pure offline local pre-cached tiles
    attribution: 'City of Coquitlam Cadastral (100% Offline Local Cache)',
    subdomains: ['a', 'b', 'c'],
    maxNativeZoom: 20,
    maxZoom: 22
  }
};

export const MODE_DEFAULTS = {
  EXPLORE: "STREET",
  DRIVER_SETUP: "STREET",
  ADMIN_DISPATCHES: "STREET"
};

// Emergency Unit Colors
export const UNIT_COLORS = {
  ENGINE: "#ef4444",
  LADDER: "#f97316",
  RESCUE: "#3b82f6",
  CHIEF: "#eab308",
  DEFAULT: "#10b981"
};

// 🚒 COQUITLAM FIRE HALLS
// Official municipal civic addresses with verified driveway front-apron GPS coordinates for emergency routing
export const STATIONS = [
  {
    id: "1",
    hall: 1,
    name: "Town Centre Fire Hall (Hall 1)",
    address: "1300 Pinetree Way",
    coords: [49.29109654571679, -122.79072561861948] // Front apron driveway GPS
  },
  {
    id: "2",
    hall: 2,
    name: "Mariner Fire Hall (Hall 2)",
    address: "775 Mariner Way",
    coords: [49.2622197420057, -122.81747986099539] // Front apron driveway GPS
  },
  {
    id: "3",
    hall: 3,
    name: "Austin Heights Fire Hall (Hall 3)",
    address: "438 Nelson Street",
    coords: [49.24803974681661, -122.86546062387211] // Front apron driveway GPS
  },
  {
    id: "4",
    hall: 4,
    name: "Burke Mountain Fire Hall (Hall 4)",
    address: "3501 David Ave",
    coords: [49.29510006403205, -122.74247651791484] // Front apron driveway GPS
  }
];

export const STATIONS_MAP = STATIONS.reduce((acc, stn) => {
  acc[stn.id] = stn.coords;
  return acc;
}, {});

// Hall colours: the one table for every place a hall is coloured -- zone fills, route lines,
// the unit dots in the ETA list -- so they cannot disagree. Chosen 2026-09-09 for separation
// from each other and from the NFPA 291 hydrant badges (sky, green, orange, light red); the
// operator asked for "4 colors that look nice" and judges them on the kiosk.
export const HALL_COLOURS = {
  "1": "#e11d48", // rose      -- Town Centre
  "2": "#2563eb", // royal blue -- Mariner
  "3": "#0d9488", // teal      -- Austin Heights
  "4": "#7c3aed", // violet    -- Burke Mountain
};
export const UNASSIGNED_HALL_COLOUR = "#475569"; // slate
export const hallColour = (id) => HALL_COLOURS[String(id)] || UNASSIGNED_HALL_COLOUR;

// 🏢 KNOWN BUILDING COMPLEXES & HIGH-RISE REGISTRY
// Pre-configured building names, exact tower footprints, and verified front-entrance routing access points
export const KNOWN_BUILDINGS = [
  {
    name: "Grand Central 2",
    address: "2968 Glen Dr, Coquitlam",
    aliases: ["GRAND CENTRAL 2", "GRAND CENTRAL TWO", "2968 GLEN", "2968 GLEN DR"],
    lat: 49.282800,
    lng: -122.796800, // Exact West Tower Footprint for 2968 Glen Dr facing Glen Dr
    frontEntrance: [49.282800, -122.796800], // Glen Dr West Front Entrance
    note: "Highrise Tower (West Block) — Main Front Entrance on Glen Dr"
  },
  {
    name: "Grand Central 1",
    address: "2978 Glen Dr, Coquitlam",
    aliases: ["GRAND CENTRAL 1", "GRAND CENTRAL ONE", "2978 GLEN", "2978 GLEN DR"],
    lat: 49.282800,
    lng: -122.794600, // Exact East Tower Footprint facing Glen Dr / Pinetree Way
    frontEntrance: [49.282800, -122.794600],
    note: "Highrise Tower (East Block) — Front Entrance on Glen Dr / Pinetree Way"
  },
  {
    name: "Grand Central 3",
    address: "2975 Atlantic Ave, Coquitlam",
    aliases: ["GRAND CENTRAL 3", "GRAND CENTRAL THREE", "2975 ATLANTIC", "2975 ATLANTIC AVE"],
    lat: 49.281300,
    lng: -122.795600, // Exact South Tower Footprint facing Atlantic Ave
    frontEntrance: [49.281300, -122.795600],
    note: "Highrise Tower (South Block) — Front Entrance on Atlantic Ave"
  },
  {
    name: "Mura",
    address: "2980 Atlantic Ave, Coquitlam",
    aliases: ["MURA", "2980 ATLANTIC", "2980 ATLANTIC AVE"],
    lat: 49.281297,
    lng: -122.795576,
    frontEntrance: [49.281300, -122.795600],
    note: "Highrise — Front Entrance on Atlantic Ave"
  },
  {
    name: "Obelisk",
    address: "1178 Pinetree Way, Coquitlam",
    aliases: ["OBELISK", "1178 PINETREE", "1178 PINETREE WAY"],
    lat: 49.281969,
    lng: -122.793950,
    frontEntrance: [49.281969, -122.793950],
    note: "Highrise — Front Entrance on Pinetree Way"
  },
  {
    name: "Celadon (Windsor Gate)",
    address: "3102 Windsor Gate, Coquitlam",
    aliases: ["CELADON", "WINDSOR GATE", "3102 WINDSOR GATE"],
    lat: 49.279370,
    lng: -122.785004,
    frontEntrance: [49.279370, -122.785004],
    note: "Highrise Complex — Entrance on Windsor Gate"
  },
  {
    name: "Coquitlam Town Centre Park",
    address: "1299 Pinetree Way, Coquitlam",
    aliases: ["TOWN CENTRE PARK", "TC PARK", "1299 PINETREE"],
    lat: 49.287800,
    lng: -122.790500,
    frontEntrance: [49.287800, -122.790500],
    note: "Park Main Entrance & Plaza"
  },
  {
    name: "1386 Coast Meridian Rd",
    address: "1386 Coast Meridian Rd, Coquitlam",
    aliases: ["1386 COAST MERIDIAN", "1386 COAST MERIDIAN RD"],
    lat: 49.297541,
    lng: -122.755800, // Frontage on Coast Meridian Rd (Prevents routing to rear alley)
    frontEntrance: [49.297541, -122.755800],
    note: "Main Front Entrance on Coast Meridian Rd (Do not route via rear alley)"
  }
];
