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
    useEffect(() => {
      if (!visible) return;
      
      const layer = dynamicMapLayer({
          url: "https://geodata.coquitlam.ca/arcgis/rest/services/DynamicServices/Water/MapServer",
          layers: [2], // 2 = Water Hydrants
          opacity: 0.9,
          f: 'image'
      }).addTo(map);

      return () => { 
          map.removeLayer(layer);
      };
    }, [map, visible]);
    
    return null;
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