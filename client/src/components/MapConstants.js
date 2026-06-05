// 🎨 COLORS
export const UNIT_COLORS = { 
  "E1": "#ef4444", "E2": "#3b82f6", "E3": "#22c55e", 
  "Q5": "#eab308", "E4": "#a855f7", "UNKNOWN": "#9ca3af" 
};

// 🗺️ BASE LAYERS (No-label basemaps)
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
};

// 🎮 DEFAULTS
export const MODE_DEFAULTS = {
    EXPLORE: "GREY",
    TRAINING_ZONES: "DARK",
    TRAINING_INTERSECTIONS: "GREY",
    TRAINING_BLOCKS: "GREY",
    TRAINING_ADDRESSES: "GREY",
    ROAD_CLOSURES: "GREY"
};

// 🚒 FIRE STATIONS COORDINATES
// Verified coordinates for Coquitlam Fire Halls
export const STATIONS = [
  { id: "1", name: "Town Centre Fire Hall (TCFH)", coords: [49.29109654571679, -122.79072561861948] },
  { id: "2", name: "Mariner Fire Hall", coords: [49.2622197420057, -122.81747986099539] },
  { id: "3", name: "Austin Heights Fire Hall", coords: [49.24803974681661, -122.86546062387211] },
  { id: "4", name: "Burke Mountain Fire Hall", coords: [49.29510006403205, -122.74247651791484] }
];

export const STATIONS_MAP = STATIONS.reduce((acc, stn) => {
  acc[stn.id] = stn.coords;
  return acc;
}, {});

