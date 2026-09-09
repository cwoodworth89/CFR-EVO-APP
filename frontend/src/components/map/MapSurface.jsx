import React, { useState, useEffect } from 'react';
import { MapContainer, Pane, ZoomControl, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { BaseMap, CoquitlamOverlays, StationsLayer, HydrantsLayer } from '../MapLayers';
import { BASE_LAYERS } from '../MapConstants';

/**
 * The street basemap and the cadastral overlay, which cannot both carry names.
 *
 * Cadastral tiles begin at z14 and carry their own road names and addresses. Below that
 * the basemap has to provide them, above it the basemap must stop or every street is
 * labelled twice. That handover is one decision about two layers, so it lives here rather
 * than in each caller -- the dispatch route panel does not track zoom at all, and asking
 * every consumer to derive it was how the two surfaces came to disagree (operator,
 * 2026-09-08: the dispatch map had been double-labelled from z14 up, and the console from
 * z14 to z15).
 *
 * `streetLabels` from the caller is intent -- "names are wanted here" -- not a demand for
 * the basemap specifically. This decides where they come from.
 */
function StreetAndCadastral({ baseStyle, streetLabels, showCadastral, onCadastralError }) {
  const map = useMap();
  const [zoom, setZoom] = useState(() => map.getZoom());

  useEffect(() => {
    const sync = () => setZoom(map.getZoom());
    map.on('zoomend', sync);
    sync();
    return () => map.off('zoomend', sync);
  }, [map]);

  const cadastralDrawing = showCadastral && zoom >= BASE_LAYERS.CADASTRAL.minZoom;

  return (
    <>
      <BaseMap style={baseStyle} useLabelsFallback={streetLabels && !cadastralDrawing} />
      <CoquitlamOverlays visible={showCadastral} onLoadError={onCadastralError} />
    </>
  );
}

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

  // Legend for the "no map data" hatch painted by .leaflet-container (#40).
  // Off by default: only the full map surfaces have room for it, and a caption
  // on a small inset panel is noise.
  showNoTileLegend = false,

  // always-on layers
  baseStyle = 'STREET',
  streetLabels = false,
  showCadastral = false,
  onCadastralError,
  showFireHalls = true,
  showHydrants = false,
  // [lat, lng] the hydrant layer measures from: with it the layer draws from zoom 12.
  // `hydrantHighlightIds` (a Set of gisId) names the hydrants to pulse -- the picks of
  // utils/routeHydrants.js -- and without it the layer pulses its own nearest. Punch-list #74.
  hydrantTargetCoords = null,
  hydrantHighlightIds = null,

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

      <StreetAndCadastral
        baseStyle={baseStyle}
        streetLabels={streetLabels}
        showCadastral={showCadastral}
        onCadastralError={onCadastralError}
      />
      <StationsLayer visible={showFireHalls} />
      <HydrantsLayer visible={showHydrants} targetCoords={hydrantTargetCoords} highlightIds={hydrantHighlightIds} />

      {showNoTileLegend && (
        <div
          className="cfr-no-tile-legend"
          title="Hatched areas hold no cached tile for this layer at this zoom. This is missing offline map data, not a tile server failure. See punch-list #40."
        >
          No map data at this zoom
        </div>
      )}

      {children}
    </MapContainer>
  );
}
