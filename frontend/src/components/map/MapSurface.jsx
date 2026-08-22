import React from 'react';
import { MapContainer, Pane, ZoomControl } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { BaseMap, CoquitlamOverlays, StationsLayer, HydrantsLayer } from '../MapLayers';

/**
 * The one map. Owns the Leaflet container, the custom panes, and the layers that are on
 * in every mode; everything mode-specific is passed as children.
 *
 * Step 3 of docs/architecture/unified_map_surface.md. The workstation console and the
 * dispatch display each had their own `<MapContainer>` mounting the same base, overlay,
 * station and hydrant layers with slightly different options. What legitimately differs is
 * which *extra* layers mount and how the view is fitted, not how the map is built.
 *
 * Children render inside the container, so they can use `useMap` and the react-leaflet
 * context exactly as if they were written inline.
 *
 * Panes exist so zone fills sit under the base labels and zone numbers sit above them.
 * They are declared here rather than by ZonesLayer because a pane is a property of the
 * map, not of a layer, and two layers referencing the same pane must not both create it.
 */

/** Layer stacking. Leaflet's own overlayPane is 400, so these bracket it. */
const PANE_Z = {
  underlay: 390, // below base map labels — zone fills
  labels: 410,   // above base map labels — zone numbers
};

export default function MapSurface({
  // container
  center,
  zoom = 12,
  minZoom,
  maxZoom,
  maxBounds,
  maxBoundsViscosity,
  mapRef,
  className = 'bg-slate-900',
  style = { height: '100%', width: '100%' },
  zoomControl = false,
  zoomControlPosition = 'bottomright',

  // always-on layers
  baseStyle = 'VOYAGER',
  showCadastral = false,
  onCadastralError,
  showFireHalls = true,
  showHydrants = false,

  children,
}) {
  return (
    <MapContainer
      center={center}
      zoom={zoom}
      minZoom={minZoom}
      maxZoom={maxZoom}
      maxBounds={maxBounds}
      maxBoundsViscosity={maxBoundsViscosity}
      style={style}
      className={className}
      zoomControl={false}
      ref={mapRef}
    >
      {zoomControl && <ZoomControl position={zoomControlPosition} />}

      <Pane name="underlayPane" style={{ zIndex: PANE_Z.underlay }} />
      <Pane name="labelsPane" style={{ zIndex: PANE_Z.labels }} />

      <BaseMap style={baseStyle} useLabelsFallback={false} />
      <CoquitlamOverlays visible={showCadastral} onLoadError={onCadastralError} />
      <StationsLayer visible={showFireHalls} />
      <HydrantsLayer visible={showHydrants} />

      {children}
    </MapContainer>
  );
}
