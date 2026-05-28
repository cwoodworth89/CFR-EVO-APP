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
    QUIZ_ZONES: "DARK",
    QUIZ_INTERSECTIONS: "GREY",
    QUIZ_BLOCKS: "GREY",
    QUIZ_ADDRESSES: "GREY",
    ROAD_CLOSURES: "GREY"
};
