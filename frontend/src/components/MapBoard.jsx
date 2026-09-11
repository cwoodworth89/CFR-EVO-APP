/* global __BUILD_DATE__ */
// NOTE: Map layout config is in docs/gis_endpoints.md, but its local-JSON sections are
// SUPERSEDED -- hydrants/zones now come from PostGIS via the API, not public/data/*.json.
import React, { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

// Import from your other components
import { RailroadCrossingsLayer } from './MapLayers';
import { MapClickEvents } from './MapActions';
import { useArrivalPoint } from '../hooks/useArrivalPoint';
import { CircleMarker, Tooltip } from 'react-leaflet';
import { Header } from './hud/Header';
import { useAdminSession } from '../hooks/useAdminSession';
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
import { useCompactViewport } from '../hooks/useCompactViewport';
import { routeFitOptions } from './map/fitPadding';

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
export default function MapBoard({ onReviewCall, initialMode = "EXPLORE" }) {
  const {
    map, setMap, currentZoom, isOffDefault, userPanned, setUserPanned, resetView,
    fitTo, invalidateSoon,
  } = useMapInstance();

  // Safe dynamic compile-time stamp
  const buildTime = typeof __BUILD_DATE__ !== 'undefined' ? __BUILD_DATE__ : new Date().toISOString();

  // RAW DATA STATES
  const [zones, setZones] = useState([]);
  const [selectedClosure, setSelectedClosure] = useState(null);
  
  // APP/TERMINAL STATE
  const [appMode, setAppMode] = useState(initialMode);
  const admin = useAdminSession();
  // A phone (below `lg`): the sidebars become sheets over the map and the detail stack a
  // tabbed sheet at the bottom; the fits pad by what the sheet covers. Above `md` nothing
  // changes; `md` was measured too narrow (hooks/useCompactViewport.js).
  const compact = useCompactViewport();
  const stackRef = useRef(null);
  const getFitOverlays = useCallback(
    () => (compact && stackRef.current ? { bottom: stackRef.current.offsetHeight || 0 } : null),
    [compact],
  );

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
  const [routeCoordinates, setRouteCoordinates] = useState([]);
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

  // Arrival point (punch-list #49), the same hook the dispatch display uses in a review
  // replay: the parcel row behind the searched address, the placement mode, the draft pin.
  const arrival = useArrivalPoint({
    address: targetAddress?.address,
    // The map follows the ruling: the route and the hydrant picks measure from the new
    // point, or from the computed frontage again after a clear.
    onSaved: useCallback((parcel) => {
      if (!parcel) return;
      const nextLat = parcel.entrance_lat ?? parcel.front_lat ?? parcel.lat;
      const nextLng = parcel.entrance_lng ?? parcel.front_lng ?? parcel.lng;
      if (nextLat != null && nextLng != null) {
        setTargetAddress(prev => prev ? { ...prev, lat: nextLat, lng: nextLng, front_lat: nextLat, front_lng: nextLng } : prev);
        setRouteCoordinates([]);
      }
    }, []),
  });
  const targetParcel = arrival.parcel;

  // The parcel outline, drawn on the map and in the satellite tile the way a dispatch draws
  // it (operator, 2026-09-08: "good for checking out how the screen will look during a
  // dispatch event and for pre-planning"). The search result carries no geometry; the
  // lookup behind the hook does.
  useEffect(() => {
    if (!Array.isArray(targetParcel?.rings) || targetParcel.rings.length === 0) return;
    setTargetPolygon(targetParcel.rings.map(ring => ring.map(coord => [coord[1], coord[0]])));
  }, [targetParcel]);

  // What the detail stack sees: the searched target with the parcel's rings from the
  // lookup, so the satellite tile outlines the parcel as it does on a dispatch.
  const stackCall = useMemo(() => {
    if (!targetAddress) return null;
    const rings = targetParcel?.rings?.length ? targetParcel.rings : (targetAddress.rings || []);
    return { ...targetAddress, rings };
  }, [targetAddress, targetParcel]);




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

  // Fit the origin hall and the destination. The padding is measured from the map
  // (map/fitPadding.js). It was written as [340, 80] / [400, 80] on the belief that the
  // sidebars overlay the map; they are flex siblings and the map is already narrowed by
  // them, so the route was fitted into the middle half of what was left, and on a phone the
  // literals exceeded the container, which Leaflet answers with a NaN zoom (measured
  // 2026-09-09, docs/standards/dependency-behaviour.md). On a phone the detail sheet does
  // overlay the map, and its measured height pads the bottom.
  useEffect(() => {
    if (map && targetAddress && STATIONS[homeHall] && appMode === "EXPLORE" && !userPanned && targetCoords) {
      fitTo([STATIONS[homeHall], targetCoords], routeFitOptions(map, { animate: true, overlays: getFitOverlays() }));
    }
  }, [map, targetAddress, homeHall, appMode, userPanned, targetCoords, fitTo, getFitOverlays]);


  // Auto-resize Leaflet map container to prevent gray areas when sidebars open/close
  useEffect(() => {
    return invalidateSoon();
  }, [invalidateSoon, leftSidebarOpen, rightSidebarOpen, compact]);

  const startMode = useCallback((mode) => {
      setAppMode(mode);
      setActiveDispatch(null);
      setTargetAddress(null);
      applyModeDefaults(mode);
      setLeftSidebarOpen(true);
      setRightSidebarOpen(false);
  }, [applyModeDefaults]);

  // Locking while on the review screen returns to the map: the admin entry is gone from
  // the select and the screen behind it is admin-only. Waits for the first session check,
  // so a return from a review replay (initialMode ADMIN_DISPATCHES) is not bounced before
  // the stored token has been verified.
  useEffect(() => {
    if (!(admin.checked && !admin.unlocked && appMode === 'ADMIN_DISPATCHES')) return undefined;
    const id = window.setTimeout(() => startMode('EXPLORE'), 0);
    return () => window.clearTimeout(id);
  }, [admin.checked, admin.unlocked, appMode, startMode]);

  // One expression for which base layer is actually drawn, so the overlays that have to
  // read against it -- the zone numbers -- cannot disagree with it.
  const baseStyle = (appMode === "EXPLORE" && mapStyle === "SATELLITE") ? "SATELLITE" : "STREET";

  // Whether the street tiles carry their own labels. This used to be smuggled inside the
  // choice between two BASE_LAYERS names ("GREY" meant no labels, "VOYAGER" meant labels),
  // which read as a style preference rather than the decision it is. The rule is unchanged.
  //
  // Note the middle clause is not a typo: turning "Road Names & Addresses" ON at zoom 16+
  // takes labels OFF the basemap, because that same toggle draws the cadastral overlay,
  // which carries its own road names -- two sets of labels on one map is worse than none.
  const streetLabels = baseStyle === "STREET"
    && !(showLabels && currentZoom >= 16)
    && Boolean(showLabels || targetAddress || currentZoom <= 15);

  return (
    <div className="h-dvh w-screen flex flex-col bg-slate-950 overflow-hidden text-slate-100 font-sans safe-area">
      
      <Header 
        admin={admin}
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

      <div className="flex flex-row flex-1 min-h-0 w-full relative overflow-hidden z-10">
        {/* Left Control Panel & Option Toggles */}
        <LeftSidebar 
          {...layers}
          compact={compact}
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
              baseStyle={baseStyle}
              streetLabels={streetLabels}
              showCadastral={showLabels && !cadastralError}
              onCadastralError={() => setCadastralError(true)}
              showFireHalls={showFireHalls}
              // The full layer stays behind its toggle; a searched address gets its picks
              // drawn by DispatchTargetLayer regardless (operator, 2026-09-06, #74: "I don't
              // need to see all of those hydrants. Just the recommended ones").
              showHydrants={showHydrants}
              hydrantHighlightIds={hydrantHighlightIds}
          >
            <ZonesLayer zones={zones} visible={showZones} currentZoom={currentZoom} onImagery={baseStyle === "SATELLITE"} />

            {/* AT-GRADE RAILROAD CROSSINGS LAYER */}
            <RailroadCrossingsLayer visible={showRailroadCrossings} />
            
            <RoadClosuresLayer
              closures={activeClosures}
              visible={showRoadClosures}
              selectedClosure={selectedClosure}
              onSelect={setSelectedClosure}
            />

            {appMode === "EXPLORE" && arrival.placing && (
              <MapClickEvents onMapClick={arrival.onMapClick} />
            )}
            {appMode === "EXPLORE" && arrival.draft && (
              <CircleMarker
                center={[arrival.draft.lat, arrival.draft.lng]}
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
                nearestHydrants={nearestHydrants}
                currentZoom={currentZoom}
                originStation={STATIONS[homeHall]}
                homeHall={homeHall}
                routingMetrics={activeDispatch?.routing_metrics || []}
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
            nearestHydrants={nearestHydrants}
            homeStation={STATIONS[homeHall]}
            buildTime={buildTime}
            mapStyle={mapStyle}
            setMapStyle={setMapStyle}
            defaultMapStyle={MODE_DEFAULTS.EXPLORE}
            resetView={resetView}
            compact={compact}
            getFitOverlays={getFitOverlays}
          />
        </div>

        {/* Right 1/3 Spatial Inspection Stack Panel (Target Address, 3D Satellite, Street View) */}
        {/* Beside the map from `lg` up; a tabbed sheet over the bottom of it on a phone. The
            wrapper is measured for the fit padding, so the sheet's height is what it is. */}
        {appMode === "EXPLORE" && targetAddress && (
          <div
            ref={stackRef}
            className={compact
              ? 'absolute inset-x-0 bottom-0 z-[1000] bg-slate-950 border-t border-slate-800 rounded-t-2xl p-2 shadow-2xl'
              : 'w-[380px] h-full bg-slate-950 border-l border-slate-800 p-3 z-[1000] flex-shrink-0 shadow-2xl'}
          >
          <DetailStack
            call={stackCall}
            className="h-full"
            compact={compact}
            sheet={compact}
            topCard={
              <TargetAddressCard
                targetAddress={targetAddress}
                nearestHydrants={nearestHydrants}
                hydrantTier={routeHydrants.tier}
                parcel={targetParcel}
                placingEntrance={arrival.placing}
                entranceDraft={arrival.draft}
                onStartPlacing={arrival.start}
                onCancelPlacing={arrival.cancel}
                onSaveEntrance={arrival.save}
                adminUnlocked={admin.unlocked}
                onClose={() => setTargetAddress(null)}
              />
            }
          />
          </div>
        )}

        {/* Right Sidebar Alerts Panel */}
        {(!targetAddress || appMode !== "EXPLORE") && (
          <RightSidebar 
            {...layers}
            compact={compact}
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