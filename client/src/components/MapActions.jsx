import React, { useEffect } from 'react';
import { useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';

// COMPONENT: Handle Map Clicks
export function MapClickEvents({ onMapClick }) {
  useMapEvents({ click: (e) => onMapClick(e.latlng) });
  return null;
}

// COMPONENT: Smart Zoom Logic
export function SmartZoom({ target, mode, allBlocks, allZones }) {
  const map = useMap();
  
  useEffect(() => {
    if (!target) return;
    let bounds;
    
    // 1. ZONES: Zoom to Target (Zoom 13 - District View)
    if (mode === "QUIZ_ZONES") {
        const latLngs = target.geometry.coordinates[0].map(c => [c[1], c[0]]);
        bounds = L.latLngBounds(latLngs);
        map.flyTo(bounds.getCenter(), 13, { animate: true });
    }

    // 2. BLOCKS: Zoom to the correct neighborhood around the target segment with search jitter
    else if (mode === "QUIZ_BLOCKS") {
      // Calculate center of the target polyline
      const start = target.coordinates[0];
      const end = target.coordinates[1];
      const centerLat = (start[0] + end[0]) / 2;
      const centerLng = (start[1] + end[1]) / 2;

      // Add a minor search jitter (+/- 150m) to avoid giving away the exact center
      const latOffset = (Math.random() - 0.5) * 0.003;
      const lngOffset = (Math.random() - 0.5) * 0.004;

      const searchCenter = [centerLat + latOffset, centerLng + lngOffset];
      map.flyTo(searchCenter, 15, { animate: true });
    }

    // 3. ADDRESSES: "Search Area" Style
    // Updated: Zoom out slightly (16) and randomize center so it's not dead-center
    else if (mode === "QUIZ_ADDRESSES") {
        // Create a random offset (Jitter)
        // +/- 0.003 degrees is roughly +/- 300 meters
        const latOffset = (Math.random() - 0.5) * 0.006; 
        const lngOffset = (Math.random() - 0.5) * 0.008; 

        const newCenter = [
            target.lat + latOffset, 
            target.lng + lngOffset
        ];

        // Zoom 16 = "Block View" (Good for finding numbers, but requires searching)
        map.flyTo(newCenter, 16, { animate: true });
    }

  }, [target, map, mode, allBlocks, allZones]);
  return null;
}

// COMPONENT: Feedback Zoom
export function ZoomToFeedback({ guessBlock, targetBlock, mode }) {
  const map = useMap();
  useEffect(() => {
    if (mode === "QUIZ_BLOCKS" && guessBlock && targetBlock) {
      const points = [...guessBlock.coordinates, ...targetBlock.coordinates];
      const bounds = L.latLngBounds(points);
      map.fitBounds(bounds, { paddingTopLeft: [100, 100], paddingBottomRight: [350, 100], maxZoom: 17, animate: true });
    }
  }, [guessBlock, targetBlock, mode, map]);
  return null;
}