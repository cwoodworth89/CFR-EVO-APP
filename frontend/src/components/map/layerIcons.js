import L from 'leaflet';

const BASE_URL = import.meta.env.BASE_URL || '/';

// Memoizes one divIcon per station so repeated renders reuse the same DOM node.
const STATION_ICON_CACHE = {};

/**
 * Leaflet div icons for the map layers.
 *
 * Extracted from MapLayers.jsx for `react-refresh/only-export-components`.
 *
 * createSchoolIcon was removed rather than moved: it had no remaining caller after the
 * hardcoded school list came out of MapLayers.jsx with the custom_places removal
 * (2ef12b7), so it was dead code.
 */

export const createFireHallIcon = (stationId = '1') => {
  const key = String(stationId);
  if (!STATION_ICON_CACHE[key]) {
    STATION_ICON_CACHE[key] = L.divIcon({
      className: 'custom-station-user-icon',
      html: `<div style="position:relative;display:flex;align-items:center;justify-content:center;background:transparent;border:none;border-radius:50%;opacity:0.95;filter:drop-shadow(0 3px 6px rgba(0,0,0,0.85));cursor:pointer;">
        <img src="${BASE_URL}icons/fire_hall.png" 
             style="width:38px;height:38px;max-width:38px;max-height:38px;object-fit:cover;border-radius:50%;overflow:hidden;background:transparent;border:none;display:block;" 
             alt="Fire Hall ${key}" />
        <span style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);background:rgba(15,23,42,0.92);color:#fbbf24;border:1.5px solid #fbbf24;border-radius:9999px;font-size:11px;font-weight:900;width:18px;height:18px;display:flex;align-items:center;justify-content:center;font-family:monospace;box-shadow:0 2px 5px rgba(0,0,0,0.8);pointer-events:none;">${key}</span>
      </div>`,
      iconSize: [38, 38],
      iconAnchor: [19, 19],
      popupAnchor: [0, -19]
    });
  }
  return STATION_ICON_CACHE[key];
};

// 🗺️ BASEMAP COMPONENT

export const createRailroadCrossingIcon = () => L.divIcon({
  className: 'custom-rr-user-icon',
  html: `<div style="display:flex;align-items:center;justify-content:center;border-radius:50%;opacity:0.88;filter:drop-shadow(0 3px 6px rgba(0,0,0,0.85));cursor:pointer;">
    <img src="${BASE_URL}icons/railroad_crossing.png" 
         onerror="this.onerror=null; this.src='${BASE_URL}icons/railroad_crossing.svg';" 
         style="width:34px;height:34px;max-width:34px;max-height:34px;object-fit:cover;border-radius:50%;overflow:hidden;display:block;" 
         alt="Railroad Crossing" />
  </div>`,
  iconSize: [34, 34],
  iconAnchor: [17, 17],
  popupAnchor: [0, -17]
});

// Coquitlam At-Grade CP Rail Crossings (Verified Coquitlam Fire Rescue Coordinates)
