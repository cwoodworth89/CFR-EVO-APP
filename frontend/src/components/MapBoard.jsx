/* global __BUILD_DATE__ */
// NOTE: For details on local GIS JSONs (hydrants.json, zones.json) and map layout config, see docs/gis_endpoints.md
import React, { useEffect, useState, useRef, useCallback, useMemo } from 'react'; // Added useRef, useCallback, useMemo
import { MapContainer, Polygon, CircleMarker, Polyline, Tooltip, Pane, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import * as turf from '@turf/turf';
import L from 'leaflet';

// Import from your other components
import { BaseMap, CoquitlamOverlays, StationsLayer, FireZonesLayer, HydrantsLayer, RailroadCrossingsLayer, SchoolsLayer } from './MapLayers';
import { MapClickEvents } from './MapActions';
import { Header, LeftSidebar, RightSidebar } from './DashboardHUD';
import { MODE_DEFAULTS, UNIT_COLORS, STATIONS_MAP as STATIONS, KNOWN_BUILDINGS, OPERATIONAL_BOUNDS, COQUITLAM_CENTER } from './MapConstants';
import { apiClient } from '../apiClient';

export function enrichAddressWithBuilding(targetObj) {
  if (!targetObj) return null;
  const rawAddr = (targetObj.address || '').toUpperCase().trim();
  
  const matchedBuilding = KNOWN_BUILDINGS.find(b => {
    if (rawAddr.includes(b.name.toUpperCase())) return true;
    if (rawAddr.includes(b.address.toUpperCase())) return true;
    return b.aliases.some(alias => rawAddr.includes(alias));
  });

  if (matchedBuilding) {
    return {
      ...targetObj,
      address: matchedBuilding.address,
      buildingName: matchedBuilding.name,
      lat: matchedBuilding.frontEntrance ? matchedBuilding.frontEntrance[0] : matchedBuilding.lat,
      lng: matchedBuilding.frontEntrance ? matchedBuilding.frontEntrance[1] : matchedBuilding.lng,
      frontEntrance: matchedBuilding.frontEntrance,
      note: matchedBuilding.note
    };
  }

  return targetObj;
}

import { RoutingOverlay } from './RoutingOverlay';
import PropertySatellitePanel from './kiosk/PropertySatellitePanel';
import StreetViewPanel from './kiosk/StreetViewPanel';
import { calculateEVORouteMetrics, DEFAULT_ROUTING_CONFIG } from '../utils/EVORoutingEngine';

// Lazy-load heavy administrative and configuration modals to reduce initial kiosk bundle size
const DispatchReview = React.lazy(() => import('./DispatchReview'));
const DriverStationSetup = React.lazy(() => import('./DriverStationSetup'));
const EVORoutingConfigModal = React.lazy(() => import('./EVORoutingConfigModal'));

const ModalLoadingFallback = () => (
  <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-[2000] flex items-center justify-center select-none font-mono">
    <div className="flex items-center gap-3 bg-slate-900 border border-slate-800 px-5 py-3 rounded-2xl text-slate-300 text-xs shadow-2xl">
      <span className="animate-spin border-2 border-sky-400 border-t-transparent h-4 w-4 rounded-full"></span>
      <span>Loading Interface...</span>
    </div>
  </div>
);
import { sanitizeAddress } from '../utils/addressUtils';
import { useDispatchListener } from '../hooks/useDispatchListener';

// 🎲 Pure utility function to pick a random element, satisfying React 19 render purity rules
const getRandomElement = (arr) => {
  if (!arr || arr.length === 0) return null;
  const index = Math.floor(Math.random() * arr.length);
  return arr[index];
};

const getZoneCentroid = (zone) => {
  if (!zone || !zone.geometry || !zone.geometry.coordinates || !zone.geometry.coordinates[0]) return null;
  const coords = zone.geometry.coordinates[0];
  let minLat = 90, maxLat = -90, minLng = 180, maxLng = -180;
  coords.forEach(pt => {
    const lng = pt[0];
    const lat = pt[1];
    if (lat < minLat) minLat = lat;
    if (lat > maxLat) maxLat = lat;
    if (lng < minLng) minLng = lng;
    if (lng > maxLng) maxLng = lng;
  });
  return [(minLat + maxLat) / 2, (minLng + maxLng) / 2];
};

const createSoftZoneNumberIcon = (zoneId) => L.divIcon({
  className: 'soft-zone-number-marker',
  html: `<div style="display:flex;align-items:center;justify-content:center;color:#0f172a;font-weight:800;font-size:12px;font-family:ui-monospace, SFMono-Regular, monospace;pointer-events:none;user-select:none;opacity:0.85;white-space:nowrap;line-height:1;">${zoneId}</div>`,
  iconSize: [32, 16],
  iconAnchor: [16, 8]
});

// 🗺️ GeometryDecoder decodes Municipal 511 encoded coordinates sequentially
class GeometryDecoder {
  constructor(encoded) {
    this.points = [];
    this.index = 0;
    if (!encoded) return;
    let u = 0;
    const c = encoded.length;
    let f = 0;
    let e = 0;
    while (u < c) {
      let r = 0;
      let t = 0;
      let i;
      do {
        i = encoded.charCodeAt(u++) - 63;
        t |= (i & 31) << r;
        r += 5;
      } while (i >= 32);
      const o = (t & 1) !== 0 ? ~(t >> 1) : t >> 1;
      f += o;

      r = 0;
      t = 0;
      do {
        i = encoded.charCodeAt(u++) - 63;
        t |= (i & 31) << r;
        r += 5;
      } while (i >= 32);
      const s = (t & 1) !== 0 ? ~(t >> 1) : t >> 1;
      e += s;

      this.points.push([f / 1e5, e / 1e5]);
    }
  }

  getNPoints(n) {
    const pts = this.points.slice(this.index, this.index + n);
    this.index += n;
    return pts;
  }
}

// helper for road closure type names from Municipal 511
const getClosureTypeName = (bit) => {
  switch (bit) {
    case 1: return "Detour";
    case 8: return "Sidewalk Closed";
    case 16: return "Bike Lane Closed";
    case 32:
    case 256:
    case 512: return "Lane(s) Closed";
    case 2048: return "Alternating Traffic";
    case 8192: return "One Direction Closed";
    case 16384: return "Road Closed - Local Traffic Only";
    case 32768:
    case 65536: return "Road Closed - Emergency Access Only";
    case 131072: return "Intermittent Blockage";
    case 262144: return "Road Closed - No Emergency Access";
    default: return "";
  }
};

// 🚧 Barricade Icon for Road Closures
const closureIcon = L.divIcon({
  className: 'custom-closure-icon',
  html: `<div style="
    background-color: #f59e0b;
    border: 2px solid #000000;
    border-radius: 6px;
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 5px rgba(0,0,0,0.4);
    font-size: 15px;
    box-sizing: border-box;
  ">🚧</div>`,
  iconSize: [28, 28],
  iconAnchor: [14, 14],
  popupAnchor: [0, -14]
});


// 🚧 Sub-component to manage openPopup on selection
function RoadClosureMarker({ closure, isSelected, onSelect }) {
  const markerRef = useRef(null);

  useEffect(() => {
    if (isSelected && markerRef.current) {
      const timer = setTimeout(() => {
        if (markerRef.current) {
          markerRef.current.openPopup();
        }
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [isSelected]);

  let color = "#ef4444"; // NO_ACCESS
  if (closure.emergencyAccess === "ACCESS_ONLY") color = "#f59e0b"; // ACCESS_ONLY
  if (closure.emergencyAccess === "CAUTION") color = "#eab308"; // CAUTION

  const markerPos = Array.isArray(closure.coordinates) && closure.coordinates.length >= 2 
    ? [parseFloat(closure.coordinates[0]), parseFloat(closure.coordinates[1])] 
    : COQUITLAM_CENTER;

  const polylinePos = Array.isArray(closure.polyline) && closure.polyline.length > 0
    ? closure.polyline.map(pt => [parseFloat(pt[0]), parseFloat(pt[1])])
    : [];

  return (
    <React.Fragment>
      {polylinePos.length > 0 && (
        <Polyline 
          positions={polylinePos} 
          pathOptions={{ 
            color: color, 
            weight: 6, 
            dashArray: "10, 10", 
            opacity: 0.85 
          }} 
        />
      )}
      <Marker 
        ref={markerRef}
        position={markerPos} 
        icon={closureIcon}
        eventHandlers={{
          click: () => {
            onSelect(closure);
          }
        }}
      >
        <Popup className="road-closure-popup" onClose={() => {
          if (isSelected) onSelect(null);
        }}>
          <div className="bg-slate-950 text-white p-2.5 border border-slate-800 rounded-md" style={{ minWidth: '220px', maxWidth: '260px' }}>
            <div className="flex justify-between items-center gap-2">
              <span className={`px-1.5 py-0.5 rounded text-[8px] font-black tracking-wider ${
                closure.emergencyAccess === 'NO_ACCESS' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                closure.emergencyAccess === 'ACCESS_ONLY' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
                'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
              }`}>
                {closure.emergencyAccess === 'NO_ACCESS' ? 'FULL CLOSURE' :
                 closure.emergencyAccess === 'ACCESS_ONLY' ? 'EMERGENCY ACCESS ONLY' :
                 'LANE CLOSURE'}
              </span>
              <span className="text-[9px] text-slate-550 font-mono font-medium">{closure.source}</span>
            </div>
            <h3 className="font-bold text-sm text-slate-200 mt-2 leading-tight">{closure.headline}</h3>
            <p className="text-[9px] text-slate-400 font-mono mt-0.5 font-semibold">{closure.street}</p>
            {(closure.affectedZones?.length > 0 || closure.zoneId) && (
              <div className="mt-1.5 pt-1 border-t border-slate-900 flex justify-between items-center text-[9px] font-mono">
                <span className="text-slate-400 font-medium">📍 Impacted Zones</span>
                <span className="bg-sky-950 text-sky-300 border border-sky-800/80 px-1.5 py-0.5 rounded font-black">
                  {closure.affectedZones?.length > 0 
                    ? `Zone ${closure.affectedZones.join(", ")}` 
                    : `Zone ${closure.zoneId}`}
                </span>
              </div>
            )}

            {closure.startDate && (
              <p className="text-[9px] text-sky-400/90 font-mono mt-1 flex items-center gap-1 font-bold">
                📅 {closure.endDate ? (
                  `${new Date(closure.startDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })} - ${new Date(closure.endDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`
                ) : (
                  `Started ${new Date(closure.startDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })} (Until Further Notice)`
                )}
              </p>
            )}
            <p className="text-xs text-slate-350 mt-2 font-sans leading-relaxed border-t border-slate-900 pt-1.5 whitespace-pre-line overflow-y-auto pr-1 scrollbar-thin scrollbar-thumb-slate-800 scrollbar-track-transparent" style={{ whiteSpace: 'pre-line', maxHeight: '200px' }}>{closure.description}</p>
          </div>
        </Popup>

      </Marker>
    </React.Fragment>
  );
}


// 🎯 Custom Target Address Icon
const targetIcon = L.divIcon({
  className: 'custom-target-icon',
  html: `<div style="
    background-color: #4f46e5;
    border: 2px solid #ffffff;
    border-radius: 50%;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 6px rgba(0,0,0,0.4);
    font-size: 13px;
    box-sizing: border-box;
    color: white;
  ">🎯</div>`,
  iconSize: [24, 24],
  iconAnchor: [12, 12],
  popupAnchor: [0, -12]
});

// 🏠 Find the Alpha side segment of a parcel boundary (clockwise ordering)
// rings: targetAddress.rings[0], referencePt: [lng, lat] (from route end or fallback)
function getAlphaSegment(rings, referencePt) {
  if (!rings || rings.length < 2) return null;
  
  const refPt = turf.point(referencePt);
  let minDistance = Infinity;
  let alphaSeg = null;
  
  for (let i = 0; i < rings.length - 1; i++) {
    const p1 = rings[i];
    const p2 = rings[i+1];
    const segment = turf.lineString([p1, p2]);
    const dist = turf.pointToLineDistance(refPt, segment, { units: 'meters' });
    if (dist < minDistance) {
      minDistance = dist;
      alphaSeg = segment;
    }
  }
  return alphaSeg;
}

export default function MapBoard({ onSimulateCall, onLaunchKiosk, initialMode = "EXPLORE" }) {
  const [map, setMap] = useState(null);

  // Safe dynamic compile-time stamp
  const buildTime = typeof __BUILD_DATE__ !== 'undefined' ? __BUILD_DATE__ : new Date().toISOString();

  // RAW DATA STATES
  const [zones, setZones] = useState([]);
  const [roadClosures, setRoadClosures] = useState([]);
  const [selectedClosure, setSelectedClosure] = useState(null);
  
  // APP/TERMINAL STATE
  const [appMode, setAppMode] = useState(initialMode);

  useEffect(() => {
    if (initialMode) {
      setAppMode(initialMode);
    }
  }, [initialMode]);
  const [activeDispatch, setActiveDispatch] = useState(null);
  const [mapStyle, setMapStyle] = useState("GREY"); 
  const [showLabels, setShowLabels] = useState(true); 
  const [showHydrants, setShowHydrants] = useState(true); 
  const [showZones, setShowZones] = useState(true); 
  const [showRoadClosures, setShowRoadClosures] = useState(true); 
  const [showActiveNow, setShowActiveNow] = useState(true);
  const [showNext24h, setShowNext24h] = useState(false);
  const [showNext7d, setShowNext7d] = useState(false);
  const [showRailroadCrossings, setShowRailroadCrossings] = useState(false);
  const [showSchools, setShowSchools] = useState(false);
  const [showFireHalls, setShowFireHalls] = useState(true);
  const [currentZoom, setCurrentZoom] = useState(12);
  const [cadastralError, setCadastralError] = useState(false); 
  
  // COLLAPSIBLE SIDEBAR STATES
  const [leftSidebarOpen, setLeftSidebarOpen] = useState(true);
  const [rightSidebarOpen, setRightSidebarOpen] = useState(false);

  // NAVIGATION & ROUTING STATES
  const [homeHall, setHomeHall] = useState(() => {
    return import.meta.env.VITE_DEFAULT_HALL || "1";
  });
  const [targetAddress, setTargetAddress] = useState(null);
  const [targetPolygon, setTargetPolygon] = useState(null);
  const [allNearbyHydrants, setAllNearbyHydrants] = useState([]);
  const [routeCoordinates, setRouteCoordinates] = useState([]);
  const targetMarkerRef = useRef(null);
  const [allHydrantsData, setAllHydrantsData] = useState([]);

  // EVO Routing Engine Configuration State
  const [routingConfig, setRoutingConfig] = useState(DEFAULT_ROUTING_CONFIG);
  const [showRoutingConfigModal, setShowRoutingConfigModal] = useState(false);

  // Compute Response Route Metrics via CFR-EVORoutingEngine
  const routeMetrics = useMemo(() => {
    if (!targetAddress || !STATIONS[homeHall]) return null;
    const origin = STATIONS[homeHall];
    const target = [targetAddress.lat, targetAddress.lng];
    
    const dispatchedUnits = activeDispatch?.units 
      ? activeDispatch.units.split(',').map(u => u.trim()) 
      : ['SQ1', 'E1', 'L1'];

    return calculateEVORouteMetrics({
      originCoords: origin,
      targetCoords: target,
      dispatchedUnits,
      routeCoordinates,
      config: routingConfig,
      timeOfDay: new Date()
    });
  }, [targetAddress, homeHall, routeCoordinates, activeDispatch, routingConfig]);

  const [userPanned, setUserPanned] = useState(false);
  const [isOffDefault, setIsOffDefault] = useState(false);

  // Track zoom level & map movement off default center/zoom
  useEffect(() => {
    if (!map) return;
    const updateMapState = () => {
      const zoom = map.getZoom();
      setCurrentZoom(zoom);
      const center = map.getCenter();
      const latDiff = Math.abs(center.lat - COQUITLAM_CENTER[0]);
      const lngDiff = Math.abs(center.lng - COQUITLAM_CENTER[1]);
      const zoomDiff = Math.abs(zoom - 12);
      
      // Off default if panned > ~300m or zoomed away from 12
      const offDefault = latDiff > 0.003 || lngDiff > 0.003 || zoomDiff > 0.15;
      setIsOffDefault(offDefault);
    };

    const onUserGesture = (e) => {
      if (e && e.originalEvent) {
        setUserPanned(true);
      }
    };

    map.on('zoomend moveend', updateMapState);
    map.on('dragstart zoomstart touchstart', onUserGesture);
    updateMapState();
    return () => {
      map.off('zoomend moveend', updateMapState);
      map.off('dragstart zoomstart touchstart', onUserGesture);
    };
  }, [map]);

  // Load all hydrants data and fire zones once on mount
  useEffect(() => {
    const baseUrl = import.meta.env.BASE_URL;
    fetch(`${baseUrl}data/hydrants.json`)
      .then(r => r.ok ? r.json() : [])
      .then(data => {
        setAllHydrantsData(data);
      })
      .catch(err => {
        console.error("Failed to load local cached hydrants database:", err);
      });

    // Fetch zones on startup for offline map overlay
    fetch(`${baseUrl}data/zones.json?v=2`)
      .then(r => r.ok ? r.json() : [])
      .then(data => {
        setZones(data);
      })
      .catch(err => {
        console.error("Failed to load zones at startup:", err);
      });
  }, []);

  const updateTargetAddress = useCallback((addr) => {
    if (addr && addr.address) {
      const enriched = enrichAddressWithBuilding(addr);
      const clean = sanitizeAddress(enriched.address);
      setTargetAddress({ ...enriched, address: clean });
    } else {
      setTargetAddress(enrichAddressWithBuilding(addr));
    }
    setUserPanned(false); // Reset user pan state when a new target address is selected
    if (addr && addr.rings) {
      const leafletPolygon = addr.rings.map(ring => 
        ring.map(coord => [coord[1], coord[0]])
      );
      setTargetPolygon(leafletPolygon);
    } else {
      setTargetPolygon(null);
    }
    setAllNearbyHydrants([]);
    setRouteCoordinates([]);
  }, []);

  // Auto-open target address popup when targetAddress changes
  useEffect(() => {
    if (targetAddress && targetMarkerRef.current) {
      const timer = setTimeout(() => {
        if (targetMarkerRef.current) {
          targetMarkerRef.current.openPopup();
        }
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [targetAddress]);

  useEffect(() => {
    localStorage.setItem('home_hall', homeHall);
  }, [homeHall]);

  // Subscribe to live dispatches via MQTT WebSockets
  useDispatchListener({
    enabled: true,
    onInsert: (dispatch) => {
      const newCall = dispatch.rawRecord || dispatch;
      if (newCall) {
        setActiveDispatch(newCall);
        const target = newCall.target || (newCall.address ? { address: newCall.address, lat: newCall.lat || COQUITLAM_CENTER[0], lng: newCall.lng || COQUITLAM_CENTER[1] } : null);
        if (target) {
          updateTargetAddress(target);
          if (map && target.lat && target.lng) {
            map.flyTo([target.lat, target.lng], 17, { animate: true });
          }
        }
        setLeftSidebarOpen(true);
        setRightSidebarOpen(false);
      }
    },
    onUpdate: (dispatch) => {
      const updatedCall = dispatch.rawRecord || dispatch;
      setActiveDispatch(curr => {
        if (curr && (curr.id === updatedCall.id || curr.dispatch_id === updatedCall.dispatch_id)) {
          const oldTarget = curr.target;
          const newTarget = updatedCall.target;
          if (newTarget && (!oldTarget || oldTarget.lat !== newTarget.lat || oldTarget.lng !== newTarget.lng)) {
            updateTargetAddress(newTarget);
            if (map && newTarget.lat && newTarget.lng) {
              map.flyTo([newTarget.lat, newTarget.lng], 17, { animate: true });
            }
          }
          return updatedCall;
        }
        return curr;
      });
    },
    onDelete: (dispatch) => {
      const deletedCall = dispatch.rawRecord || dispatch;
      setActiveDispatch(curr => {
        if (curr && (curr.id === deletedCall.id || curr.dispatch_id === deletedCall.dispatch_id)) {
          updateTargetAddress(null);
          return null;
        }
        return curr;
      });
    }
  });

  // Query Nearby Hydrants on targetAddress change (using local in-memory dataset)
  useEffect(() => {
    if (!targetAddress || allHydrantsData.length === 0) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setAllNearbyHydrants(prev => prev.length > 0 ? [] : prev);
      return;
    }

    const lat = targetAddress.lat;
    const lng = targetAddress.lng;
    const centerPoint = turf.point([lng, lat]);

    try {
      // Filter hydrants within 300m (0.3 km)
      const nearby = allHydrantsData
        .map(h => {
          const hydPoint = turf.point([h.lng, h.lat]);
          const distKm = turf.distance(centerPoint, hydPoint, { units: 'kilometers' });
          const distM = Math.round(distKm * 1000);
          return { ...h, distM };
        })
        .filter(h => h.distM <= 300)
        .map(h => ({
          gisId: h.gisId,
          lat: h.lat,
          lng: h.lng,
          flowClass: h.flowClass,
          status: h.status
        }));

      setAllNearbyHydrants(nearby);
    } catch (e) {
      console.warn("Failed to filter nearby hydrants locally:", e);
      setAllNearbyHydrants(prev => prev.length > 0 ? [] : prev);
    }
  }, [targetAddress, allHydrantsData]);

  // Filter and sort nearby hydrants dynamically with Alpha-segment logic
  const nearestHydrants = useMemo(() => {
    if (allNearbyHydrants.length === 0 || !targetAddress) return [];

    const targetLat = targetAddress.front_lat || targetAddress.lat;
    const targetLng = targetAddress.front_lng || targetAddress.lng;
    const fromPoint = turf.point([targetLng, targetLat]);

    // Try to construct parcel boundary components
    let parcelLine = null;
    let ringCoords = null;
    if (targetAddress.rings && targetAddress.rings.length > 0) {
      try {
        ringCoords = targetAddress.rings[0];
        if (ringCoords.length >= 2) {
          parcelLine = turf.lineString(ringCoords);
        }
      } catch (e) {
        console.warn("Could not construct parcel boundary line for hydrant calculations:", e);
      }
    }

    // Determine target frontage reference point if route is loaded
    let commonFrontagePt = null;
    if (routeCoordinates && routeCoordinates.length > 0) {
      const lastRouteCoord = routeCoordinates[routeCoordinates.length - 1];
      commonFrontagePt = [lastRouteCoord.lng, lastRouteCoord.lat];
    }

    // Process each hydrant to compute distances to Alpha line
    const hydrantsWithDistances = allNearbyHydrants.map(hyd => {
      const toPoint = turf.point([hyd.lng, hyd.lat]);
      let distance;

      if (ringCoords && ringCoords.length >= 2) {
        // Find Alpha segment closest to either the common frontage (route end) or this hydrant itself
        const refPt = commonFrontagePt || [hyd.lng, hyd.lat];
        const alphaSeg = getAlphaSegment(ringCoords, refPt);
        
        if (alphaSeg) {
          distance = Math.round(turf.pointToLineDistance(toPoint, alphaSeg, { units: 'meters' }));
        } else if (parcelLine) {
          distance = Math.round(turf.pointToLineDistance(toPoint, parcelLine, { units: 'meters' }));
        } else {
          distance = Math.round(turf.distance(fromPoint, toPoint, { units: 'kilometers' }) * 1000);
        }
      } else {
        distance = Math.round(turf.distance(fromPoint, toPoint, { units: 'kilometers' }) * 1000);
      }

      return {
        ...hyd,
        distance
      };
    });

    // Sort by Alpha distance
    hydrantsWithDistances.sort((a, b) => a.distance - b.distance);

    // Filter by route line if available
    if (routeCoordinates && routeCoordinates.length > 1) {
      try {
        const routeLine = turf.lineString(routeCoordinates.map(c => [c.lng, c.lat]));
        const onRouteHydrants = hydrantsWithDistances.map(hyd => {
          const pt = turf.point([hyd.lng, hyd.lat]);
          const distanceToRoute = turf.pointToLineDistance(pt, routeLine, { units: 'meters' });
          return { ...hyd, distanceToRoute };
        }).filter(hyd => hyd.distanceToRoute <= 25); // 25m threshold along route

        if (onRouteHydrants.length > 0) {
          onRouteHydrants.sort((a, b) => a.distance - b.distance);
          return onRouteHydrants.slice(0, 3); // Return up to 3 hydrants on route
        }
      } catch (e) {
        console.error("Error filtering hydrants by route line:", e);
      }
    }

    return hydrantsWithDistances.slice(0, 3); // Return up to 3 closest hydrants
  }, [allNearbyHydrants, targetAddress, routeCoordinates]);

  const targetCoords = useMemo(() => {
    if (!targetAddress) return null;
    const lat = targetAddress.front_lat || targetAddress.lat;
    const lng = targetAddress.front_lng || targetAddress.lng;
    return [lat, lng];
  }, [targetAddress]);

  // Adaptive Zooming: fit bounds to show both origin hall & destination address inside middle window (between Left 320px & Right 380px sidebars)
  useEffect(() => {
    if (map && targetAddress && STATIONS[homeHall] && appMode === "EXPLORE" && !userPanned && targetCoords) {
      const origin = STATIONS[homeHall];
      map.fitBounds([origin, targetCoords], { 
        paddingTopLeft: [340, 80], 
        paddingBottomRight: [400, 80], 
        animate: true 
      });
    }
  }, [map, targetAddress, homeHall, appMode, userPanned, targetCoords]);

  // ROAD ACCESS FILTER STATES
  const [filterNoAccess, setFilterNoAccess] = useState(true);
  const [filterAccessOnly, setFilterAccessOnly] = useState(true);
  const [filterCaution, setFilterCaution] = useState(true);

  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [score, setScore] = useState(0);
  const [feedback, setFeedback] = useState(null);
  
  const [userGuess, setUserGuess] = useState(null);
  const [distanceOff, setDistanceOff] = useState(0); 
  const [clickedBlockData, setClickedBlockData] = useState(null);

  // ⏱️ TIMER REF (Prevents double-skipping if you hit Enter while waiting)
  const autoAdvanceTimer = useRef(null);

  // Auto-resize Leaflet map container to prevent gray areas when sidebars open/close
  useEffect(() => {
    if (map) {
      const timer = setTimeout(() => {
        map.invalidateSize();
      }, 350); // wait for transitions to settle
      return () => clearTimeout(timer);
    }
  }, [map, leftSidebarOpen, rightSidebarOpen]);

  // LOAD ROAD CLOSURES (Strictly local containerized FastAPI /api/road-closures)
  useEffect(() => {
    const loadClosures = () => {
      apiClient.roadClosures.fetchAll()
        .then(rawEvents => {
          if (!Array.isArray(rawEvents)) return;
          const now = new Date();
          const processed = rawEvents.map(evt => {
            const start = evt.startDate ? new Date(evt.startDate) : null;
            const end = evt.endDate ? new Date(evt.endDate) : null;

            let isActive = false, isFuture = false, isExpired = false;
            if (start && now < start) {
              isFuture = true;
            } else if (end && now > end) {
              isExpired = true;
            } else {
              isActive = true;
            }
            return {
              ...evt,
              isActive,
              isFuture,
              isExpired
            };
          });
          setRoadClosures(processed);
        })
        .catch(err => {
          console.warn("Failed to load local road closures:", err);
        });
    };

    loadClosures();
    const interval = setInterval(loadClosures, 300000); // 5 min interval
    return () => clearInterval(interval);
  }, []);

  const startMode = useCallback((mode) => {
      if (mode === "KIOSK_VIEW") {
        if (typeof onLaunchKiosk === 'function') {
          onLaunchKiosk();
        }
        return;
      }
      setAppMode(mode);
      setActiveDispatch(null);
      setTargetAddress(null);
      setMapStyle(MODE_DEFAULTS[mode] || "GREY"); 
      setShowLabels(mode === "EXPLORE");
      
      if (mode === "EXPLORE") {
          setShowZones(true);
          setShowHydrants(true);
          setShowRoadClosures(true);
          setLeftSidebarOpen(true);
          setRightSidebarOpen(false);
      } else {
          setLeftSidebarOpen(true);
          setRightSidebarOpen(false);
      }
  }, [onLaunchKiosk]);

  const getZoneStyle = (zone) => {
    // Color-code by fire hall for explore/live modes
    const stationName = zone.station || "";
    let color = "#475569"; // default slate gray
    
    if (stationName.includes("Hall 1") || zone.unit_id === "E1") color = "#f43f5e";      // Soft Crimson Red for Hall 1
    else if (stationName.includes("Hall 2") || zone.unit_id === "E2") color = "#3b82f6"; // Soft Royal Blue for Hall 2
    else if (stationName.includes("Hall 3") || zone.unit_id === "E3" || zone.unit_id === "Q5") color = "#10b981"; // Soft Emerald Green for Hall 3
    else if (stationName.includes("Hall 4") || zone.unit_id === "E4") color = "#a855f7"; // Soft Purple for Hall 4
    
    return {
      color: color,
      fillColor: color,
      fillOpacity: 0.10,
      weight: 1.8,
      dashArray: "4 4"
    };
  };
 
  // Filter closures for map and alerts rendering based on access severity & timeframe window
  const activeClosures = roadClosures.filter(closure => {
    // 1. Access Severity Filter
    if (closure.emergencyAccess === "NO_ACCESS" && !filterNoAccess) return false;
    if (closure.emergencyAccess === "ACCESS_ONLY" && !filterAccessOnly) return false;
    if (closure.emergencyAccess === "CAUTION" && !filterCaution) return false;

    // 2. Timeframe Window Filter
    const now = new Date();
    const isCurrentlyActive = closure.isActive;
    const is24hFuture = closure.isFuture && closure.start && ((closure.start.getTime() - now.getTime()) <= 24 * 3600 * 1000);
    const is7dFuture = closure.isFuture && closure.start && ((closure.start.getTime() - now.getTime()) <= 7 * 86400 * 1000);

    const matchesTimeframe = 
      (showActiveNow && isCurrentlyActive) ||
      (showNext24h && is24hFuture) ||
      (showNext7d && is7dFuture);

    return matchesTimeframe;
  });
 
  return (
    <div className="h-screen w-screen flex flex-col bg-slate-950 overflow-hidden text-slate-100 font-sans">
      
      <Header 
        appMode={appMode} 
        setAppMode={startMode} 
        mapStyle={mapStyle} 
        setMapStyle={setMapStyle} 
        showLabels={showLabels} 
        setShowLabels={setShowLabels} 
        leftSidebarOpen={leftSidebarOpen}
        setLeftSidebarOpen={setLeftSidebarOpen}
        rightSidebarOpen={rightSidebarOpen}
        setRightSidebarOpen={setRightSidebarOpen}
        showRoadClosures={showRoadClosures}
        setShowRoadClosures={setShowRoadClosures}
        onOpenRoutingConfig={() => setShowRoutingConfigModal(true)}
        alertsCount={showRoadClosures ? activeClosures.length : 0}
        gisOffline={cadastralError}
        homeHall={homeHall}
      />

      <div className="flex flex-row flex-grow w-full h-[calc(100vh-4rem)] relative overflow-hidden z-10">
        {/* Left Control Panel & Option Toggles */}
        <LeftSidebar 
          leftSidebarOpen={leftSidebarOpen}
          setLeftSidebarOpen={setLeftSidebarOpen}
          appMode={appMode}
          activeDispatch={activeDispatch}
          setActiveDispatch={setActiveDispatch}
          loadingTraining={loadingTraining}
          mapStyle={mapStyle}
          setMapStyle={setMapStyle}
          onOpenRoutingConfig={() => setShowRoutingConfigModal(true)}
          showZones={showZones}
          setShowZones={setShowZones}
          showHydrants={showHydrants}
          setShowHydrants={setShowHydrants}
          showRoadClosures={showRoadClosures}
          setShowRoadClosures={setShowRoadClosures}
          showLabels={showLabels}
          setShowLabels={setShowLabels}
          showRailroadCrossings={showRailroadCrossings}
          setShowRailroadCrossings={setShowRailroadCrossings}
          showSchools={showSchools}
          setShowSchools={setShowSchools}
          showFireHalls={showFireHalls}
          setShowFireHalls={setShowFireHalls}
          addresses={addresses}
          homeHall={homeHall}
          setHomeHall={setHomeHall}
          targetAddress={targetAddress}
          setTargetAddress={updateTargetAddress}
          nearestHydrant={nearestHydrants[0] || null}
          nearestHydrants={nearestHydrants}
          routeMetrics={routeMetrics}
          filterNoAccess={filterNoAccess}
          setFilterNoAccess={setFilterNoAccess}
          filterAccessOnly={filterAccessOnly}
          setFilterAccessOnly={setFilterAccessOnly}
          filterCaution={filterCaution}
          setFilterCaution={setFilterCaution}
          showActiveNow={showActiveNow}
          setShowActiveNow={setShowActiveNow}
          showNext24h={showNext24h}
          setShowNext24h={setShowNext24h}
          showNext7d={showNext7d}
          setShowNext7d={setShowNext7d}
          map={map}
        />

        {/* Map Container Wrapper */}
        <div className="flex-grow h-full relative flex flex-col bg-slate-900 min-w-0">
          <MapContainer 
              center={COQUITLAM_CENTER} 
              zoom={12} 
              minZoom={12}
              maxZoom={22}
              maxBounds={OPERATIONAL_BOUNDS}
              maxBoundsViscosity={1.0}
              style={{ height: "100%", width: "100%" }} 
              className="bg-slate-900" zoomControl={false} ref={setMap}
          >
            <BaseMap 
              style={(appMode === "EXPLORE" && mapStyle === "SATELLITE") ? "SATELLITE" : (showLabels && currentZoom >= 16) ? "GREY" : (showLabels || targetAddress || currentZoom <= 15) ? "VOYAGER" : "GREY"} 
              useLabelsFallback={false} 
            />
            
            <CoquitlamOverlays 
                visible={showLabels && !cadastralError} 
                onLoadError={() => setCadastralError(true)} 
            />
            
            {/* Hydrants Visual GIS Overlay */}
            <HydrantsLayer visible={showHydrants} />
            
            {/* Schools GIS Overlay */}
            <SchoolsLayer visible={showSchools} />
            
            {/* 2. DEFINE CUSTOM PANES */}
            <Pane name="underlayPane" style={{ zIndex: 390 }} />
            <Pane name="labelsPane" style={{ zIndex: 410 }} />
            
            {/* 3. LAYERS ASSIGNED TO PANES */}
            
            {/* Soft Multi-Color Vector Response Zones Layer (Color-coded by Fire Hall - OFF at zoom >= 16) */}
            {(showZones) && currentZoom < 16 && zones.map((zone) => (
              <Polygon 
                  key={zone.zone_id} 
                  positions={zone.geometry.coordinates[0].map(c => [c[1], c[0]])} 
                  pathOptions={getZoneStyle(zone)} 
                  pane="underlayPane" 
              />
            ))}

            {/* Centered Soft Black Zone Number Labels (ON at zoom 13/14/15 when showZones is ON, OFF at zoom >= 16) */}
            {(showZones) && currentZoom >= 13 && currentZoom < 16 && zones.map((zone) => {
              const center = getZoneCentroid(zone);
              if (!center) return null;
              return (
                <Marker 
                  key={`zone-num-${zone.zone_id}`}
                  position={center}
                  icon={createSoftZoneNumberIcon(zone.zone_id)}
                  interactive={false}
                  pane="labelsPane"
                />
              );
            })}

            {/* HIDE STATIONS IN TRAINING MODE */}
            {<StationsLayer visible={showFireHalls} />}

            {/* AT-GRADE RAILROAD CROSSINGS LAYER */}
            <RailroadCrossingsLayer visible={showRailroadCrossings} />
            
            {/* ROAD CLOSURES LAYER */}
            {showRoadClosures && activeClosures.map((closure, i) => (
              <RoadClosureMarker 
                key={closure.id || i}
                closure={closure}
                isSelected={selectedClosure !== null && selectedClosure.id === closure.id}
                onSelect={setSelectedClosure}
              />
            ))}

            {/* Active Target Address Marker & Suggested Route Overlay */}
            {appMode === "EXPLORE" && targetAddress && (
              <>
                {targetPolygon && (
                  <Polygon 
                    positions={targetPolygon} 
                    pathOptions={{ 
                      color: targetAddress.buildingName ? '#f59e0b' : '#0284c7', 
                      fillColor: targetAddress.buildingName ? '#f59e0b' : '#38bdf8', 
                      fillOpacity: targetAddress.buildingName ? 0.08 : 0.15, 
                      weight: 2,
                      dashArray: '4,4'
                    }}
                  />
                )}
                {targetAddress.buildingName && (
                  <CircleMarker
                    center={[targetAddress.lat, targetAddress.lng]}
                    radius={20}
                    pathOptions={{
                      color: '#f59e0b',
                      fillColor: '#38bdf8',
                      fillOpacity: 0.25,
                      weight: 2.5,
                      className: 'animate-pulse'
                    }}
                  />
                )}
                <Marker 
                  ref={targetMarkerRef}
                  position={[targetAddress.lat, targetAddress.lng]} 
                  icon={targetIcon}
                />

                {/* Highlight Top 3 closest hydrants (No tracer line) */}
                {nearestHydrants.map((hyd, idx) => {
                  const isPrimary = idx === 0;
                  return (
                    <CircleMarker 
                      key={`${hyd.gisId}-${idx}`}
                      center={[hyd.lat, hyd.lng]} 
                      radius={isPrimary ? 16 : 12} 
                      pathOptions={{ 
                        color: isPrimary ? '#06b6d4' : '#c084fc', // Cyan for closest, Lavender for others
                        fillColor: isPrimary ? '#22d3ee' : '#e9d5ff', 
                        fillOpacity: isPrimary ? 0.15 : 0.1, 
                        weight: isPrimary ? 2 : 1.5,
                        className: isPrimary ? 'animate-pulse' : '' 
                      }} 
                    >
                      <Tooltip direction="top" className="font-bold text-xs bg-slate-950 text-white border border-slate-800 p-2 shadow-xl">
                        <div className="flex flex-col gap-0.5" style={{ minWidth: '120px' }}>
                          <span className={`text-[9px] uppercase font-mono tracking-wider ${isPrimary ? 'text-cyan-400' : 'text-purple-400'}`}>
                            {isPrimary ? 'NEAREST HYDRANT' : `HYDRANT OPTION #${idx + 1}`}
                          </span>
                          <span className="text-white text-sm font-bold">{hyd.gisId}</span>
                          <span className="text-slate-400 text-[10px] mt-1 font-mono">Distance: {hyd.distance}m</span>
                          {hyd.flowClass && (
                            <span className="text-sky-400 text-xs font-semibold">Flow Class: {hyd.flowClass}</span>
                          )}
                        </div>
                      </Tooltip>
                    </CircleMarker>
                  );
                })}

                {STATIONS[homeHall] && (
                  <RoutingOverlay 
                    from={STATIONS[homeHall]} 
                    to={targetCoords} 
                    onRouteCalculated={setRouteCoordinates}
                  />
                )}
              </>
            )}
          </MapContainer>

          {/* Top-Right Floating Controls: Zoom Level & Quick Reset View Button */}
          <div className="absolute top-3 right-3 z-[1000] flex flex-col items-end gap-2">
            <div className="pointer-events-none select-none px-2.5 py-1 rounded-lg bg-slate-950/90 border border-slate-800/80 text-[10px] font-mono text-slate-400 backdrop-blur-md shadow-lg flex items-center gap-2">
              <span className="text-[9px] text-slate-500 font-bold uppercase tracking-wider">ZOOM</span>
              <span className="font-extrabold text-amber-400 font-mono text-xs">
                {typeof currentZoom === 'number' ? currentZoom.toFixed(1) : currentZoom}
              </span>
            </div>

            {isOffDefault && (
              <button
                onClick={() => {
                  setUserPanned(false);
                  if (map) {
                    map.flyTo(COQUITLAM_CENTER, 12, { animate: true, duration: 0.8 });
                  }
                }}
                title="Reset view to Coquitlam City Center (Zoom 12)"
                className="px-3 py-1.5 rounded-lg bg-slate-950/90 hover:bg-slate-900 border border-slate-800 hover:border-cyan-500/60 text-slate-200 hover:text-cyan-300 text-xs font-semibold shadow-xl backdrop-blur-md transition-all duration-200 flex items-center gap-1.5 cursor-pointer active:scale-95 group animate-in fade-in slide-in-from-top-1 duration-200"
              >
                <svg className="w-3.5 h-3.5 text-cyan-400 group-hover:rotate-180 transition-transform duration-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                <span>Reset View</span>
              </button>
            )}
          </div>

          {/* Floating Re-Center Button when user pans or zooms */}
          {userPanned && targetAddress && (
            <button
              onClick={() => {
                setUserPanned(false);
                if (map && targetCoords && STATIONS[homeHall]) {
                  map.fitBounds([STATIONS[homeHall], targetCoords], {
                    paddingTopLeft: [340, 80],
                    paddingBottomRight: [400, 80],
                    animate: true
                  });
                }
              }}
              className="absolute bottom-6 left-1/2 -translate-x-1/2 z-[1100] bg-slate-900/95 hover:bg-slate-800 text-sky-400 font-extrabold text-xs px-4.5 py-2.5 rounded-full border border-sky-500/60 shadow-2xl flex items-center gap-2 transition-all cursor-pointer animate-in fade-in slide-in-from-bottom-3 duration-200"
            >
              <span className="animate-pulse">🎯</span>
              <span>RE-CENTER ON ROUTE</span>
            </button>
          )}

          {/* APPLICATION VERSION & COMPILE TIMESTAMP WATERMARK */}
          <div className="absolute bottom-3 left-3 z-[1000] pointer-events-none font-mono text-[9px] text-slate-400/85 drop-shadow-sm select-none">
            CFR EVO APP | BUILD: {buildTime} | LICENSE: POLYFORM NONCOMMERCIAL 1.0.0
          </div>
        </div>

        {/* Right 1/3 Spatial Inspection Stack Panel (Target Address, 3D Satellite, Street View) */}
        {appMode === "EXPLORE" && targetAddress && (
          <aside className="w-[380px] h-full bg-slate-950 border-l border-slate-800 p-3 flex flex-col gap-3 z-[1000] flex-shrink-0 shadow-2xl animate-in slide-in-from-right duration-300">
            {/* Top 1/3 Address Information Card */}
            <div className="flex-1 min-h-0 bg-slate-900/90 border border-slate-800 rounded-2xl p-4 flex flex-col justify-between shadow-xl backdrop-blur relative overflow-hidden">
              <div>
                <div className="flex justify-between items-center gap-2 pb-2.5 border-b border-slate-800">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] text-slate-400 font-mono font-bold uppercase tracking-wider">SEARCH TARGET</span>
                    <span className="text-emerald-400 text-[9px] font-black tracking-wider bg-emerald-950/80 border border-emerald-800/80 px-2 py-0.5 rounded">ACTIVE ROUTE</span>
                  </div>
                  <button 
                    onClick={() => setTargetAddress(null)}
                    className="text-slate-400 hover:text-white text-xs font-bold w-6 h-6 flex items-center justify-center rounded-full hover:bg-slate-800 transition cursor-pointer"
                    title="Close Inspection Panel"
                  >
                    ✕
                  </button>
                </div>

                {targetAddress.buildingName && (
                  <div className="flex items-center gap-1.5 mt-2.5 bg-amber-950/70 border border-amber-700/80 px-2.5 py-1 rounded-lg text-amber-300 font-extrabold text-xs">
                    <span>🏢</span>
                    <span>{targetAddress.buildingName}</span>
                  </div>
                )}
                <h3 className="font-black text-lg text-sky-400 mt-2 leading-tight uppercase font-sans tracking-tight">
                  {targetAddress.address}
                </h3>
                <p className="text-[11px] text-slate-400 font-mono mt-0.5 font-semibold">Coquitlam, BC</p>
                {targetAddress.note && (
                  <p className="text-[10px] text-sky-300 font-sans italic mt-1 font-semibold bg-slate-950/60 p-1.5 rounded border border-slate-800">
                    ℹ️ {targetAddress.note}
                  </p>
                )}
                
                {nearestHydrants.length > 0 && (
                  <div className="mt-3 pt-2.5 border-t border-slate-800/80 flex flex-col gap-1.5">
                    <span className="text-[9.5px] text-sky-400 font-extrabold uppercase tracking-wider font-mono flex items-center gap-1">
                      💧 Nearest Hydrant
                    </span>
                    <div className="flex justify-between text-xs bg-slate-950/80 px-3 py-1.5 rounded-lg border border-slate-800/80 font-mono">
                      <span className="text-slate-400">ID / Distance</span>
                      <span className="text-white font-black">{nearestHydrants[0].gisId} ({nearestHydrants[0].distance}m)</span>
                    </div>
                    {nearestHydrants[0].flowClass && (
                      <div className="flex justify-between text-xs bg-slate-950/80 px-3 py-1.5 rounded-lg border border-slate-800/80 font-mono">
                        <span className="text-slate-400">Flow Rating</span>
                        <span className="text-sky-400 font-black">{nearestHydrants[0].flowClass}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Middle 1/3 3D Property Satellite View */}
            <div className="flex-1 min-h-0 relative">
              <PropertySatellitePanel activeCall={targetAddress} />
            </div>

            {/* Bottom 1/3 Google Street View */}
            <div className="flex-1 min-h-0 relative">
              <StreetViewPanel activeCall={targetAddress} />
            </div>
          </aside>
        )}

        {/* Right Sidebar Alerts Panel */}
        {(!targetAddress || appMode !== "EXPLORE") && (
          <RightSidebar 
            rightSidebarOpen={rightSidebarOpen}
            setRightSidebarOpen={setRightSidebarOpen}
            appMode={appMode}
            roadClosures={roadClosures}
            showRoadClosures={showRoadClosures}
            filterNoAccess={filterNoAccess}
            filterAccessOnly={filterAccessOnly}
            filterCaution={filterCaution}
            showActiveNow={showActiveNow}
            showNext24h={showNext24h}
            showNext7d={showNext7d}
            map={map}
            onSelectClosure={setSelectedClosure}
            zones={zones}
            homeHall={homeHall}
          />
        )}
      </div>

      <React.Suspense fallback={<ModalLoadingFallback />}>
        {appMode === "ADMIN_DISPATCHES" && (
          <DispatchReview 
            onClose={() => startMode("EXPLORE")} 
            onSimulateCall={onSimulateCall}
          />
        )}

        {appMode === "DRIVER_SETUP" && (
          <DriverStationSetup 
            onClose={() => startMode("EXPLORE")} 
          />
        )}

        {/* EVO Routing Engine Tuning Configuration Modal */}
        {showRoutingConfigModal && (
          <EVORoutingConfigModal 
            isOpen={showRoutingConfigModal}
            onClose={() => setShowRoutingConfigModal(false)}
            config={routingConfig}
            setConfig={setRoutingConfig}
          />
        )}
      </React.Suspense>
    </div>
  );
}