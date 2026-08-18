// Map & Layer Constants
import { TILE_BASE_URL, API_BASE_URL } from '../apiClient';

// 🌐 REGIONAL OPERATIONAL BOUNDING BOX (Coquitlam, Port Mann Bridge / North Surrey, Port Moody, Belcarra, Burnaby, New Westminster, Pinecone Burke)
export const OPERATIONAL_BOUNDS = [
  [49.15, -123.04], // Southwest: North Surrey / New Westminster / Central Burnaby
  [49.48, -122.60]  // Northeast: Pinecone Burke / Widgeon / Western Pitt Meadows
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
    maxNativeZoom: 18,
    maxZoom: 22,
  },
  DARK: {
    type: 'tile',
    url: `${TILE_BASE_URL}/services/street_nolabels/tiles/{z}/{x}/{y}.png`,
    fallbackUrl: null, // 100% pure offline local pre-cached tiles
    attribution: '© OpenStreetMap contributors & Carto (100% Offline Local Cache)',
    subdomains: ['a', 'b', 'c'],
    maxNativeZoom: 18,
    maxZoom: 22,
  },
  SATELLITE: {
    type: 'tile',
    url: `${TILE_BASE_URL}/services/satellite/tiles/{z}/{x}/{y}.jpg`,
    fallbackUrl: null, // 100% pure offline local pre-cached tiles
    attribution: 'City of Coquitlam 7.5cm Orthophotos & Maxar (100% Offline Local Cache)',
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
    maxNativeZoom: 18,
    maxZoom: 22
  },
  VOYAGER: {
    type: 'tile',
    url: `${TILE_BASE_URL}/services/street/tiles/{z}/{x}/{y}.png`,
    fallbackUrl: null, // 100% pure offline local pre-cached tiles
    attribution: '© OpenStreetMap contributors & Carto (100% Offline Local Cache)',
    subdomains: ['a', 'b', 'c'],
    maxNativeZoom: 18,
    maxZoom: 22
  }
};

export const MODE_DEFAULTS = {
  EXPLORE: "GREY",
  TRAINING_ZONES: "DARK",
  TRAINING_INTERSECTIONS: "GREY",
  TRAINING_BLOCKS: "GREY",
  TRAINING_ADDRESSES: "GREY",
  KIOSK_VIEW: "DARK"
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
