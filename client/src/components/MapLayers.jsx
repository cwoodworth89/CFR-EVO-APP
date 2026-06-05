import React, { useEffect, useRef } from 'react';
import { Marker, Tooltip, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { dynamicMapLayer } from 'esri-leaflet';
import { BASE_LAYERS, MODE_DEFAULTS } from './MapConstants';

// 🚒 STATIONS
// Coordinates verified against official Coquitlam Fire Hall addresses
const STATIONS = [
    { id: "1", name: "Town Centre Fire Hall (TCFH)", coords: [49.291329039026046, -122.79161362016414] },
    { id: "2", name: "Mariner Fire Hall", coords: [49.26223510671969, -122.81725512755891] },
    { id: "3", name: "Austin Heights Fire Hall", coords: [49.24804277980424, -122.86566519365569] },
    { id: "4", name: "Burke Mountain Fire Hall", coords: [49.2952132946437, -122.7425391041921] }
];

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

// ≡ƒ¢á∩╕Å BASEMAP COMPONENT
export function BaseMap({ style }) {
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

        if (config.type === 'tile') {
            const tileLayer = L.tileLayer(config.url, {
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
    }, [map, style]);

    return null;
}

// 🏗️ COQUITLAM ROADS/PARCELS
export function CoquitlamOverlays({ visible }) {
    const map = useMap();
    useEffect(() => {
      if (!visible) return;
      
      const overlayLayer = dynamicMapLayer({
          url: "https://geodata.coquitlam.ca/arcgis/rest/services/DynamicServices/Cadastral/MapServer",
          opacity: 0.9,
          layers: [0, 1, 16], // Roads, Addresses, Parcels
          f: 'image'
      }).addTo(map);

      return () => { 
          map.removeLayer(overlayLayer);
      };
    }, [map, visible]);
    
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

    // 1. Render static Esri dynamic map overlay at zoom levels >= 17 for official hydrant icons
    React.useEffect(() => {
      if (!visible || zoom < 17) return;
      
      const layer = dynamicMapLayer({
          url: "https://geodata.coquitlam.ca/arcgis/rest/services/DynamicServices/Water/MapServer",
          layers: [2], // 2 = Water Hydrants
          opacity: 0.9,
          f: 'image'
      }).addTo(map);

      return () => { 
          map.removeLayer(layer);
      };
    }, [map, visible, zoom]);

    // 2. Zoom >= 17: Fetch dynamic bounding-box vector hydrants for detailed highlights
    const bbox = visible && zoom >= 17 ? map.getBounds().toBBoxString() : "";
    React.useEffect(() => {
      if (!visible || zoom < 17 || !bbox) {
        setHydrants([]);
        return;
      }

      let active = true;
      const bounds = map.getBounds();
      const minLng = bounds.getSouthWest().lng;
      const minLat = bounds.getSouthWest().lat;
      const maxLng = bounds.getNorthEast().lng;
      const maxLat = bounds.getNorthEast().lat;

      const url = `https://geodata.coquitlam.ca/arcgis/rest/services/DynamicServices/Water/MapServer/2/query?geometry=${minLng},${minLat},${maxLng},${maxLat}&geometryType=esriGeometryEnvelope&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=OBJECTID,gis_id,status,flow_class&returnGeometry=true&outSR=4326&f=json`;

      fetch(url)
        .then(r => {
          if (!r.ok) throw new Error("HTTP " + r.status);
          return r.json();
        })
        .then(data => {
          if (active && data && data.features) {
            setHydrants(data.features);
          }
        })
        .catch(err => {
          console.warn("Failed to fetch viewport hydrants:", err);
        });

      return () => {
        active = false;
      };
    }, [visible, zoom, map, bbox]);

    // Custom Icon styling to highlight and overlay details on top of official city symbols
    const getHydrantIcon = (status, flowClass) => {
      let bgColor = 'transparent'; 
      let borderColor = 'transparent';
      let emoji = '';
      let opacity = '1.0';
      let borderStyle = 'none';

      if (status === 'PRIVATE') {
        bgColor = 'rgba(245, 158, 11, 0.15)'; // Transparent amber highlight fill
        borderColor = '#f59e0b'; // Amber highlighting ring
        borderStyle = '2px solid';
      } else if (status === 'ABANDONED' || status === 'OUT_OF_SERVICE' || status === 'INACTIVE') {
        bgColor = 'rgba(55, 65, 81, 0.6)'; // Dark semi-transparent caution mask
        borderColor = '#ef4444'; // Red caution border
        emoji = '⚠️';
        opacity = '0.9';
        borderStyle = '2px solid';
      }

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
            <div style="
              background-color: ${bgColor};
              border: ${borderStyle} ${borderColor};
              border-radius: 50%;
              width: 24px;
              height: 24px;
              display: flex;
              align-items: center;
              justify-content: center;
              box-shadow: ${status === 'PRIVATE' || emoji ? '0 2px 4px rgba(0,0,0,0.4)' : 'none'};
              font-size: 11px;
              box-sizing: border-box;
              opacity: ${opacity};
            ">${emoji}</div>
            ${labelHtml}
          </div>
        `,
        // Covers vertical height of circle (24px) + margin/text (~20px) = 44px
        iconSize: [32, 48],
        iconAnchor: [16, 12], // Centered horizontally (16) and vertically in the circle (12)
        popupAnchor: [0, -12]
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