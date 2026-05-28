import React, { useEffect, useRef } from 'react';
import { Marker, Tooltip, useMap } from 'react-leaflet';
import L from 'leaflet';
import { dynamicMapLayer } from 'esri-leaflet';
import { BASE_LAYERS, MODE_DEFAULTS } from './MapConstants';

// 🚒 STATIONS
// Coordinates verified against official Coquitlam Fire Hall addresses
const STATIONS = [
    { id: "1", name: "Hall 1", coords: [49.291329039026046, -122.79161362016414] },
    { id: "2", name: "Hall 2", coords: [49.26223510671969, -122.81725512755891] },
    { id: "3", name: "Hall 3", coords: [49.24804277980424, -122.86566519365569] },
    { id: "4", name: "Hall 4", coords: [49.2952132946437, -122.7425391041921] }
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

    // 1. Zoom < 15: Render static Esri image overlay for high performance city-wide view
    React.useEffect(() => {
      if (!visible || zoom >= 15) return;
      
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

    // 2. Zoom >= 15: Fetch dynamic bounding-box vector hydrants for detailed highlights
    const bbox = visible && zoom >= 15 ? map.getBounds().toBBoxString() : "";
    React.useEffect(() => {
      if (!visible || zoom < 15 || !bbox) {
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

    // Custom Icon styling based on GIS status
    const getHydrantIcon = (status, flowClass) => {
      let bgColor = '#ef4444'; // Default Operating (Red)
      let borderColor = '#ffffff';
      let emoji = '💧';
      let opacity = '1.0';
      let borderStyle = '2px solid';

      if (status === 'PRIVATE') {
        bgColor = '#f59e0b'; // Amber
      } else if (status === 'ABANDONED' || status === 'OUT_OF_SERVICE' || status === 'INACTIVE') {
        bgColor = '#374151'; // Dark gray
        borderColor = '#ef4444'; // Red warning border
        emoji = '⚠️';
        opacity = '0.85';
        borderStyle = '2px solid';
      }

      // High-contrast rating label below the circular icon
      const labelHtml = flowClass ? `
        <div style="
          margin-top: 2px;
          font-family: monospace, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, sans-serif;
          font-weight: 900;
          font-size: 10px;
          color: #ffffff;
          text-shadow: -1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000, 1px 1px 0 #000;
          letter-spacing: 0.5px;
          text-align: center;
          line-height: 1;
        ">${flowClass}</div>
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
              box-shadow: 0 2px 4px rgba(0,0,0,0.5);
              font-size: 12px;
              box-sizing: border-box;
              opacity: ${opacity};
            ">${emoji}</div>
            ${labelHtml}
          </div>
        `,
        iconSize: [28, 38],
        iconAnchor: [14, 12], // Centered on the circle (y: 12 is center of 24px circle)
        popupAnchor: [0, -12]
      });
    };

    if (!visible) return null;

    return (
      <>
        {zoom >= 15 && hydrants.map((h, i) => {
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