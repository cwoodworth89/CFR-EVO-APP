// NOTE: For live MapServer endpoints (Parcels, Roads, Zones) and fallback logic, see docs/gis_endpoints.md
import React, { useEffect, useRef } from 'react';
import { Marker, CircleMarker, Tooltip, Popup, Polygon, useMap } from 'react-leaflet';
import L from 'leaflet';
import '@maplibre/maplibre-gl-leaflet';
import 'maplibre-gl/dist/maplibre-gl.css';
import { BASE_LAYERS, CADASTRAL_MIN_ZOOM, MODE_DEFAULTS, STATIONS } from './MapConstants';
import { loadStreetStyle, setLabelsVisible, capRoadNames } from './map/vectorBasemap';
import { API_BASE_URL, TILE_BASE_URL } from '../apiClient';
import { createFireHallIcon, createRailroadCrossingIcon } from './map/layerIcons';
import { COQUITLAM_RAILROAD_CROSSINGS } from './map/railroadCrossings';



// 🚒 Custom Fire Hall Icon Loader (Memoized to prevent render flicker)
const BASE_URL = import.meta.env.BASE_URL || '/';

export function BaseMap({ style, useLabelsFallback, cadastralNames = false }) {
    const map = useMap();
    const layerRef = useRef(null);
    const glRef = useRef(null);
    // The latest label props, read by the style-load handler however late it fires.
    const wantRef = useRef({ labels: useLabelsFallback, cadastralNames });
    wantRef.current = { labels: useLabelsFallback, cadastralNames };

    // Labels and the cadastral handover are style properties of the vector map, applied
    // in place. On the raster they were a second tile set, and switching it mid-zoom read
    // as a basemap reload to the operator (2026-09-08); nothing here rebuilds the layer.
    const applyLabelState = () => {
        const gl = glRef.current;
        if (!gl || !gl.isStyleLoaded()) return;
        const want = wantRef.current;
        setLabelsVisible(gl, want.labels !== false);
        capRoadNames(gl, want.cadastralNames ? CADASTRAL_MIN_ZOOM : null);
    };

    useEffect(() => {
        const cleanup = () => {
            glRef.current = null;
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

        const config = BASE_LAYERS[style] || BASE_LAYERS.STREET;

        if (config.type === 'vector') {
            // The street basemap: MapLibre GL in a Leaflet layer, so every overlay pane
            // (zones, hydrants, parcels, routes, closures) is untouched.
            let cancelled = false;
            loadStreetStyle().then((glStyle) => {
                if (cancelled) return;
                const layer = L.maplibreGL({
                    style: glStyle,
                    pane: 'tilePane',
                    interactive: false,
                    maxZoom: config.maxZoom,
                    attributionControl: { customAttribution: config.attribution },
                });
                layer.addTo(map);
                layerRef.current = layer;
                glRef.current = layer.getMaplibreMap();
                glRef.current.on('style.load', applyLabelState);
                applyLabelState();
            }).catch((error) => {
                // No basemap. The "no map data" hatch on .leaflet-container stays visible
                // and says so (punch-list #40); nothing is drawn in its place (CLAUDE.md s6.1).
                console.error('Street basemap unavailable; the hatch stands in for it:', error);
            });
            return () => { cancelled = true; cleanup(); };
        }

        // Raster archives (the aerial layer): plain tiles from cfr_tiles. The online
        // fallback class that used to live here never had a URL to fall back to
        // (fallbackUrl is null on every layer, CLAUDE.md s1) and is gone.
        const tileLayer = L.tileLayer(config.url, {
            attribution: config.attribution,
            maxNativeZoom: config.maxNativeZoom ?? 18,
            maxZoom: config.maxZoom ?? 22,
            noWrap: true,
            crossOrigin: "anonymous",
            pane: "tilePane",
            zIndex: 100,
        });
        tileLayer.addTo(map);
        layerRef.current = tileLayer;

        return cleanup;
    // applyLabelState reads the props through wantRef; the label effect below owns changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [map, style]);

    useEffect(() => {
        applyLabelState();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [useLabelsFallback, cadastralNames]);

    return null;
}

// 🏗️ COQUITLAM ROADS/PARCELS (100% Offline Local MBTiles overlay via mbtileserver on port 8081)
export function CoquitlamOverlays({ visible, onLoadError }) {
    const map = useMap();
    useEffect(() => {
      if (!visible) return;
      
      // URL and zoom depths come from BASE_LAYERS.CADASTRAL, where every other layer's
      // config lives. They were written out again here, identically, so the constant was
      // dead while the real layer carried its own copy -- two definitions that happened to
      // agree. Opacity, pane and z-index stay local: those are this overlay's rendering
      // decisions, not part of what the layer IS.
      const cadastral = BASE_LAYERS.CADASTRAL;
      const overlayLayer = L.tileLayer(
          cadastral.url,
          {
              transparent: true,
              opacity: 0.9,
              attribution: cadastral.attribution,
              maxNativeZoom: cadastral.maxNativeZoom,
              maxZoom: cadastral.maxZoom,
              pane: "overlayPane",
              zIndex: 350
          }
      );
      // MapBoard passes onLoadError to surface a cadastral outage; without this
      // listener the callback was never invoked and the banner could never appear.
      if (onLoadError) overlayLayer.on('tileerror', onLoadError);
      overlayLayer.addTo(map);

      return () => {
        try {
          if (map.hasLayer(overlayLayer)) {
            map.removeLayer(overlayLayer);
          }
        } catch { /* non-fatal: caller handles the absent value */ }
      };
    }, [map, visible, onLoadError]);
    
    return null;
}

// Helper distance function (Haversine formula in meters)
function getDistanceMeters(lat1, lon1, lat2, lon2) {
  if (lat1 == null || lon1 == null || lat2 == null || lon2 == null) return Infinity;
  const R = 6371000;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

// Unified single-source Hydrant Detail Card component for both hover Tooltip & click Popup
function HydrantDetailCard({ gisId, statusVal, flowClass, label }) {
  const isOperating = label === 'OPERATING';
  const isPrivate = label === 'PRIVATE';

  const statusStyle = isOperating
    ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
    : isPrivate
    ? 'bg-amber-500/20 text-amber-400 border-amber-500/30'
    : 'bg-rose-500/20 text-rose-400 border-rose-500/30';

  // An unrated hydrant must say so. The City records no flow_class for private
  // hydrants; a previous sync default wrote "AA" (the HIGHEST NFPA 291 class), which
  // told crews an unrated hydrant was the best available supply. Blank is not good
  // enough either -- absence of a badge reads as "nothing to report".
  const fc = (flowClass || '').toUpperCase();
  const isRated = ['AA', 'A', 'B', 'C'].includes(fc);

  let flowBadgeColor = 'text-slate-400';
  if (fc === 'AA') flowBadgeColor = 'text-sky-400';
  else if (fc === 'A') flowBadgeColor = 'text-emerald-400';
  else if (fc === 'B') flowBadgeColor = 'text-amber-400';
  else if (fc === 'C') flowBadgeColor = 'text-rose-400';

  return (
    <div className="bg-slate-950 text-white p-2.5 border border-slate-800 rounded-xl shadow-2xl font-mono" style={{ minWidth: '180px', maxWidth: '240px' }}>
      <div className="flex justify-between items-center gap-2 border-b border-slate-850 pb-1.5">
        <span className="text-[9px] text-slate-400 font-mono uppercase tracking-wider font-bold">HYDRANT DETAIL</span>
        <span className={`px-1.5 py-0.5 rounded text-[8px] font-extrabold tracking-wider border ${statusStyle}`}>
          {label}
        </span>
      </div>
      <h3 className="font-bold text-sm text-sky-400 mt-1.5 leading-tight">ID: {gisId}</h3>
      <div className="mt-2 pt-1.5 border-t border-slate-850 flex justify-between items-center text-xs">
        <span className="text-slate-400 font-sans">Flow Rating</span>
        {isRated ? (
          <span className={`font-mono font-bold ${flowBadgeColor}`}>{fc}</span>
        ) : (
          <span className="font-mono font-black text-amber-300 bg-amber-950/60 border border-amber-700/70 px-1.5 py-0.5 rounded text-[10px] tracking-wider">
            ⚠️ UNRATED
          </span>
        )}
      </div>
      {!isRated && (
        <p className="mt-1 text-[9px] text-amber-300/90 font-sans leading-snug">
          No NFPA 291 flow rating on record for this hydrant. Confirm supply on scene.
        </p>
      )}
      <div className="mt-1 flex justify-between items-center text-xs">
        <span className="text-slate-400 font-sans font-medium">Status</span>
        <span className="text-slate-300 font-mono font-semibold">{statusVal}</span>
      </div>
    </div>
  );
}

// 💧 NEW: WATER HYDRANTS GIS LAYER
export function HydrantsLayer({ visible, targetCoords, minZoom = 12, highlightIds = null }) {
    const map = useMap();
    const [zoom, setZoom] = React.useState(map.getZoom());
    const [hydrants, setHydrants] = React.useState([]);
    const [allHydrants, setAllHydrants] = React.useState([]);
    const [boundsTick, setBoundsTick] = React.useState(0);

    // Track map zoom and movements
    React.useEffect(() => {
      if (!visible) return;

      const handleMapChange = () => {
        setZoom(map.getZoom());
        setBoundsTick(prev => prev + 1);
      };

      map.on('zoomend', handleMapChange);
      map.on('moveend', handleMapChange);
      map.on('move', handleMapChange);
      
      handleMapChange();

      return () => {
        map.off('zoomend', handleMapChange);
        map.off('moveend', handleMapChange);
        map.off('move', handleMapChange);
      };
    }, [map, visible]);

    // Load the hydrant inventory from public.hydrants via the API.
    // Previously fetched frontend/public/data/hydrants.json directly, which could drift
    // from the database and bypassed the null-flow_class contract.
    React.useEffect(() => {
      if (!visible) return;

      fetch(`${API_BASE_URL}/api/hydrants`)
        .then(r => {
          if (!r.ok) throw new Error("HTTP " + r.status);
          return r.json();
        })
        .then(data => {
          setAllHydrants(Array.isArray(data) ? data : []);
        })
        .catch(err => {
          console.warn("Failed to load hydrants from API:", err);
        });
    }, [visible]);

    // Filter local hydrants in-memory with 25% viewport buffer padding
    React.useEffect(() => {
      const activeMinZoom = targetCoords ? minZoom : 16;
      if (!visible || zoom < activeMinZoom || allHydrants.length === 0) {
        setHydrants([]);
        return;
      }

      const bounds = map.getBounds();
      const padLat = (bounds.getNorth() - bounds.getSouth()) * 0.25;
      const padLng = (bounds.getEast() - bounds.getWest()) * 0.25;

      const minLng = bounds.getWest() - padLng;
      const maxLng = bounds.getEast() + padLng;
      const minLat = bounds.getSouth() - padLat;
      const maxLat = bounds.getNorth() + padLat;

      const filtered = allHydrants.filter(h => 
        h.lng >= minLng && h.lng <= maxLng &&
        h.lat >= minLat && h.lat <= maxLat
      );

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
    }, [visible, zoom, map, boundsTick, allHydrants, targetCoords, minZoom]);

    // Calculate nearest City Hydrant & nearest Private Hydrant to targetCoords
    const { nearestCity, nearestPrivate } = React.useMemo(() => {
      if (!targetCoords || !Array.isArray(targetCoords) || targetCoords.length < 2 || allHydrants.length === 0) {
        return { nearestCity: null, nearestPrivate: null };
      }
      const [tLat, tLng] = targetCoords;
      let cBest = null;
      let cMin = Infinity;
      let pBest = null;
      let pMin = Infinity;

      for (const h of allHydrants) {
        const d = getDistanceMeters(tLat, tLng, h.lat, h.lng);
        const st = (h.status || '').toUpperCase();
        if (st === 'PRIVATE') {
          if (d < pMin && d <= 400) {
            pMin = d;
            pBest = { ...h, distMeters: Math.round(d) };
          }
        } else if (st !== 'ABANDONED' && st !== 'OUT_OF_SERVICE' && st !== 'INACTIVE') {
          if (d < cMin && d <= 800) {
            cMin = d;
            cBest = { ...h, distMeters: Math.round(d) };
          }
        }
      }
      return { nearestCity: cBest, nearestPrivate: pBest };
    }, [targetCoords, allHydrants]);

    // Custom Icon styling

    // Tactical Highlight Icons for Nearest City & Private Hydrants

    const canvasRenderer = React.useMemo(() => L.canvas({ padding: 0.5 }), []);

    if (!visible) return null;

    const activeMinZoom = targetCoords ? minZoom : 16;

    return (
      <>
        {/* Viewport Hydrants (Nearest Hydrant Dot Pulses Smoothly) */}
        {zoom >= activeMinZoom && hydrants.map((h, i) => {
          if (!h.geometry || h.geometry.x === undefined || h.geometry.y === undefined) return null;
          const coords = [h.geometry.y, h.geometry.x];
          const statusVal = (h.attributes.status || "").toUpperCase();
          const gisId = h.attributes.gis_id || "Unknown";
          const flowClass = h.attributes.flow_class || "";
          
          // With `highlightIds` the caller has already chosen (utils/routeHydrants.js, the
          // operator's along-the-route rule) and the layer only draws; without it the layer
          // falls back to its own nearest-city / nearest-private pick.
          const isNearestCity = highlightIds ? false : Boolean(nearestCity && nearestCity.gisId === gisId);
          const isNearestPrivate = highlightIds
            ? (highlightIds.has(gisId) && statusVal === 'PRIVATE')
            : Boolean(nearestPrivate && nearestPrivate.gisId === gisId);
          const isNearest = highlightIds ? highlightIds.has(gisId) : (isNearestCity || isNearestPrivate);

          let label = "OPERATING";
          if (statusVal === "PRIVATE") label = "PRIVATE";
          if (statusVal === "ABANDONED" || statusVal === "OUT_OF_SERVICE" || statusVal === "INACTIVE") label = "OUT OF SERVICE";

          // Unrated hydrants get a neutral grey, deliberately outside the four NFPA
          // 291 colours, so an unknown rating can never be mistaken for a class.
          const fc = (flowClass || "").toUpperCase();
          let borderColor = '#94a3b8';
          if (fc === 'AA') borderColor = '#38bdf8';
          else if (fc === 'A') borderColor = '#4ade80';
          else if (fc === 'B') borderColor = '#fb923c';
          else if (fc === 'C') borderColor = '#f87171';
          if (statusVal === 'PRIVATE') borderColor = '#f59e0b';
          if (statusVal === 'ABANDONED' || statusVal === 'OUT_OF_SERVICE' || statusVal === 'INACTIVE') borderColor = '#ef4444';

          return (
            <CircleMarker
              key={`canvas-${gisId}-${i}`}
              center={coords}
              radius={isNearest ? 7.5 : 5}
              renderer={canvasRenderer}
              pathOptions={{
                color: isNearest ? (isNearestPrivate ? '#f59e0b' : '#38bdf8') : '#0f172a',
                fillColor: borderColor,
                fillOpacity: isNearest ? 1 : 0.95,
                weight: isNearest ? 3 : 1.5,
                className: isNearest ? 'motion-safe:animate-pulse' : ''
              }}
            >
              <Tooltip direction="top" offset={[0, -6]} className="!bg-transparent !border-0 !p-0 !shadow-none">
                <HydrantDetailCard gisId={gisId} statusVal={statusVal} flowClass={flowClass} label={label} />
              </Tooltip>
              <Popup className="hydrant-popup">
                <HydrantDetailCard gisId={gisId} statusVal={statusVal} flowClass={flowClass} label={label} />
              </Popup>
            </CircleMarker>
          );
        })}
      </>
    );
}

export function StationsLayer({ visible = true }) {
    if (!visible) return null;
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
