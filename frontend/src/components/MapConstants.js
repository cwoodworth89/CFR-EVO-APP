// Map & Layer Constants

export const BASE_LAYERS = {
  GREY: {
    type: 'tile',
    url: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
    attribution: '&copy; <a href="https://carto.com/">CARTO</a>',
    subdomains: 'abcd',
    maxNativeZoom: 19,
    maxZoom: 22
  },
  DARK: {
    type: 'tile',
    url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    attribution: '&copy; <a href="https://carto.com/">CARTO</a>',
    subdomains: 'abcd',
    maxNativeZoom: 19,
    maxZoom: 22
  },
  SATELLITE: {
    type: 'tile',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Esri, Maxar, Earthstar Geographics',
    subdomains: 'abc',
    maxNativeZoom: 18,
    maxZoom: 22
  },
  OSM: {
    type: 'tile',
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; OpenStreetMap contributors',
    subdomains: 'abc',
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
