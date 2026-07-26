// NOTE: For live MapServer endpoints (Parcels, Roads, Zones) and fallback logic, see docs/gis_endpoints.md
import React, { useEffect, useRef } from 'react';
import { Marker, Tooltip, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { dynamicMapLayer } from 'esri-leaflet';
import * as turf from '@turf/turf';
import { BASE_LAYERS, MODE_DEFAULTS, STATIONS } from './MapConstants';



// 🚒 Custom Fire Hall Icon Loader
const BASE_URL = import.meta.env.BASE_URL || '/';

export const createFireHallIcon = (stationId = '1') => L.divIcon({
  className: 'custom-station-user-icon',
  html: `<div style="position:relative;display:flex;align-items:center;justify-content:center;background:transparent;border:none;filter:drop-shadow(0 3px 6px rgba(0,0,0,0.85));cursor:pointer;">
    <img src="${BASE_URL}icons/firehall.png" 
         onerror="if(this.src.includes('firehall.png')){this.src='${BASE_URL}icons/fire_hall.png';}else if(this.src.includes('fire_hall.png')){this.src='${BASE_URL}icons/fire_hall.svg';}else{this.onerror=null;}" 
         style="width:38px;height:38px;max-width:38px;max-height:38px;object-fit:contain;background:transparent;border:none;display:block;" 
         alt="Fire Hall ${stationId}" />
    <span style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);background:rgba(15,23,42,0.92);color:#fbbf24;border:1.5px solid #fbbf24;border-radius:9999px;font-size:11px;font-weight:900;width:18px;height:18px;display:flex;align-items:center;justify-content:center;font-family:monospace;box-shadow:0 2px 5px rgba(0,0,0,0.8);pointer-events:none;">${stationId}</span>
  </div>`,
  iconSize: [38, 38],
  iconAnchor: [19, 19],
  popupAnchor: [0, -19]
});

// 🗺️ BASEMAP COMPONENT
export function BaseMap({ style, useLabelsFallback }) {
    const map = useMap();
    const layerRef = useRef(null);

    useEffect(() => {
        const cleanup = () => {
            if (layerRef.current) {
                try {
                    if (map.hasLayer(layerRef.current)) {
                        map.removeLayer(layerRef.current);
                    }
                } catch (error) {
                    console.warn("Suppressed base layer cleanup error:", error);
                }
                layerRef.current = null;
            }
        };

        cleanup();

        const config = BASE_LAYERS[style] || BASE_LAYERS.GREY;
        let url = typeof config === 'string' ? config : (config.url || BASE_LAYERS.GREY.url || 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png');
        if (useLabelsFallback && url && url.includes('_nolabels')) {
            url = url.replace('_nolabels', '_all');
        }

        const attribution = typeof config === 'object' ? config.attribution : '&copy; <a href="https://carto.com/">CARTO</a>';
        const subdomains = typeof config === 'object' ? config.subdomains : 'abcd';
        const maxNativeZoom = typeof config === 'object' ? (config.maxNativeZoom ?? 19) : 19;
        const maxZoom = typeof config === 'object' ? (config.maxZoom ?? 22) : 22;

        const tileLayer = L.tileLayer(url, {
            attribution: attribution,
            subdomains: subdomains,
            maxNativeZoom: maxNativeZoom,
            maxZoom: maxZoom,
            noWrap: true,
        });
        tileLayer.addTo(map);
        layerRef.current = tileLayer;

        return cleanup;
    }, [map, style, useLabelsFallback]);

    return null;
}

// 🏗️ COQUITLAM ROADS/PARCELS
export function CoquitlamOverlays({ visible, onLoadError }) {
    const map = useMap();
    useEffect(() => {
      if (!visible) return;
      
      const overlayLayer = dynamicMapLayer({
          url: "https://geodata.coquitlam.ca/arcgis/rest/services/DynamicServices/Cadastral/MapServer",
          opacity: 0.9,
          layers: [0, 1, 16], // Roads, Addresses, Parcels
          f: 'image'
      });

      if (onLoadError) {
          overlayLayer.on('requesterror', (err) => {
              console.warn("Coquitlam Cadastral map server is inaccessible. Triggering standard basemap labels fallback.", err);
              onLoadError();
          });
      }

      overlayLayer.addTo(map);

      return () => { 
          overlayLayer.off('requesterror');
          map.removeLayer(overlayLayer);
      };
    }, [map, visible, onLoadError]);
    
    return null;
}

// 🚒 NEW: FIRE ZONES (Official GIS Layer)
// Updated to accept a 'pane' prop
export function FireZonesLayer({ visible, pane }) {
    const map = useMap();
    useEffect(() => {
      if (!visible) return;
      
      const layer = dynamicMapLayer({
          url: "https://geodata.coquitlam.ca/arcgis/rest/services/DynamicServices/Planning/MapServer",
          layers: [6], 
          opacity: 0.8,
          f: 'image',
          pane: pane || 'overlayPane' // 👈 THIS IS THE FIX
      }).addTo(map);

      return () => { 
          map.removeLayer(layer);
      };
    }, [map, visible, pane]); // Add pane to dependencies
    
    return null;
}

// 💧 NEW: WATER HYDRANTS GIS LAYER
export function HydrantsLayer({ visible }) {
    const map = useMap();
    const [zoom, setZoom] = React.useState(map.getZoom());
    const [hydrants, setHydrants] = React.useState([]);

    // Track map zoom and movements
    React.useEffect(() => {
      if (!visible) return;

      const handleMapChange = () => {
        setZoom(map.getZoom());
      };

      map.on('zoomend', handleMapChange);
      map.on('moveend', handleMapChange);
      
      // Initialize
      handleMapChange();

      return () => {
        map.off('zoomend', handleMapChange);
        map.off('moveend', handleMapChange);
      };
    }, [map, visible]);

    const [allHydrants, setAllHydrants] = React.useState([]);

    // Load local cached hydrant database once when visible
    React.useEffect(() => {
      if (!visible) return;

      const baseUrl = import.meta.env.BASE_URL;
      fetch(`${baseUrl}data/hydrants.json`)
        .then(r => {
          if (!r.ok) throw new Error("HTTP " + r.status);
          return r.json();
        })
        .then(data => {
          setAllHydrants(data);
        })
        .catch(err => {
          console.warn("Failed to load local cached hydrants:", err);
        });
    }, [visible]);

    // Zoom >= 17: Filter local hydrants in-memory based on current bounding box with spatial thresholding
    const lastCenterRef = React.useRef(null);
    const lastZoomRef = React.useRef(null);
    const debounceTimerRef = React.useRef(null);
    const bbox = visible && zoom >= 17 ? map.getBounds().toBBoxString() : "";

    React.useEffect(() => {
      if (!visible || zoom < 17 || allHydrants.length === 0 || !bbox) {
        setHydrants([]);
        return;
      }

      const currentCenter = map.getCenter();
      const currentZoom = map.getZoom();
      const lastCenter = lastCenterRef.current;
      const lastZoom = lastZoomRef.current;

      let shouldFilter = false;
      if (!lastCenter || lastZoom !== currentZoom) {
        shouldFilter = true;
      } else {
        const from = turf.point([lastCenter.lng, lastCenter.lat]);
        const to = turf.point([currentCenter.lng, currentCenter.lat]);
        const distMeters = turf.distance(from, to, { units: 'kilometers' }) * 1000;
        if (distMeters >= 75) {
          shouldFilter = true;
        }
      }

      if (!shouldFilter) return;

      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }

      debounceTimerRef.current = setTimeout(() => {
        lastCenterRef.current = currentCenter;
        lastZoomRef.current = currentZoom;

        const bounds = map.getBounds();
        const minLng = bounds.getSouthWest().lng;
        const minLat = bounds.getSouthWest().lat;
        const maxLng = bounds.getNorthEast().lng;
        const maxLat = bounds.getNorthEast().lat;

        // Filter hydrants in current viewport bounds
        const filtered = allHydrants.filter(h => 
          h.lng >= minLng && h.lng <= maxLng &&
          h.lat >= minLat && h.lat <= maxLat
        );

        // Map back to format expected by rendering code: { geometry: {x,y}, attributes: {OBJECTID,gis_id,status,flow_class} }
        const formatted = filtered.map(h => ({
          geometry: { x: h.lng, y: h.lat },
          attributes: {
            OBJECTID: h.id,
            gis_id: h.gisId,
            status: h.status,
            flow_class: h.flowClass
          }
        }));

        setHydrants(formatted);
      }, 100); // Fast 100ms debounce since local array filtering is instant

      return () => {
        if (debounceTimerRef.current) {
          clearTimeout(debounceTimerRef.current);
        }
      };
    }, [visible, zoom, map, bbox, allHydrants]);

    // Custom Icon styling to highlight details and flow ratings in a premium dot-and-ring aesthetic
    const getHydrantIcon = (status, flowClass) => {
      let bgColor = 'rgba(15, 23, 42, 0.6)'; // dark fill inside the ring
      let borderColor = '#facc15'; // default yellow
      let borderStyle = '2px solid';
      let opacity = '1.0';
      
      let isSpecial = false;
      let emoji = '';

      if (status === 'PRIVATE') {
        borderColor = '#f59e0b'; // Amber
        isSpecial = true;
        emoji = '🔒';
      } else if (status === 'ABANDONED' || status === 'OUT_OF_SERVICE' || status === 'INACTIVE') {
        borderColor = '#ef4444'; // Red
        isSpecial = true;
        emoji = '⚠️';
        opacity = '0.9';
      } else {
        // NFPA 291 Color code by flow class rating
        const fc = (flowClass || "").toUpperCase();
        if (fc === 'AA') {
          borderColor = '#38bdf8'; // Sky Blue
        } else if (fc === 'A') {
          borderColor = '#4ade80'; // Green
        } else if (fc === 'B') {
          borderColor = '#fb923c'; // Orange
        } else if (fc === 'C') {
          borderColor = '#f87171'; // Red
        } else {
          borderColor = '#facc15'; // Yellow
        }
      }

      const iconHtml = isSpecial ? `
        <div style="
          background-color: ${status === 'PRIVATE' ? 'rgba(245, 158, 11, 0.15)' : 'rgba(55, 65, 81, 0.6)'};
          border: ${borderStyle} ${borderColor};
          border-radius: 50%;
          width: 20px;
          height: 20px;
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 2px 4px rgba(0,0,0,0.4);
          font-size: 10px;
          box-sizing: border-box;
          opacity: ${opacity};
        ">${emoji}</div>
      ` : `
        <div style="
          width: 20px;
          height: 20px;
          border: 2px solid ${borderColor};
          border-radius: 50%;
          background-color: ${bgColor};
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 2px 4px rgba(0,0,0,0.4);
          box-sizing: border-box;
          opacity: ${opacity};
        ">
          <div style="
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: ${borderColor};
          "></div>
        </div>
      `;

      // High-contrast rating label (e.g. AA) in white
      const ratingHtml = flowClass ? `
        <div style="
          font-family: monospace, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, sans-serif;
          font-weight: 900;
          font-size: 9px;
          color: #ffffff;
          text-shadow: -1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000, 1px 1px 0 #000;
          letter-spacing: 0.5px;
          text-align: center;
          line-height: 1;
        ">${flowClass}</div>
      ` : '';

      // Combined vertical stack label block (Only displaying rating under icon per user request)
      const labelHtml = ratingHtml ? `
        <div style="
          display: flex; 
          flex-direction: column; 
          align-items: center; 
          margin-top: 2px; 
          pointer-events: none;
        ">
          ${ratingHtml}
        </div>
      ` : '';

      return L.divIcon({
        className: 'custom-hydrant-icon-container',
        html: `
          <div style="
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
          ">
            ${iconHtml}
            ${labelHtml}
          </div>
        `,
        // Covers vertical height of circle (20px) + margin/text (~20px) = 40px
        iconSize: [24, 40],
        iconAnchor: [12, 10], // Centered horizontally (12) and vertically in the circle (10)
        popupAnchor: [0, -10]
      });
    };

    if (!visible) return null;

    return (
      <>
        {zoom >= 17 && hydrants.map((h, i) => {
          if (!h.geometry || h.geometry.x === undefined || h.geometry.y === undefined) return null;
          const coords = [h.geometry.y, h.geometry.x];
          const statusVal = (h.attributes.status || "").toUpperCase();
          const gisId = h.attributes.gis_id || "Unknown";
          const flowClass = h.attributes.flow_class || "";
          
          let label = "OPERATING";
          if (statusVal === "PRIVATE") label = "PRIVATE";
          if (statusVal === "ABANDONED" || statusVal === "OUT_OF_SERVICE" || statusVal === "INACTIVE") label = "OUT OF SERVICE";

          return (
            <Marker 
              key={`${gisId}-${i}`} 
              position={coords} 
              icon={getHydrantIcon(statusVal, flowClass)}
            >
              <Tooltip direction="top" offset={[0, -10]} className="font-bold text-xs bg-slate-950 text-white border border-slate-800 shadow-xl rounded-md p-2">
                <div className="flex flex-col gap-0.5" style={{ minWidth: '120px' }}>
                  <span className="text-[9px] text-slate-400 uppercase font-mono tracking-wider">HYDRANT ID</span>
                  <span className="text-white text-sm font-bold">{gisId}</span>
                  
                  <span className="text-[9px] text-slate-400 uppercase font-mono tracking-wider mt-1.5">STATUS</span>
                  <span className={`font-bold text-xs ${
                    label === "OPERATING" ? "text-emerald-400" :
                    label === "PRIVATE" ? "text-amber-400" : "text-rose-400"
                  }`}>{label}</span>
                  
                  {flowClass && (
                    <>
                      <span className="text-[9px] text-slate-400 uppercase font-mono tracking-wider mt-1.5">FLOW CLASS</span>
                      <span className="text-sky-400 text-xs font-semibold">{flowClass}</span>
                    </>
                  )}
                </div>
              </Tooltip>
              <Popup className="hydrant-popup">
                <div className="bg-slate-950 text-white p-2.5 border border-slate-800 rounded-md" style={{ minWidth: '180px', maxWidth: '240px' }}>
                  <div className="flex justify-between items-center gap-2">
                    <span className="text-[9px] text-slate-400 font-mono font-medium">HYDRANT DETAIL</span>
                    <span className={`px-1.5 py-0.5 rounded text-[8px] font-bold tracking-wider ${
                      label === 'OPERATING' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' :
                      label === 'PRIVATE' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
                      'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                    }`}>{label}</span>
                  </div>
                  <h3 className="font-bold text-sm text-sky-400 mt-2 leading-tight">ID: {gisId}</h3>
                  
                  <div className="mt-2 pt-1.5 border-t border-slate-800 flex justify-between text-xs">
                    <span className="text-slate-400 font-sans">Flow Rating</span>
                    <span className="text-white font-mono font-bold">{flowClass || "N/A"}</span>
                  </div>
                  
                  <div className="mt-1 flex justify-between text-xs">
                    <span className="text-slate-400 font-sans">Type/Status</span>
                    <span className="text-slate-300 font-mono font-semibold">{statusVal}</span>
                  </div>
                </div>
              </Popup>
            </Marker>
          );
        })}
      </>
    );
}

export function StationsLayer() {
    return (
        <>
            {STATIONS.map(stn => (
                <Marker key={stn.id} position={stn.coords} icon={createFireHallIcon(stn.id)}>
                    <Tooltip direction="top" offset={[0, -18]} className="font-bold text-xs bg-slate-950 text-white border border-slate-800 shadow-xl rounded-md p-2">
                        <div className="flex flex-col gap-0.5 font-mono">
                          <span className="text-[9px] text-red-400 font-black uppercase tracking-wider">🚒 COQUITLAM FIRE HALL #{stn.id}</span>
                          <span className="text-white text-xs font-bold">{stn.name}</span>
                        </div>
                    </Tooltip>
                </Marker>
            ))}
        </>
    );
}



// Custom Railroad Crossing Icon Loader (Loads custom user logo from /icons/railroad_crossing.png or /icons/railroad_crossing.svg)
export const createRailroadCrossingIcon = () => L.divIcon({
  className: 'custom-railroad-user-icon',
  html: `<div style="display:flex;align-items:center;justify-content:center;filter:drop-shadow(0 3px 6px rgba(0,0,0,0.85));cursor:pointer;">
    <img src="${BASE_URL}icons/railroad_crossing.png" 
         onerror="this.onerror=null; this.src='${BASE_URL}icons/railroad_crossing.svg';" 
         style="width:34px;height:34px;max-width:34px;max-height:34px;object-fit:contain;" 
         alt="Railroad Crossing" />
  </div>`,
  iconSize: [34, 34],
  iconAnchor: [17, 17],
  popupAnchor: [0, -17]
});

// Coquitlam At-Grade CP Rail Crossings (Verified Coquitlam Fire Rescue Coordinates)
export const COQUITLAM_RAILROAD_CROSSINGS = [
  { id: 'RR-01', name: 'Westwood St Crossing', lat: 49.2692679, lng: -122.7912637, location: 'Westwood St & Kingsway Ave', avoidable: true },
  { id: 'RR-02', name: 'Kingsway Ave Crossing', lat: 49.2650819, lng: -122.7911077, location: 'Kingsway Ave (Riverbend Corridor)', avoidable: false, note: 'Difficult to avoid for Riverbend' },
  { id: 'RR-03', name: 'Pitt River Rd Crossing', lat: 49.2505499, lng: -122.8016317, location: 'Pitt River Rd at CP Rail mainline', avoidable: true },
  { id: 'RR-04', name: 'Colony Farm Rd Crossing', lat: 49.2397800, lng: -122.8142995, location: 'Colony Farm Rd (Sole Access)', avoidable: false, note: 'Sole access road - Cannot route around' }
];

export function RailroadCrossingsLayer({ visible }) {
  if (!visible) return null;

  return (
    <>
      {COQUITLAM_RAILROAD_CROSSINGS.map(rr => (
        <Marker
          key={rr.id}
          position={[rr.lat, rr.lng]}
          icon={createRailroadCrossingIcon()}
        >
          <Tooltip direction="top" offset={[0, -10]} className="font-bold text-xs bg-slate-950 text-white border border-slate-800 shadow-xl rounded-md p-2">
            <div className="flex flex-col gap-0.5 font-mono">
              <span className="text-[9px] text-amber-400 font-black uppercase tracking-wider">⚠️ CP RAIL AT-GRADE CROSSING</span>
              <span className="text-white text-xs font-bold">{rr.name}</span>
              <span className="text-[8.5px] text-slate-300">{rr.location}</span>
              {rr.note && <span className="text-[8px] text-amber-300/90 font-sans italic mt-0.5">ℹ️ {rr.note}</span>}
            </div>
          </Tooltip>
        </Marker>
      ))}
    </>
  );
}

// 🏫 Custom School Icon Loader (Loads custom user logo from /icons/school.png or /icons/school.svg)
export const createSchoolIcon = () => L.divIcon({
  className: 'custom-school-user-icon',
  html: `<div style="display:flex;align-items:center;justify-content:center;filter:drop-shadow(0 3px 6px rgba(0,0,0,0.85));cursor:pointer;">
    <img src="${BASE_URL}icons/school.png" 
         onerror="this.onerror=null; this.src='${BASE_URL}icons/school.svg';" 
         style="width:32px;height:32px;max-width:32px;max-height:32px;object-fit:contain;" 
         alt="School" />
  </div>`,
  iconSize: [32, 32],
  iconAnchor: [16, 16],
  popupAnchor: [0, -16]
});

// Official School District 43 (SD43 Coquitlam) GIS Dataset
export const COQUITLAM_SCHOOLS = [
  // SECONDARY SCHOOLS (9-12)
  { id: 'SCH-01', name: 'Pinetree Secondary', type: 'Secondary (9-12)', lat: 49.290971, lng: -122.789727, address: '3000 Pinewood Ave, Coquitlam' },
  { id: 'SCH-02', name: 'Gleneagle Secondary', type: 'Secondary (9-12)', lat: 49.284324, lng: -122.809637, address: '1195 Lansdowne Dr, Coquitlam' },
  { id: 'SCH-03', name: 'Centennial Secondary', type: 'Secondary (9-12)', lat: 49.256094, lng: -122.846422, address: '570 Poirier St, Coquitlam' },
  { id: 'SCH-04', name: 'Dr. Charles Best Secondary', type: 'Secondary (9-12)', lat: 49.263301, lng: -122.834416, address: '2525 Como Lake Ave, Coquitlam' },
  { id: 'SCH-05', name: 'Heritage Woods Secondary', type: 'Secondary (9-12)', lat: 49.296194, lng: -122.819485, address: '1300 David Ave, Port Moody/Coquitlam' },
  { id: 'SCH-06', name: 'Terry Fox Secondary', type: 'Secondary (9-12)', lat: 49.268500, lng: -122.756200, address: '1260 Riverwood Gate, Port Coquitlam' },
  { id: 'SCH-07', name: 'Riverside Secondary', type: 'Secondary (9-12)', lat: 49.252500, lng: -122.775800, address: '2215 Reeve St, Port Coquitlam' },
  { id: 'SCH-08', name: 'CABE Secondary', type: 'Secondary (9-12)', lat: 49.256057, lng: -122.840904, address: '1411 Foster Ave, Coquitlam' },

  // MIDDLE SCHOOLS (6-8)
  { id: 'SCH-09', name: 'Como Lake Middle', type: 'Middle (6-8)', lat: 49.251446, lng: -122.863386, address: '1121 King Albert Ave, Coquitlam' },
  { id: 'SCH-10', name: 'École Banting Middle', type: 'Middle (6-8)', lat: 49.263609, lng: -122.880040, address: '820 Banting St, Coquitlam' },
  { id: 'SCH-11', name: 'Hillcrest Middle', type: 'Middle (6-8)', lat: 49.245015, lng: -122.844075, address: '2161 Regan Ave, Coquitlam' },
  { id: 'SCH-12', name: 'Maple Creek Middle', type: 'Middle (6-8)', lat: 49.287890, lng: -122.783570, address: '3700 Townline Rd, Coquitlam' },
  { id: 'SCH-13', name: 'Scott Creek Middle', type: 'Middle (6-8)', lat: 49.284324, lng: -122.809637, address: '1240 Lansdowne Dr, Coquitlam' },
  { id: 'SCH-14', name: 'Summit Middle', type: 'Middle (6-8)', lat: 49.294200, lng: -122.790500, address: '1450 Westwood St, Coquitlam' },
  { id: 'SCH-15', name: 'École Citadel Middle', type: 'Middle (6-8)', lat: 49.248500, lng: -122.775000, address: '1265 Citadel Dr, Port Coquitlam' },

  // ELEMENTARY SCHOOLS (K-5)
  { id: 'SCH-16', name: 'Alderson Elementary', type: 'Elementary (K-5)', lat: 49.239731, lng: -122.873000, address: '825 Gauthier Ave, Coquitlam' },
  { id: 'SCH-17', name: 'Baker Drive Elementary', type: 'Elementary (K-5)', lat: 49.268121, lng: -122.803196, address: '885 Baker Dr, Coquitlam' },
  { id: 'SCH-18', name: 'Bramblewood Elementary', type: 'Elementary (K-5)', lat: 49.297535, lng: -122.809393, address: '2875 Panorama Dr, Coquitlam' },
  { id: 'SCH-19', name: 'Cape Horn Elementary', type: 'Elementary (K-5)', lat: 49.230790, lng: -122.836984, address: '155 Finnigan St, Coquitlam' },
  { id: 'SCH-20', name: 'Coast Salish Elementary', type: 'Elementary (K-5)', lat: 49.297952, lng: -122.740824, address: '3538 Sheffield Ave, Coquitlam' },
  { id: 'SCH-21', name: 'Meadowbrook Elementary', type: 'Elementary (K-5)', lat: 49.272861, lng: -122.804093, address: '900 Meadowbrook Way, Coquitlam' },
  { id: 'SCH-22', name: 'Westwood Elementary', type: 'Elementary (K-5)', lat: 49.294205, lng: -122.789993, address: '3610 Pinetree Way, Coquitlam' }
];

export function SchoolsLayer({ visible }) {
  if (!visible) return null;

  return (
    <>
      {COQUITLAM_SCHOOLS.map(sch => (
        <Marker
          key={sch.id}
          position={[sch.lat, sch.lng]}
          icon={createSchoolIcon()}
        >
          <Tooltip direction="top" offset={[0, -10]} className="font-bold text-xs bg-slate-950 text-white border border-slate-800 shadow-xl rounded-md p-2">
            <div className="flex flex-col gap-0.5 font-mono">
              <span className="text-[9px] text-blue-400 font-black uppercase tracking-wider">🏫 SCHOOL ZONE</span>
              <span className="text-white text-xs font-bold">{sch.name}</span>
              <span className="text-[8.5px] text-slate-300">{sch.type} — {sch.address}</span>
            </div>
          </Tooltip>
        </Marker>
      ))}
    </>
  );
}