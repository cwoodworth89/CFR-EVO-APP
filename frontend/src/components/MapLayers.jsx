// NOTE: For live MapServer endpoints (Parcels, Roads, Zones) and fallback logic, see docs/gis_endpoints.md
import React, { useEffect, useRef } from 'react';
import { Marker, Tooltip, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { dynamicMapLayer } from 'esri-leaflet';
import * as turf from '@turf/turf';
import { BASE_LAYERS, MODE_DEFAULTS, STATIONS } from './MapConstants';



// 🎨 TUNED ICON (Fixed anchor centering)
const stationIcon = L.divIcon({
  className: 'custom-icon',
  html: `<div style="
    background-color: white;
    border: 2px solid #ef4444;
    border-radius: 50%;
    width: 30px;
    height: 30px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 5px rgba(0,0,0,0.3);
    font-size: 18px;
    box-sizing: content-box;
  ">🚒</div>`,
  iconSize: [34, 34],   // Width (30) + Border (4)
  iconAnchor: [17, 17], // Center (17)
  popupAnchor: [0, -20]
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

        const config = BASE_LAYERS[style];
        if (!config) {
            console.warn(`Unknown base layer style: ${style}`);
            return;
        }

        let url = config.url;
        if (useLabelsFallback && url.includes('_nolabels')) {
            url = url.replace('_nolabels', '_all');
        }

        if (config.type === 'tile') {
            const tileLayer = L.tileLayer(url, {
                attribution: config.attribution,
                subdomains: config.subdomains,
                maxNativeZoom: config.maxNativeZoom ?? 19,
                maxZoom: config.maxZoom ?? 22,
                noWrap: true,
            });
            tileLayer.addTo(map);
            layerRef.current = tileLayer;
        } else {
            console.warn('Unsupported base layer type:', config.type);
        }

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
                <Marker key={stn.id} position={stn.coords} icon={stationIcon}>
                    <Tooltip direction="top" offset={[0, -15]} className="font-bold text-xs">{stn.name}</Tooltip>
                </Marker>
            ))}
        </>
    );
}

// 🏗️ NEW: TOWER CRANES LAYER
const craneIcon = L.divIcon({
  className: 'custom-crane-icon',
  html: `<div style="
    background-color: #fff;
    border: 2px solid #ea580c;
    border-radius: 50%;
    width: 26px;
    height: 26px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 5px rgba(0,0,0,0.4);
    font-size: 15px;
    box-sizing: content-box;
  ">🏗️</div>`,
  iconSize: [30, 30],
  iconAnchor: [15, 15],
  popupAnchor: [0, -15]
});

export function CranesLayer({ visible, onSelectCrane }) {
  const [cranes, setCranes] = React.useState([]);

  React.useEffect(() => {
    if (!visible) return;

    fetch('/data/tower_cranes.json')
      .then(r => {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(data => {
        setCranes(data);
      })
      .catch(err => {
        console.warn("Failed to load Coquitlam tower cranes:", err);
      });
  }, [visible]);

  if (!visible) return null;

  return (
    <>
      {cranes.map(c => (
        <Marker 
          key={c.id} 
          position={[c.lat, c.lng]} 
          icon={craneIcon}
          eventHandlers={{
            click: () => {
              if (onSelectCrane) onSelectCrane(c);
            }
          }}
        >
          <Tooltip direction="top" offset={[0, -10]} className="font-bold text-xs bg-slate-950 text-white border border-slate-800 shadow-xl rounded-md p-2">
            <div className="flex flex-col gap-0.5">
              <span className="text-[9px] text-slate-400 uppercase font-mono tracking-wider">TOWER CRANE</span>
              <span className="text-white text-xs font-bold">{c.id}</span>
            </div>
          </Tooltip>
          <Popup className="crane-popup">
            <div className="bg-slate-950 text-white p-2.5 border border-slate-800 rounded-md" style={{ minWidth: '180px', maxWidth: '240px' }}>
              <div className="flex justify-between items-center gap-2">
                <span className="text-[9px] text-slate-400 font-mono font-medium">PRE-INCIDENT DATA</span>
                <span className="px-1.5 py-0.5 rounded text-[8px] font-bold tracking-wider bg-orange-500/20 text-orange-400 border border-orange-500/30">ACTIVE</span>
              </div>
              <h3 className="font-bold text-sm text-orange-400 mt-2 leading-tight">{c.name}</h3>
              
              <div className="mt-2 pt-1.5 border-t border-slate-800 flex justify-between text-xs">
                <span className="text-slate-400 font-sans">Location</span>
                <span className="text-slate-300 text-right leading-tight ml-2">{c.address}</span>
              </div>
              
              <div className="mt-3">
                <a 
                  href={c.pre_incident_plan_url} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="w-full flex items-center justify-center gap-1.5 px-3 py-1.5 bg-orange-600/20 hover:bg-orange-600/40 text-orange-400 hover:text-orange-300 border border-orange-500/30 hover:border-orange-500/50 rounded text-center text-xs font-bold transition-all shadow-md cursor-pointer"
                >
                  🔗 View Pre-Incident Plan
                </a>
              </div>
            </div>
          </Popup>
        </Marker>
      ))}
    </>
  );
}