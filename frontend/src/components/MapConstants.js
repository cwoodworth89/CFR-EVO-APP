// Map & Layer Constants

// 🗺️ BASE LAYERS (Clean no-label basemaps for Coquitlam municipal vector overlays)
export const BASE_LAYERS = {
  GREY: {
    type: 'tile',
    url: 'https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png',
    attribution: '© OpenStreetMap contributors & Carto',
    subdomains: ['a', 'b', 'c', 'd'],
    maxNativeZoom: 19,
    maxZoom: 22,
  },
  DARK: {
    type: 'tile',
    url: 'https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png',
    attribution: '© OpenStreetMap contributors & Carto',
    subdomains: ['a', 'b', 'c', 'd'],
    maxNativeZoom: 19,
    maxZoom: 22,
  },
  SATELLITE: {
    type: 'tile',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Esri, Maxar, Earthstar Geographics',
    subdomains: ['a', 'b', 'c'],
    maxNativeZoom: 18,
    maxZoom: 22
  },
  OSM: {
    type: 'tile',
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '© OpenStreetMap contributors',
    subdomains: ['a', 'b', 'c'],
    maxNativeZoom: 19,
    maxZoom: 22
  },
  VOYAGER: {
    type: 'tile',
    url: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
    attribution: '© OpenStreetMap contributors & Carto',
    subdomains: ['a', 'b', 'c', 'd'],
    maxNativeZoom: 19,
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
// Pre-configured building names and verified front-entrance routing access points
export const KNOWN_BUILDINGS = [
  {
    name: "Grand Central 2",
    address: "2968 Glen Dr, Coquitlam",
    aliases: ["GRAND CENTRAL 2", "GRAND CENTRAL TWO", "2968 GLEN", "2968 GLEN DR"],
    lat: 49.282500,
    lng: -122.796200, // Main front driveway entrance on Glen Dr (Prevents routing to back alleyway)
    frontEntrance: [49.282500, -122.796200],
    note: "Highrise — Main Front Entrance on Glen Dr (Do not route via back alley)"
  },
  {
    name: "Grand Central 1",
    address: "2978 Glen Dr, Coquitlam",
    aliases: ["GRAND CENTRAL 1", "2978 GLEN", "2978 GLEN DR"],
    lat: 49.282188,
    lng: -122.796949,
    frontEntrance: [49.282200, -122.796900],
    note: "Highrise — Front Entrance on Glen Dr"
  },
  {
    name: "Grand Central 3",
    address: "2958 Glen Dr, Coquitlam",
    aliases: ["GRAND CENTRAL 3", "2958 GLEN", "2958 GLEN DR"],
    lat: 49.282800,
    lng: -122.795500,
    frontEntrance: [49.282800, -122.795500],
    note: "Highrise — Front Entrance on Glen Dr"
  },
  {
    name: "Mura",
    address: "2980 Atlantic Ave, Coquitlam",
    aliases: ["MURA", "2980 ATLANTIC"],
    lat: 49.281297,
    lng: -122.795576,
    frontEntrance: [49.281300, -122.795600],
    note: "Highrise — Front Entrance on Atlantic Ave"
  },
  {
    name: "Coquitlam Town Centre Park",
    address: "1299 Pinetree Way, Coquitlam",
    aliases: ["TOWN CENTRE PARK", "TC PARK"],
    lat: 49.287800,
    lng: -122.790500,
    frontEntrance: [49.287800, -122.790500],
    note: "Park Main Entrance"
  }
];
