import React from 'react';
import { useMapEvents } from 'react-leaflet';

// COMPONENT: Handle Map Clicks
export function MapClickEvents({ onMapClick }) {
  useMapEvents({ click: (e) => onMapClick && onMapClick(e.latlng) });
  return null;
}
