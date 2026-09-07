/* global __BUILD_DATE__ */
// NOTE: Map layout config is in docs/gis_endpoints.md, but its local-JSON sections are
// SUPERSEDED -- hydrants/zones now come from PostGIS via the API, not public/data/*.json.
import React, { useEffect, useState, useRef, useCallback, useMemo } from 'react'; // Added useRef, useCallback, useMemo
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

// Import from your other components
import { RailroadCrossingsLayer } from './MapLayers';
import { MapClickEvents } from './MapActions';
import { CircleMarker, Tooltip } from 'react-leaflet';
import { Header } from './hud/Header';
import { LeftSidebar } from './hud/LeftSidebar';
import { RightSidebar } from './hud/RightSidebar';
import { MODE_DEFAULTS, UNIT_COLORS, STATIONS_MAP as STATIONS, KNOWN_BUILDINGS, OPERATIONAL_BOUNDS, COQUITLAM_CENTER } from './MapConstants';
import { enrichAddressWithBuilding } from './map/mapGeometry';
import { pickRouteHydrants } from '../utils/routeHydrants';
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
import { apiClient, API_BASE_URL } from '../apiClient';

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
  // Arrival point (punch-list #49): the parcel row behind the searched address, the
  // placement mode, and the draft pin the operator has clicked but not yet saved.
  const [targetParcel, setTargetParcel] = useState(null);
  const [placingEntrance, setPlacingEntrance] = useState(false);
  const [entranceDraft, setEntranceDraft] = useState(null);
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
    setRouteCoordinates([]);
    // setUserPanned is a useState setter and therefore stable, but it now arrives through
    // useMapInstance, so the compiler can no longer prove that and bails out of optimizing
    // this component unless it is declared. Listing it changes nothing at runtime.
  }, [setUserPanned]);

  // The parcel row for the searched address: its entrance_* columns drive the arrival
  // point section of the card. Cleared with the target.
  useEffect(() => {
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTargetParcel(null);
    setPlacingEntrance(false);
    setEntranceDraft(null);
    const key = targetAddress?.address;
    if (!key) return undefined;
    apiClient.parcels.lookup(key).then((res) => {
      if (!cancelled && res?.found && res.parcel) setTargetParcel(res.parcel);
    }).catch(() => { /* the card says the parcel is unknown */ });
    return () => { cancelled = true; };
  }, [targetAddress?.address]);

  const handleEntranceMapClick = useCallback((latlng) => {
    if (!placingEntrance || !latlng) return;
    setEntranceDraft({ lat: latlng.lat, lng: latlng.lng });
  }, [placingEntrance]);

  const saveEntrance = useCallback(async ({ lat, lng, note, setBy }) => {
    if (!targetParcel) throw new Error('No parcel behind this address');
    const res = await apiClient.parcels.saveEntrance({
      gis_id: targetParcel.gis_id, address: targetParcel.address,
      lat, lng, note, set_by: setBy,
    });
    const parcel = res?.parcel;
    setTargetParcel(parcel || null);
    setPlacingEntrance(false);
    setEntranceDraft(null);
    // The map follows the ruling: the route and the hydrant picks measure from the new
    // point, or from the computed frontage again after a clear.
    if (parcel) {
      const nextLat = parcel.entrance_lat ?? parcel.front_lat ?? parcel.lat;
      const nextLng = parcel.entrance_lng ?? parcel.front_lng ?? parcel.lng;
      if (nextLat != null && nextLng != null) {
        setTargetAddress(prev => prev ? { ...prev, lat: nextLat, lng: nextLng, front_lat: nextLat, front_lng: nextLng } : prev);
        setRouteCoordinates([]);
      }
    }
    return parcel;
  }, [targetParcel]);

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

  // The hydrants to show for the searched address, by the operator's rule
  // (utils/routeHydrants.js): along the route within 300 ft of arrival first, then around
  // the address, then within the 1,000 ft supply lay. Replaces the Alpha-segment version
  // (2026-09-06, punch-list #74). Picks carry `distance` in metres and `how`.
  const routeHydrants = useMemo(() => {
    if (!targetAddress || allHydrantsData.length === 0) return { tier: 'no_target', picks: [], routeKnown: false };
    const lat = targetAddress.front_lat ?? targetAddress.lat;
    const lng = targetAddress.front_lng ?? targetAddress.lng;
    if (lat == null || lng == null) return { tier: 'no_target', picks: [], routeKnown: false };
    return pickRouteHydrants({
      hydrants: allHydrantsData,
      routeCoords: routeCoordinates || [],
      destination: { lat: Number(lat), lng: Number(lng) },
    });
  }, [allHydrantsData, targetAddress, routeCoordinates]);
  const nearestHydrants = routeHydrants.picks;
  const hydrantHighlightIds = useMemo(() => new Set(nearestHydrants.map(h => h.gisId)), [nearestHydrants]);

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
              baseStyle={(appMode === "EXPLORE" && mapStyle === "SATELLITE") ? "SATELLITE" : (showLabels && currentZoom >= 16) ? "GREY" : (showLabels || targetAddress || currentZoom <= 15) ? "VOYAGER" : "GREY"}
              showCadastral={showLabels && !cadastralError}
              onCadastralError={() => setCadastralError(true)}
              showFireHalls={showFireHalls}
              // The full layer stays behind its toggle; a searched address gets its picks
              // drawn by DispatchTargetLayer regardless (operator, 2026-09-06, #74: "I don't
              // need to see all of those hydrants. Just the recommended ones").
              showHydrants={showHydrants}
              hydrantHighlightIds={hydrantHighlightIds}
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

            {appMode === "EXPLORE" && placingEntrance && (
              <MapClickEvents onMapClick={handleEntranceMapClick} />
            )}
            {appMode === "EXPLORE" && entranceDraft && (
              <CircleMarker
                center={[entranceDraft.lat, entranceDraft.lng]}
                radius={10}
                pathOptions={{ color: '#f59e0b', fillColor: '#fbbf24', fillOpacity: 0.9, weight: 3, dashArray: '4 3' }}
              >
                <Tooltip permanent direction="top" offset={[0, -10]}>Arrival point (unsaved)</Tooltip>
              </CircleMarker>
            )}
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
                hydrantTier={routeHydrants.tier}
                parcel={targetParcel}
                placingEntrance={placingEntrance}
                entranceDraft={entranceDraft}
                onStartPlacing={() => { setPlacingEntrance(true); setEntranceDraft(null); }}
                onCancelPlacing={() => { setPlacingEntrance(false); setEntranceDraft(null); }}
                onSaveEntrance={saveEntrance}
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