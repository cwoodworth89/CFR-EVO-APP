// NOTE: For live MapServer endpoints (Parcels, Roads, Zones) and fallback logic, see docs/gis_endpoints.md
import React, { useEffect, useRef } from 'react';
import { Marker, CircleMarker, Tooltip, Popup, Polygon, useMap } from 'react-leaflet';
import L from 'leaflet';
import { BASE_LAYERS, MODE_DEFAULTS, STATIONS } from './MapConstants';
import { TILE_BASE_URL } from '../apiClient';



// 🚒 Custom Fire Hall Icon Loader (Memoized to prevent render flicker)
const BASE_URL = import.meta.env.BASE_URL || '/';
const STATION_ICON_CACHE = {};

export const createFireHallIcon = (stationId = '1') => {
  const key = String(stationId);
  if (!STATION_ICON_CACHE[key]) {
    STATION_ICON_CACHE[key] = L.divIcon({
      className: 'custom-station-user-icon',
      html: `<div style="position:relative;display:flex;align-items:center;justify-content:center;background:transparent;border:none;border-radius:50%;opacity:0.95;filter:drop-shadow(0 3px 6px rgba(0,0,0,0.85));cursor:pointer;">
        <img src="${BASE_URL}icons/fire_hall.png" 
             style="width:38px;height:38px;max-width:38px;max-height:38px;object-fit:cover;border-radius:50%;overflow:hidden;background:transparent;border:none;display:block;" 
             alt="Fire Hall ${key}" />
        <span style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);background:rgba(15,23,42,0.92);color:#fbbf24;border:1.5px solid #fbbf24;border-radius:9999px;font-size:11px;font-weight:900;width:18px;height:18px;display:flex;align-items:center;justify-content:center;font-family:monospace;box-shadow:0 2px 5px rgba(0,0,0,0.8);pointer-events:none;">${key}</span>
      </div>`,
      iconSize: [38, 38],
      iconAnchor: [19, 19],
      popupAnchor: [0, -19]
    });
  }
  return STATION_ICON_CACHE[key];
};

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

        const disableWan = String(import.meta.env.VITE_DISABLE_WAN_FALLBACK || 'false').toLowerCase() === 'true';
        const config = BASE_LAYERS[style] || BASE_LAYERS.GREY;
        let url = typeof config === 'string' ? config : (config.url || BASE_LAYERS.GREY.url || `${TILE_BASE_URL}/services/street_nolabels/tiles/{z}/{x}/{y}.png`);
        let fallbackUrl = disableWan ? null : (typeof config === 'object' ? config.fallbackUrl : null);

        if (useLabelsFallback && url && url.includes('_nolabels')) {
            url = url.replace('_nolabels', '');
        }
        if (useLabelsFallback && fallbackUrl && fallbackUrl.includes('_nolabels')) {
            fallbackUrl = fallbackUrl.replace('_nolabels', '');
        }

        const attribution = typeof config === 'object' ? config.attribution : '© OpenStreetMap contributors (Offline Local)';
        const subdomains = typeof config === 'object' ? config.subdomains : ['a', 'b', 'c', 'd'];
        const maxNativeZoom = typeof config === 'object' ? (config.maxNativeZoom ?? 18) : 18;
        const maxZoom = typeof config === 'object' ? (config.maxZoom ?? 22) : 22;

        // Custom Leaflet TileLayer with graceful online fallback support
        const FallbackTileLayer = L.TileLayer.extend({
            createTile: function(coords, done) {
                const tile = document.createElement('img');

                if (this.options.crossOrigin || this.options.crossOrigin === '') {
                    tile.crossOrigin = this.options.crossOrigin === true ? '' : this.options.crossOrigin;
                }

                tile.alt = '';
                tile.setAttribute('role', 'presentation');

                let fallbackTried = false;

                const onLoad = () => {
                    done(null, tile);
                };

                const onError = (e) => {
                    if (fallbackUrl && !fallbackTried) {
                        fallbackTried = true;
                        let sub = 'a';
                        if (Array.isArray(subdomains) && subdomains.length > 0) {
                            sub = subdomains[Math.abs(coords.x + coords.y) % subdomains.length];
                        }
                        const fUrl = fallbackUrl
                            .replace('{s}', sub)
                            .replace('{z}', coords.z)
                            .replace('{x}', coords.x)
                            .replace('{y}', coords.y)
                            .replace('{r}', '');
                        tile.src = fUrl;
                    } else {
                        done(e, tile);
                    }
                };

                L.DomEvent.on(tile, 'load', onLoad);
                L.DomEvent.on(tile, 'error', onError);

                tile.src = this.getTileUrl(coords);
                return tile;
            }
        });

        const tileLayer = new FallbackTileLayer(url, {
            attribution: attribution,
            subdomains: subdomains,
            maxNativeZoom: maxNativeZoom,
            maxZoom: maxZoom,
            noWrap: true,
            crossOrigin: "anonymous",
            pane: "tilePane",
            zIndex: 100,
        });
        tileLayer.addTo(map);
        layerRef.current = tileLayer;

        return cleanup;
    }, [map, style, useLabelsFallback]);

    return null;
}

// 🏗️ COQUITLAM ROADS/PARCELS (100% Offline Local MBTiles overlay via mbtileserver on port 8081)
export function CoquitlamOverlays({ visible, onLoadError }) {
    const map = useMap();
    useEffect(() => {
      if (!visible) return;
      
      const overlayLayer = L.tileLayer(
          `${TILE_BASE_URL}/services/cadastral/tiles/{z}/{x}/{y}.png`,
          {
              transparent: true,
              opacity: 0.9,
              maxNativeZoom: 20,
              maxZoom: 22,
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
export function HydrantsLayer({ visible, targetCoords, minZoom = 12 }) {
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
          
          const isNearestCity = nearestCity && nearestCity.gisId === gisId;
          const isNearestPrivate = nearestPrivate && nearestPrivate.gisId === gisId;
          const isNearest = isNearestCity || isNearestPrivate;

          let label = "OPERATING";
          if (statusVal === "PRIVATE") label = "PRIVATE";
          if (statusVal === "ABANDONED" || statusVal === "OUT_OF_SERVICE" || statusVal === "INACTIVE") label = "OUT OF SERVICE";

          // Unrated hydrants get a neutral grey, deliberately outside the four NFPA
          // 291 colours, so an unknown rating can never be mistaken for a class.
          const fc = (flowClass || "").toUpperCase();
          const isRated = ['AA', 'A', 'B', 'C'].includes(fc);
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
                className: isNearest ? 'animate-pulse' : ''
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
export const createRailroadCrossingIcon = () => L.divIcon({
  className: 'custom-rr-user-icon',
  html: `<div style="display:flex;align-items:center;justify-content:center;border-radius:50%;opacity:0.88;filter:drop-shadow(0 3px 6px rgba(0,0,0,0.85));cursor:pointer;">
    <img src="${BASE_URL}icons/railroad_crossing.png" 
         onerror="this.onerror=null; this.src='${BASE_URL}icons/railroad_crossing.svg';" 
         style="width:34px;height:34px;max-width:34px;max-height:34px;object-fit:cover;border-radius:50%;overflow:hidden;display:block;" 
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
  html: `<div style="display:flex;align-items:center;justify-content:center;border-radius:50%;opacity:0.88;filter:drop-shadow(0 3px 6px rgba(0,0,0,0.85));cursor:pointer;">
    <img src="${BASE_URL}icons/school.png" 
         onerror="this.onerror=null; this.src='${BASE_URL}icons/school.svg';" 
         style="width:32px;height:32px;max-width:32px;max-height:32px;object-fit:cover;border-radius:50%;overflow:hidden;display:block;" 
         alt="School" />
  </div>`,
  iconSize: [32, 32],
  iconAnchor: [16, 16],
  popupAnchor: [0, -16]
});
