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
export const BASE_LAYERS = {
  GREY: {
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
  DARK: {
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
  // Aerial imagery. Serves the City of Coquitlam 2025 7.5cm orthophotos ONLY
  // (`ortho.mbtiles`, Open Government Licence), crawled from the City's own
  // imagery service, with no Esri fallback beneath it.
  //
  // Until 2026-08-30 this key pointed at `services/satellite`, which is Esri
  // World Imagery end to end -- the orthos had never been ingested, despite this
  // attribution string naming them. Blank outside the ortho footprint is the
  // correct rendering (CLAUDE.md 6.1): it shows where imagery genuinely stops
  // rather than silently substituting a coarser source.
  SATELLITE: {
    type: 'tile',
    url: `${TILE_BASE_URL}/services/ortho/tiles/{z}/{x}/{y}.jpg`,
    fallbackUrl: null, // 100% pure offline local pre-cached tiles
    attribution: 'City of Coquitlam 2025 7.5cm Orthophoto (Open Government Licence, Offline Local Cache)',
    subdomains: ['a', 'b', 'c'],
    // z20. That is where the City's own imagery cache ends -- z21 returns 404,
    // verified at three locations 2026-08-31 -- and it is the honest limit for a
    // 7.5cm source: z20 is 9.74 cm/px here, z21 would be 4.87 cm/px with nothing
    // real to fill it. Leaflet upscales past this, so the map still reaches
    // maxZoom 22; it just stops requesting tiles that do not exist.
    maxNativeZoom: 20,
    maxZoom: 22
  },
  // ---------------------------------------------------------------------
  // TEMPORARY -- added 2026-08-31 so the operator can A/B the City crawl
  // against the retired Esri scrape on the bay display. `satellite.mbtiles`
  // is kept on the kiosk only for this comparison.
  //
  // REMOVE THIS, its button in LeftSidebar, and its branch in MapBoard's
  // baseStyle once the comparison is done -- then delete satellite.mbtiles.
  // Both layers are the same photographs; only the processing differs.
  // ---------------------------------------------------------------------
  SATELLITE_ESRI: {
    type: 'tile',
    url: `${TILE_BASE_URL}/services/satellite/tiles/{z}/{x}/{y}.jpg`,
    fallbackUrl: null,
    attribution: 'Esri World Imagery scrape (RETIRED -- comparison only)',
    subdomains: ['a', 'b', 'c'],
    maxNativeZoom: 20,
    maxZoom: 22
  },
  OSM: {
    type: 'tile',
    url: `${TILE_BASE_URL}/services/street/tiles/{z}/{x}/{y}.png`,
    fallbackUrl: null, // 100% pure offline local pre-cached tiles
    attribution: '© OpenStreetMap contributors (100% Offline Local Cache)',
    subdomains: ['a', 'b', 'c'],
    // z18: the deepest zoom crawled for the Carto street styles (operator
    // decision 2026-08-30, punch-list #47). Leaflet upscales past this, so the
    // map still zooms to maxZoom 22 -- it just stops requesting new tiles. Must
    // match "max_zoom" for street/street_nolabels in compile_mbtiles.py.
    maxNativeZoom: 18,
    maxZoom: 22
  },
  VOYAGER: {
    type: 'tile',
    url: `${TILE_BASE_URL}/services/street/tiles/{z}/{x}/{y}.png`,
    fallbackUrl: null, // 100% pure offline local pre-cached tiles
    attribution: '© OpenStreetMap contributors & Carto (100% Offline Local Cache)',
    subdomains: ['a', 'b', 'c'],
    // z18: the deepest zoom crawled for the Carto street styles (operator
    // decision 2026-08-30, punch-list #47). Leaflet upscales past this, so the
    // map still zooms to maxZoom 22 -- it just stops requesting new tiles. Must
    // match "max_zoom" for street/street_nolabels in compile_mbtiles.py.
    maxNativeZoom: 18,
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

export const OVERLAY_LAYERS = {
  CADASTRAL: {
    url: `${TILE_BASE_URL}/services/cadastral/tiles/{z}/{x}/{y}.png`,
    fallbackUrl: null,
    maxNativeZoom: 20,
    maxZoom: 22,
  }
};

export const MODE_DEFAULTS = {
  EXPLORE: "GREY",
  KIOSK_VIEW: "DARK",
  DRIVER_SETUP: "GREY",
  ADMIN_DISPATCHES: "GREY"
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
