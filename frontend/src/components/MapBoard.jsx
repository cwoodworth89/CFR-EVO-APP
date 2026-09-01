/* global __BUILD_DATE__ */
// NOTE: Map layout config is in docs/gis_endpoints.md, but its local-JSON sections are
// SUPERSEDED -- hydrants/zones now come from PostGIS via the API, not public/data/*.json.
import React, { useEffect, useState, useRef, useCallback, useMemo } from 'react'; // Added useRef, useCallback, useMemo
import 'leaflet/dist/leaflet.css';
import * as turf from '@turf/turf';
import L from 'leaflet';

// Import from your other components
import { RailroadCrossingsLayer } from './MapLayers';
import { MapClickEvents } from './MapActions';
import { Header } from './hud/Header';
import { LeftSidebar } from './hud/LeftSidebar';
import { RightSidebar } from './hud/RightSidebar';
import { MODE_DEFAULTS, UNIT_COLORS, STATIONS_MAP as STATIONS, KNOWN_BUILDINGS, OPERATIONAL_BOUNDS, COQUITLAM_CENTER } from './MapConstants';
import { getAlphaSegment, enrichAddressWithBuilding } from './map/mapGeometry';
import RoadClosureMarker from './map/RoadClosureMarker';
import ZonesLayer from './map/ZonesLayer';
import MapViewControls from './map/MapViewControls';
import TargetAddressCard from './hud/TargetAddressCard';
import DetailStack from './DetailStack';
import MapSurface from './map/MapSurface';
import RoadClosuresLayer from './map/RoadClosuresLayer';
import DispatchTargetLayer from './map/DispatchTargetLayer';
import { useMapLayerPreferences } from '../hooks/useMapLayerPreferences';
import { useRoadClosures } from '../hooks/useRoadClosures';

import { RoutingOverlay } from './RoutingOverlay';
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
import { useMapInstance } from '../hooks/useMapInstance';
import { toActiveCall, toMapTarget, isSameDispatch } from '../utils/dispatchModel';
import { API_BASE_URL } from '../apiClient';

// helper for road closure type names from Municipal 511

// 🚧 Barricade Icon for Road Closures
export default function MapBoard({ onReviewCall, onLaunchKiosk, initialMode = "EXPLORE" }) {
  const {
    map, setMap, currentZoom, isOffDefault, userPanned, setUserPanned,
    fitTo, invalidateSoon,
  } = useMapInstance();

  // Safe dynamic compile-time stamp
  const buildTime = typeof __BUILD_DATE__ !== 'undefined' ? __BUILD_DATE__ : new Date().toISOString();

  // RAW DATA STATES
  const [zones, setZones] = useState([]);
  const [selectedClosure, setSelectedClosure] = useState(null);
  
  // APP/TERMINAL STATE
  const [appMode, setAppMode] = useState(initialMode);

  // Sync the initialMode prop into local state during render rather than in an
  // effect: an effect renders the stale mode once before correcting itself.
  const [prevInitialMode, setPrevInitialMode] = useState(initialMode);
  if (initialMode && initialMode !== prevInitialMode) {
    setPrevInitialMode(initialMode);
    setAppMode(initialMode);
  }
  const [activeDispatch, setActiveDispatch] = useState(null);
  // Layer visibility and road-closure filters live in one hook so the sidebars can be
  // given {...layers} rather than forty lines of individual prop pass-through.
  const layers = useMapLayerPreferences();
  // Only the values MapBoard itself renders with. The closure time-window and access
  // filters are not destructured: they are consumed by useRoadClosures, which takes the
  // whole `layers` object, and reach the sidebars through {...layers}.
  const {
    mapStyle, showLabels, showHydrants, showZones, showRoadClosures,
    showRailroadCrossings, showFireHalls,
    // Header takes these three explicitly rather than by spread: it uses six of the
    // hook's values, so listing them keeps its interface visible.
    setMapStyle, setShowLabels, setShowRoadClosures,
    applyModeDefaults,
  } = layers;

  // Road closures and the filtered subset the map and alert count render.
  const { roadClosures, activeClosures } = useRoadClosures(layers);
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
      : []; // No units on the dispatch: show nothing rather than inventing apparatus.

    return calculateEVORouteMetrics({
      originCoords: origin,
      targetCoords: target,
      dispatchedUnits,
      routeCoordinates,
      unitMetrics: activeDispatch?.routing_metrics || []
    });
  }, [targetAddress, homeHall, routeCoordinates, activeDispatch]);



  // Load all hydrants data and fire zones once on mount
  useEffect(() => {
    const baseUrl = import.meta.env.BASE_URL;
    // public.hydrants via the API. This previously fetched data/hydrants.json, which was
    // deleted when hydrants moved to the database -- the request 404'd, the handler
    // swallowed it into an empty array, and the console's nearest-hydrant panel was
    // silently empty on every search. MapLayers already reads the API.
    fetch(`${API_BASE_URL}/api/hydrants`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(data => {
        setAllHydrantsData(Array.isArray(data) ? data : []);
      })
      .catch(err => {
        console.error("Failed to load hydrants from /api/hydrants:", err);
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
    // setUserPanned is a useState setter and therefore stable, but it now arrives through
    // useMapInstance, so the compiler can no longer prove that and bails out of optimizing
    // this component unless it is declared. Listing it changes nothing at runtime.
  }, [setUserPanned]);

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
      const newCall = toActiveCall(dispatch);
      if (newCall) {
        setActiveDispatch(newCall);
        // toMapTarget keeps unresolved coordinates null (CLAUDE.md 6.1 / 5). They used to
        // fall back to COQUITLAM_CENTER here, which put the incident at City Centre inside
        // the isWithinCoquitlam bounds check, so no Tier 1 warning fired and nothing told
        // the crew.
        const target = toMapTarget(newCall);
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
      const updatedCall = toActiveCall(dispatch);
      setActiveDispatch(curr => {
        if (isSameDispatch(curr, updatedCall)) {
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
      const deletedCall = toActiveCall(dispatch);
      setActiveDispatch(curr => {
        if (isSameDispatch(curr, deletedCall)) {
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
      // Padding is asymmetric on purpose: the left sidebar and right inspection stack
      // both overlay the map, so an evenly padded fit tucks the route underneath them.
      fitTo([STATIONS[homeHall], targetCoords], {
        paddingTopLeft: [340, 80],
        paddingBottomRight: [400, 80],
      });
    }
  }, [map, targetAddress, homeHall, appMode, userPanned, targetCoords, fitTo]);


  // Auto-resize Leaflet map container to prevent gray areas when sidebars open/close
  useEffect(() => {
    return invalidateSoon();
  }, [invalidateSoon, leftSidebarOpen, rightSidebarOpen]);

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
      applyModeDefaults(mode);
      setLeftSidebarOpen(true);
      setRightSidebarOpen(false);
  }, [onLaunchKiosk, applyModeDefaults]);

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
          {...layers}
          leftSidebarOpen={leftSidebarOpen}
          setLeftSidebarOpen={setLeftSidebarOpen}
          appMode={appMode}
          activeDispatch={activeDispatch}
          setActiveDispatch={setActiveDispatch}
          onOpenRoutingConfig={() => setShowRoutingConfigModal(true)}
          homeHall={homeHall}
          setHomeHall={setHomeHall}
          targetAddress={targetAddress}
          setTargetAddress={updateTargetAddress}
          nearestHydrant={nearestHydrants[0] || null}
          nearestHydrants={nearestHydrants}
          routeMetrics={routeMetrics}
          map={map}
        />

        {/* Map Container Wrapper */}
        <div className="flex-grow h-full relative flex flex-col bg-slate-900 min-w-0">
          <MapSurface
              center={COQUITLAM_CENTER}
              zoom={12}
              minZoom={12}
              maxZoom={22}
              maxBounds={OPERATIONAL_BOUNDS}
              maxBoundsViscosity={1.0}
              mapRef={setMap}
              baseStyle={(appMode === "EXPLORE" && (mapStyle === "SATELLITE" || mapStyle === "SATELLITE_ESRI")) ? mapStyle : (showLabels && currentZoom >= 16) ? "GREY" : (showLabels || targetAddress || currentZoom <= 15) ? "VOYAGER" : "GREY"}
              showCadastral={showLabels && !cadastralError}
              onCadastralError={() => setCadastralError(true)}
              showFireHalls={showFireHalls}
              showHydrants={showHydrants}
          >
            <ZonesLayer zones={zones} visible={showZones} currentZoom={currentZoom} />

            {/* AT-GRADE RAILROAD CROSSINGS LAYER */}
            <RailroadCrossingsLayer visible={showRailroadCrossings} />
            
            <RoadClosuresLayer
              closures={activeClosures}
              visible={showRoadClosures}
              selectedClosure={selectedClosure}
              onSelect={setSelectedClosure}
            />

            {appMode === "EXPLORE" && (
              <DispatchTargetLayer
                targetAddress={targetAddress}
                targetPolygon={targetPolygon}
                targetCoords={targetCoords}
                targetMarkerRef={targetMarkerRef}
                nearestHydrants={nearestHydrants}
                originStation={STATIONS[homeHall]}
                onRouteCalculated={setRouteCoordinates}
              />
            )}
          </MapSurface>

          <MapViewControls
            map={map}
            currentZoom={currentZoom}
            isOffDefault={isOffDefault}
            userPanned={userPanned}
            setUserPanned={setUserPanned}
            targetAddress={targetAddress}
            targetCoords={targetCoords}
            homeStation={STATIONS[homeHall]}
            buildTime={buildTime}
          />
        </div>

        {/* Right 1/3 Spatial Inspection Stack Panel (Target Address, 3D Satellite, Street View) */}
        {appMode === "EXPLORE" && targetAddress && (
          <DetailStack
            call={targetAddress}
            className="w-[380px] bg-slate-950 border-l border-slate-800 p-3 z-[1000] flex-shrink-0 shadow-2xl animate-in slide-in-from-right duration-300"
            topCard={
              <TargetAddressCard
                targetAddress={targetAddress}
                nearestHydrants={nearestHydrants}
                onClose={() => setTargetAddress(null)}
              />
            }
          />
        )}

        {/* Right Sidebar Alerts Panel */}
        {(!targetAddress || appMode !== "EXPLORE") && (
          <RightSidebar 
            {...layers}
            rightSidebarOpen={rightSidebarOpen}
            setRightSidebarOpen={setRightSidebarOpen}
            appMode={appMode}
            roadClosures={roadClosures}
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
            onReviewCall={onReviewCall}
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