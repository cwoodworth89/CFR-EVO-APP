// NOTE: For live MapServer endpoints (Parcels, Roads, Zones) and fallback logic, see docs/gis_endpoints.md
import React, { useEffect, useRef } from 'react';
import { Marker, CircleMarker, Tooltip, Popup, Polygon, useMap } from 'react-leaflet';
import L from 'leaflet';
import { BASE_LAYERS, STATIONS } from './MapConstants';
import { TILE_BASE_URL, API_BASE_URL } from '../apiClient';
import { sanitizeAddress } from '../utils/addressUtils';



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
        });
        tileLayer.addTo(map);
        layerRef.current = tileLayer;

        return cleanup;
    }, [map, style, useLabelsFallback]);

    return null;
}

// 🏛️ COQUITLAM CADASTRAL PARCEL & CIVIC ADDRESS OVERLAY (100% Offline Local Authority)
export function CadastralDetailCard({ parcel }) {
  if (!parcel) return null;
  const { address, house, street, zone_id, zonetype1, units, lot, plan, gis_id } = parcel;

  const cleanHouse = house != null ? String(house).trim() : '';
  const cleanStreet = street != null ? String(street).trim() : '';
  const cleanAddress = address != null ? String(address).trim() : '';

  const displayTitle = cleanAddress || (cleanHouse && cleanStreet ? `${cleanHouse} ${cleanStreet}` : cleanStreet || (cleanHouse ? `House #${cleanHouse}` : 'Cadastral Parcel'));
  const displaySubtitle = cleanHouse && cleanStreet ? `House #${cleanHouse} • ${cleanStreet}` : (cleanStreet || (cleanHouse ? `House #${cleanHouse}` : ''));

  return (
    <div className="bg-slate-950 text-white p-2.5 border border-slate-800 rounded-xl shadow-2xl font-mono text-left" style={{ minWidth: '190px', maxWidth: '250px' }}>
      <div className="flex justify-between items-center gap-2 border-b border-slate-850 pb-1.5">
        <span className="text-[9px] text-amber-400 font-mono uppercase tracking-wider font-bold">🏛️ CADASTRAL PARCEL</span>
        {zone_id != null && (
          <span className="px-1.5 py-0.5 rounded text-[8px] font-extrabold tracking-wider bg-sky-950 text-sky-300 border border-sky-800">
            Zone {zone_id}
          </span>
        )}
      </div>
      <h3 className="font-bold text-xs text-white mt-1.5 leading-tight">{displayTitle}</h3>
      {displaySubtitle && (
        <p className="text-[9.5px] text-slate-400 font-mono mt-0.5 font-semibold">
          {displaySubtitle}
        </p>
      )}
      {zonetype1 && (
        <div className="mt-1.5 pt-1 border-t border-slate-850 flex justify-between items-center text-[10px]">
          <span className="text-slate-400 font-sans font-medium">Zoning Type</span>
          <span className="text-amber-300 font-mono font-bold">{zonetype1}</span>
        </div>
      )}
      {units > 1 && (
        <div className="mt-1 flex justify-between items-center text-[10px]">
          <span className="text-slate-400 font-sans font-medium">Total Units</span>
          <span className="text-emerald-400 font-mono font-bold">{units} Units</span>
        </div>
      )}
      {(lot || plan) && (
        <div className="mt-1 pt-1 border-t border-slate-850/60 flex justify-between items-center text-[9px] text-slate-400 font-mono">
          <span>Lot / Plan</span>
          <span className="text-slate-300 font-bold">{lot ? `Lot ${lot}` : ''} {plan ? `Plan ${plan}` : ''}</span>
        </div>
      )}
      {gis_id && (
        <div className="mt-0.5 flex justify-between items-center text-[8.5px] text-slate-500 font-mono">
          <span>GIS ID</span>
          <span>{gis_id}</span>
        </div>
      )}
    </div>
  );
}

const CADASTRAL_LABEL_CACHE = {};

const escapeHtml = (str) => {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
};

const createCadastralLabelIcon = (house, isSmall = false) => {
  const key = `${house}-${isSmall ? 'sm' : 'lg'}`;
  if (!CADASTRAL_LABEL_CACHE[key]) {
    const cls = isSmall ? 'cadastral-house-number cadastral-house-number-sm' : 'cadastral-house-number';
    CADASTRAL_LABEL_CACHE[key] = L.divIcon({
      className: 'cadastral-label-icon-container',
      html: `<span class="${cls}">${escapeHtml(house)}</span>`,
      iconSize: [36, 14],
      iconAnchor: [18, 7],
      popupAnchor: [0, -7]
    });
  }
  return CADASTRAL_LABEL_CACHE[key];
};

export function getParcelBoundaryCoordinates(p) {
  if (!p) return null;

  // Handle GeoJSON Feature
  if (p.type === 'Feature' && p.geometry) {
    p = { ...p.properties, geometry: p.geometry };
  }

  let rawRings = p.rings || p.geometry?.coordinates || p.coordinates || p.polygon || p.geom?.coordinates || p.geojson?.coordinates;

  // Handle JSON stringified rings/coordinates or geometry if passed from raw DB columns
  if (typeof rawRings === 'string') {
    const trimmed = rawRings.trim();
    if (trimmed.startsWith('[') || trimmed.startsWith('{')) {
      try {
        rawRings = JSON.parse(trimmed);
      } catch (e) {
        // Ignore JSON parse failure
      }
    } else if (trimmed.toUpperCase().includes('POLYGON')) {
      // Support WKT POLYGON string
      const wktMatch = trimmed.match(/\(\s*\((.*?)\)\s*\)/s) || trimmed.match(/\(\s*(.*?)\s*\)/s);
      if (wktMatch) {
        const coordPairs = wktMatch[1].split(',').map(pair => {
          const parts = pair.trim().split(/\s+/).map(Number);
          return parts.length >= 2 ? parts : null;
        }).filter(Boolean);
        if (coordPairs.length >= 3) {
          rawRings = [coordPairs];
        }
      }
    }
  }

  // Handle GeoJSON geometry object with coordinates if p.geometry is stringified
  if (typeof p.geometry === 'string') {
    const trimmed = p.geometry.trim();
    if (trimmed.startsWith('{')) {
      try {
        const parsedGeom = JSON.parse(trimmed);
        if (parsedGeom?.coordinates) {
          rawRings = parsedGeom.coordinates;
        }
      } catch (e) {
        // Ignore JSON parse failure
      }
    }
  }

  if (rawRings && Array.isArray(rawRings) && rawRings.length > 0) {
    // Check if 4D MultiPolygon coordinates: [[[[lng, lat], ...]]]
    const isMultiPolygon = Array.isArray(rawRings[0]) && Array.isArray(rawRings[0][0]) && Array.isArray(rawRings[0][0][0]);
    const flattenedRings = isMultiPolygon ? rawRings.flat(1) : rawRings;

    // A single ring is an array of coordinate pairs/objects: [coord1, coord2, ...]
    const firstElem = flattenedRings[0];
    const isSingleRing = !Array.isArray(firstElem) ||
      (!Array.isArray(firstElem[0]) && (typeof firstElem[0] !== 'object' || firstElem[0] === null));
    const rings = isSingleRing ? [flattenedRings] : flattenedRings;

    const parsed = rings.map(ring => {
      if (!Array.isArray(ring)) return [];
      return ring.map(coord => {
        let c0 = null;
        let c1 = null;
        if (Array.isArray(coord) && coord.length >= 2) {
          c0 = parseFloat(coord[0]);
          c1 = parseFloat(coord[1]);
        } else if (coord && typeof coord === 'object') {
          if (coord.lat != null && (coord.lng != null || coord.lon != null)) {
            c0 = parseFloat(coord.lat);
            c1 = parseFloat(coord.lng ?? coord.lon);
          } else if (coord.x != null && coord.y != null) {
            c0 = parseFloat(coord.x);
            c1 = parseFloat(coord.y);
          }
        }
        if (c0 == null || c1 == null || isNaN(c0) || isNaN(c1)) return null;
        // If coordinate 0 is longitude (< -60 or > 90), swap to [lat, lng] for Leaflet
        if (c0 < -60 || Math.abs(c0) > 90) {
          return [c1, c0];
        }
        return [c0, c1];
      }).filter(c => c !== null);
    }).filter(ring => ring.length >= 3);

    if (parsed.length > 0) {
      return isSingleRing ? parsed[0] : (parsed.length === 1 ? parsed[0] : parsed);
    }
  }

  // Extract point coordinates if geometry is Point
  let geomPtLat = null;
  let geomPtLng = null;
  if (p.geometry?.type === 'Point' && Array.isArray(p.geometry.coordinates) && p.geometry.coordinates.length >= 2) {
    geomPtLng = p.geometry.coordinates[0];
    geomPtLat = p.geometry.coordinates[1];
  } else if (Array.isArray(p.coordinates) && p.coordinates.length === 2 && !Array.isArray(p.coordinates[0])) {
    geomPtLng = p.coordinates[0];
    geomPtLat = p.coordinates[1];
  }

  const rawLat = p.lat ?? p.centroid_lat ?? p.latitude ?? geomPtLat;
  const rawLng = p.lng ?? p.centroid_lng ?? p.longitude ?? geomPtLng;
  if (rawLat == null || rawLng == null) return null;

  const lat = parseFloat(rawLat);
  const lng = parseFloat(rawLng);
  if (isNaN(lat) || isNaN(lng) || lat === 0 || lng === 0) return null;

  const rawFLat = p.front_lat;
  const rawFLng = p.front_lng;
  const fLat = rawFLat != null ? parseFloat(rawFLat) : null;
  const fLng = rawFLng != null ? parseFloat(rawFLng) : null;

  if (fLat != null && fLng != null && !isNaN(fLat) && !isNaN(fLng) && (Math.abs(fLat - lat) > 1e-6 || Math.abs(fLng - lng) > 1e-6)) {
    const cosLat = Math.cos((lat * Math.PI) / 180);
    const vy = fLat - lat;
    const vx = (fLng - lng) * cosLat;
    const len = Math.sqrt(vy * vy + vx * vx);

    if (len > 1e-6) {
      const uy = vy / len;
      const ux = vx / len;
      const wy = -ux;
      const wx = uy;

      const depthDist = Math.max(len, 0.00014);
      const widthDist = 0.00010;

      const dLatFront = depthDist * uy;
      const dLngFront = (depthDist * ux) / cosLat;
      const dLatSide = widthDist * wy;
      const dLngSide = (widthDist * wx) / cosLat;

      return [
        [lat + dLatFront + dLatSide, lng + dLngFront + dLngSide],
        [lat + dLatFront - dLatSide, lng + dLngFront - dLngSide],
        [lat - dLatFront - dLatSide, lng - dLngFront - dLngSide],
        [lat - dLatFront + dLatSide, lng - dLngFront + dLngSide]
      ];
    }
  }

  const dLat = 0.00012;
  const dLng = 0.00016;
  return [
    [lat + dLat, lng - dLng],
    [lat + dLat, lng + dLng],
    [lat - dLat, lng + dLng],
    [lat - dLat, lng - dLng]
  ];
}

// Module-level cache for fallback address data (parsed once, queried in memory)
let cachedLocalAddresses = null;
let localAddressesLoadingPromise = null;

const getLocalAddresses = () => {
  if (cachedLocalAddresses) return Promise.resolve(cachedLocalAddresses);
  if (!localAddressesLoadingPromise) {
    const baseUrl = import.meta.env.BASE_URL || '/';
    localAddressesLoadingPromise = fetch(`${baseUrl}data/addresses.json`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(data => {
        cachedLocalAddresses = Array.isArray(data) ? data : [];
        return cachedLocalAddresses;
      })
      .catch(err => {
        localAddressesLoadingPromise = null;
        throw err;
      });
  }
  return localAddressesLoadingPromise;
};

export function CoquitlamOverlays({ visible, onLoadError, onLoadSuccess, targetCoords, minZoom = 14 }) {
  const map = useMap();
  const [zoom, setZoom] = React.useState(map ? map.getZoom() : 12);
  const [boundsTick, setBoundsTick] = React.useState(0);
  const [parcels, setParcels] = React.useState([]);
  const canvasRenderer = React.useMemo(() => L.canvas({ padding: 0.5 }), []);
  const activeReqRef = useRef(0);

  const onLoadErrorRef = useRef(onLoadError);
  onLoadErrorRef.current = onLoadError;
  const onLoadSuccessRef = useRef(onLoadSuccess);
  onLoadSuccessRef.current = onLoadSuccess;

  // Track map zoom and viewport movements (triggers on zoomend and moveend panning)
  useEffect(() => {
    if (!visible) return;

    const handleMapChange = () => {
      setZoom(map.getZoom());
      setBoundsTick(prev => prev + 1);
    };

    map.on('zoomend', handleMapChange);
    map.on('moveend', handleMapChange);
    handleMapChange();

    return () => {
      map.off('zoomend', handleMapChange);
      map.off('moveend', handleMapChange);
    };
  }, [map, visible]);

  // Fetch bounding box parcels from local PostgreSQL FastAPI authority with local static fallback
  useEffect(() => {
    if (!visible || zoom < minZoom) {
      setParcels([]);
      return;
    }

    const reqId = ++activeReqRef.current;
    const controller = new AbortController();

    const bounds = map.getBounds();
    const padLat = (bounds.getNorth() - bounds.getSouth()) * 0.20;
    const padLng = (bounds.getEast() - bounds.getWest()) * 0.20;

    const minLat = bounds.getSouth() - padLat;
    const maxLat = bounds.getNorth() + padLat;
    const minLng = bounds.getWest() - padLng;
    const maxLng = bounds.getEast() + padLng;

    const limit = zoom >= 17 ? 1200 : zoom >= 15 ? 800 : 400;
    const url = `${API_BASE_URL}/api/parcels/bbox?min_lat=${minLat}&min_lng=${minLng}&max_lat=${maxLat}&max_lng=${maxLng}&limit=${limit}&dedupe=true`;

    fetch(url, { signal: controller.signal })
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(data => {
        if (reqId !== activeReqRef.current) return;
        if (data && Array.isArray(data.parcels) && data.parcels.length > 0) {
          setParcels(data.parcels);
          if (typeof onLoadSuccessRef.current === 'function') {
            onLoadSuccessRef.current();
          }
        } else {
          fallbackToLocalAddresses();
        }
      })
      .catch(err => {
        if (err.name === 'AbortError' || reqId !== activeReqRef.current) return;
        fallbackToLocalAddresses();
      });

    function fallbackToLocalAddresses() {
      getLocalAddresses()
        .then(allAddrs => {
          if (reqId !== activeReqRef.current) return;
          if (Array.isArray(allAddrs)) {
            const seen = new Map();
            for (const a of allAddrs) {
              const aLat = parseFloat(a.lat);
              const aLng = parseFloat(a.lng);
              if (isNaN(aLat) || isNaN(aLng)) continue;
              if (aLat < minLat || aLat > maxLat || aLng < minLng || aLng > maxLng) continue;

              const cleanAddr = sanitizeAddress(a.address || '');
              const parts = cleanAddr.split(' ');
              const house = parts[0] || '';
              const street = parts.slice(1).join(' ') || '';
              const key = (house || street) ? `${house}|${street}`.toUpperCase() : `${aLat.toFixed(5)}|${aLng.toFixed(5)}`;

              if (seen.has(key)) {
                const existing = seen.get(key);
                existing.units = (existing.units || 1) + 1;
              } else {
                seen.set(key, {
                  id: `local-${seen.size}-${house}`,
                  address: cleanAddr || a.address,
                  house: house,
                  street: street,
                  units: 1,
                  lat: aLat,
                  lng: aLng,
                  front_lat: a.front_lat != null ? parseFloat(a.front_lat) : aLat,
                  front_lng: a.front_lng != null ? parseFloat(a.front_lng) : aLng
                });
                if (seen.size >= limit) break;
              }
            }

            const mapped = Array.from(seen.values());
            setParcels(mapped);
            if (typeof onLoadSuccessRef.current === 'function') {
              onLoadSuccessRef.current();
            }
          } else {
            setParcels([]);
          }
        })
        .catch(err2 => {
          if (reqId !== activeReqRef.current) return;
          console.warn("Failed to load local cadastral parcels:", err2);
          setParcels([]);
          if (typeof onLoadErrorRef.current === 'function') {
            onLoadErrorRef.current(err2);
          }
        });
    }

    return () => {
      activeReqRef.current++;
      controller.abort();
    };
  }, [map, visible, zoom, boundsTick, minZoom]);

  if (!visible || zoom < minZoom || parcels.length === 0) return null;

  const isSmall = zoom < 16;
  const showCenterDots = zoom >= 15;
  const showLabels = zoom >= 15;

  return (
    <>
      {/* 🏛️ Authentic Municipal Property Parcel Boundary Line Polygons */}
      {parcels.map((p, idx) => {
        const polyCoords = getParcelBoundaryCoordinates(p);
        if (!polyCoords) return null;
        const keyId = p.id != null ? p.id : (p.gis_id || `${p.lat}-${p.lng}-${idx}`);
        return (
          <Polygon
            key={`p-poly-${keyId}`}
            positions={polyCoords}
            renderer={canvasRenderer}
            pathOptions={{
              color: '#0284c7',
              weight: zoom >= 17 ? 1.5 : 1,
              fillColor: '#38bdf8',
              fillOpacity: zoom >= 17 ? 0.08 : 0.04,
              opacity: 0.8
            }}
            interactive={true}
          >
            <Tooltip direction="top" offset={[0, -6]} className="!bg-transparent !border-0 !p-0 !shadow-none">
              <CadastralDetailCard parcel={p} />
            </Tooltip>
            <Popup className="cadastral-popup">
              <CadastralDetailCard parcel={p} />
            </Popup>
          </Polygon>
        );
      })}

      {/* High-Performance Parcel Center Dots (Canvas Renderer, Zero Event Overhead) */}
      {showCenterDots && parcels.map((p, idx) => {
        const pLat = parseFloat(p.lat ?? p.centroid_lat ?? p.latitude);
        const pLng = parseFloat(p.lng ?? p.centroid_lng ?? p.longitude);
        if (isNaN(pLat) || isNaN(pLng)) return null;
        const keyId = p.id != null ? p.id : (p.gis_id || `${pLat}-${pLng}-${idx}`);
        return (
          <CircleMarker
            key={`p-dot-${keyId}`}
            center={[pLat, pLng]}
            radius={zoom >= 17 ? 2.5 : 1.8}
            renderer={canvasRenderer}
            pathOptions={{
              color: '#0284c7',
              fillColor: '#38bdf8',
              fillOpacity: 0.85,
              weight: 1,
              interactive: false
            }}
          />
        );
      })}

      {/* Crisp Municipal House Number Markers (Typography Overlay) */}
      {showLabels && parcels.map((p, idx) => {
        const pLat = parseFloat(p.lat ?? p.centroid_lat ?? p.latitude);
        const pLng = parseFloat(p.lng ?? p.centroid_lng ?? p.longitude);
        if (isNaN(pLat) || isNaN(pLng) || !p.house) return null;
        const keyId = p.id != null ? p.id : (p.gis_id || `${pLat}-${pLng}-${idx}`);
        return (
          <Marker
            key={`p-num-${keyId}`}
            position={[pLat, pLng]}
            icon={createCadastralLabelIcon(p.house, isSmall)}
            interactive={true}
          >
            <Tooltip direction="top" offset={[0, -8]} className="!bg-transparent !border-0 !p-0 !shadow-none">
              <CadastralDetailCard parcel={p} />
            </Tooltip>
            <Popup className="cadastral-popup">
              <CadastralDetailCard parcel={p} />
            </Popup>
          </Marker>
        );
      })}
    </>
  );
}

// 🚒 FIRE ZONES (Rendered via local zones.json layer)
export function FireZonesLayer({ visible, pane }) {
    // Legacy ArcGIS DynamicServices replaced with local zones.json
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

  let flowBadgeColor = 'text-sky-400';
  const fc = (flowClass || '').toUpperCase();
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
      {flowClass && (
        <div className="mt-2 pt-1.5 border-t border-slate-850 flex justify-between items-center text-xs">
          <span className="text-slate-400 font-sans">Flow Rating</span>
          <span className={`font-mono font-bold ${flowBadgeColor}`}>{flowClass}</span>
        </div>
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
    const getHydrantIcon = (status, flowClass) => {
      let bgColor = 'rgba(15, 23, 42, 0.6)';
      let borderColor = '#facc15';
      let borderStyle = '2px solid';
      let opacity = '1.0';
      let isSpecial = false;
      let emoji = '';

      if (status === 'PRIVATE') {
        borderColor = '#f59e0b';
        isSpecial = true;
        emoji = '🔒';
      } else if (status === 'ABANDONED' || status === 'OUT_OF_SERVICE' || status === 'INACTIVE') {
        borderColor = '#ef4444';
        isSpecial = true;
        emoji = '⚠️';
        opacity = '0.9';
      } else {
        const fc = (flowClass || "").toUpperCase();
        if (fc === 'AA') borderColor = '#38bdf8';
        else if (fc === 'A') borderColor = '#4ade80';
        else if (fc === 'B') borderColor = '#fb923c';
        else if (fc === 'C') borderColor = '#f87171';
        else borderColor = '#facc15';
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
        iconSize: [24, 40],
        iconAnchor: [12, 10],
        popupAnchor: [0, -10]
      });
    };

    // Tactical Highlight Icons for Nearest City & Private Hydrants
    const createTacticalHighlightIcon = (isPrivate, gisId, flowClass, distMeters) => {
      const mainColor = isPrivate ? '#f59e0b' : '#00e5ff';
      const badgeTitle = isPrivate ? '🔒 PRIVATE HYDRANT' : '💧 CITY HYDRANT';
      const badgeBg = isPrivate ? 'rgba(245, 158, 11, 0.95)' : 'rgba(2, 132, 199, 0.95)';

      return L.divIcon({
        className: 'custom-tactical-hydrant-highlight',
        html: `
          <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; position: relative;">
            <div style="
              width: 32px;
              height: 32px;
              border: 3px solid ${mainColor};
              border-radius: 50%;
              background: rgba(15, 23, 42, 0.85);
              box-shadow: 0 0 15px ${mainColor}, inset 0 0 10px ${mainColor};
              display: flex;
              align-items: center;
              justify-content: center;
              font-size: 14px;
              animation: pulse 2s infinite;
            ">
              ${isPrivate ? '🔒' : '💧'}
            </div>
            <div style="
              background: ${badgeBg};
              color: #ffffff;
              font-family: monospace, sans-serif;
              font-size: 9px;
              font-weight: 900;
              padding: 2px 6px;
              border-radius: 6px;
              border: 1px solid rgba(255,255,255,0.4);
              box-shadow: 0 4px 10px rgba(0,0,0,0.6);
              white-space: nowrap;
              margin-top: 3px;
              letter-spacing: 0.5px;
            ">
              ${badgeTitle} (${gisId}) • ${distMeters}m ${flowClass ? '• ' + flowClass : ''}
            </div>
          </div>
        `,
        iconSize: [180, 55],
        iconAnchor: [90, 16],
        popupAnchor: [0, -16]
      });
    };

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

          let borderColor = '#facc15';
          const fc = (flowClass || "").toUpperCase();
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

// Official City of Coquitlam Schools GIS Dataset (100% Coquitlam Jurisdiction Parcel Centroids)
export const COQUITLAM_SCHOOLS = [
  // SECONDARY SCHOOLS (9-12)
  { id: 'SCH-01', name: 'Pinetree Secondary', type: 'Secondary (9-12)', lat: 49.290122, lng: -122.791493, address: '3000 Pinewood Ave, Coquitlam' },
  { id: 'SCH-02', name: 'Gleneagle Secondary', type: 'Secondary (9-12)', lat: 49.283844, lng: -122.806786, address: '1195 Lansdowne Dr, Coquitlam' },
  { id: 'SCH-03', name: 'Centennial Secondary', type: 'Secondary (9-12)', lat: 49.252786, lng: -122.849567, address: '570 Poirier St, Coquitlam' },
  { id: 'SCH-04', name: 'Dr. Charles Best Secondary', type: 'Secondary (9-12)', lat: 49.264341, lng: -122.820242, address: '2525 Como Lake Ave, Coquitlam' },
  { id: 'SCH-08', name: 'CABE Secondary', type: 'Secondary (9-12)', lat: 49.256877, lng: -122.854906, address: '1411 Foster Ave, Coquitlam' },

  // MIDDLE SCHOOLS (6-8)
  { id: 'SCH-09', name: 'Como Lake Middle', type: 'Middle (6-8)', lat: 49.252228, lng: -122.859782, address: '1121 King Albert Ave, Coquitlam' },
  { id: 'SCH-10', name: 'École Banting Middle', type: 'Middle (6-8)', lat: 49.265892, lng: -122.876762, address: '820 Banting St, Coquitlam' },
  { id: 'SCH-11', name: 'Hillcrest Middle', type: 'Middle (6-8)', lat: 49.262730, lng: -122.834015, address: '2161 Regan Ave, Coquitlam' },
  { id: 'SCH-12', name: 'Maple Creek Middle', type: 'Middle (6-8)', lat: 49.287890, lng: -122.783570, address: '3700 Townline Rd, Coquitlam' },
  { id: 'SCH-13', name: 'Scott Creek Middle', type: 'Middle (6-8)', lat: 49.284387, lng: -122.812890, address: '1240 Lansdowne Dr, Coquitlam' },
  { id: 'SCH-14', name: 'Summit Middle', type: 'Middle (6-8)', lat: 49.295409, lng: -122.808175, address: '1450 Parkway Blvd, Coquitlam' },

  // ELEMENTARY SCHOOLS (K-5)
  { id: 'SCH-16', name: 'Alderson Elementary', type: 'Elementary (K-5)', lat: 49.239294, lng: -122.875284, address: '825 Gauthier Ave, Coquitlam' },
  { id: 'SCH-17', name: 'Baker Drive Elementary', type: 'Elementary (K-5)', lat: 49.269524, lng: -122.823617, address: '885 Baker Dr, Coquitlam' },
  { id: 'SCH-18', name: 'Bramblewood Elementary', type: 'Elementary (K-5)', lat: 49.298640, lng: -122.812884, address: '2875 Panorama Dr, Coquitlam' },
  { id: 'SCH-19', name: 'Cape Horn Elementary', type: 'Elementary (K-5)', lat: 49.235127, lng: -122.835689, address: '155 Finnigan St, Coquitlam' },
  { id: 'SCH-20', name: 'Coast Salish Elementary', type: 'Elementary (K-5)', lat: 49.297166, lng: -122.738035, address: '3538 Sheffield Ave, Coquitlam' },
  { id: 'SCH-21', name: 'Meadowbrook Elementary', type: 'Elementary (K-5)', lat: 49.272861, lng: -122.804093, address: '900 Meadowbrook Way, Coquitlam' }
];

export function SchoolsLayer({ visible }) {
  if (!visible) return null;

  return (
    <>
      {COQUITLAM_SCHOOLS.map(sch => (
        <Marker
          key={sch.id}
          position={[sch.lat, sch.lng]}
          icon={createSchoolIcon()}
        >
          <Tooltip direction="top" offset={[0, -10]} className="font-bold text-xs bg-slate-950 text-white border border-slate-800 shadow-xl rounded-md p-2">
            <div className="flex flex-col gap-0.5 font-mono">
              <span className="text-[9px] text-blue-400 font-black uppercase tracking-wider">🏫 SCHOOL ZONE</span>
              <span className="text-white text-xs font-bold">{sch.name}</span>
              <span className="text-[8.5px] text-slate-300">{sch.type} — {sch.address}</span>
            </div>
          </Tooltip>
        </Marker>
      ))}
    </>
  );
}