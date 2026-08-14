import React, { useEffect, useState, useRef, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap, useMapEvents, ZoomControl } from 'react-leaflet';
import L from 'leaflet';
import * as turf from '@turf/turf';
import { RoutingOverlay } from '../RoutingOverlay';
import { CoquitlamOverlays, StationsLayer, HydrantsLayer } from '../MapLayers';
import { BASE_LAYERS } from '../MapConstants';
import { calculateEVORouteMetrics } from '../../utils/EVORoutingEngine';

// Dynamic Screen-Aware Route Auto-Fitter (Fills 85-90% of Map Container Area)
function AutoFitBounds({ origin, destination, userPanned, callKey }) {
  const map = useMap();
  const lastKeyRef = useRef(null);

  useEffect(() => {
    if (!map || !origin || !destination) return;

    const currentKey = callKey || `${destination.lat},${destination.lng}`;
    const callChanged = lastKeyRef.current !== currentKey;
    if (callChanged) {
      lastKeyRef.current = currentKey;
    }

    // Don't auto-fit if user manually panned on the SAME call, but ALWAYS auto-fit when active call changes!
    if (userPanned && !callChanged) return;

    const bounds = L.latLngBounds(
      [origin.lat, origin.lng],
      [destination.lat, destination.lng]
    );

    // Calculate dynamic container-aware padding percentage so route scales to fill map space
    const containerSize = map.getSize();
    const w = containerSize.x || 800;
    const h = containerSize.y || 600;

    const padTop = Math.max(45, Math.round(h * 0.12));
    const padBottom = Math.max(35, Math.round(h * 0.08));
    const padSide = Math.max(35, Math.round(w * 0.08));

    map.fitBounds(bounds, {
      paddingTopLeft: [padSide, padTop],
      paddingBottomRight: [padSide, padBottom],
      maxZoom: 17,
      animate: true
    });
  }, [map, origin, destination, userPanned, callKey]);

  return null;
}

// Interactivity listener to detect manual pan/zoom
function MapInteractivity({ onPan }) {
  useMapEvents({
    dragstart: () => onPan && onPan(),
    zoomstart: () => onPan && onPan()
  });
  return null;
}

// Destination Target Icon
const destIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-gold.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

export default function RouteOverviewPanel({ activeCall, stationHall }) {
  const origin = stationHall || {
    lat: 49.29109654571679,
    lng: -122.79072561861948,
    name: 'Hall 1 (1300 Pinetree Way)'
  };
  const destLat = activeCall?.lat ?? 49.2838;
  const destLng = activeCall?.lng ?? -122.7932;
  const destination = { lat: destLat, lng: destLng };

  const [routeInfo, setRouteInfo] = useState(null);
  const [userPanned, setUserPanned] = useState(false);
  const [mapInstance, setMapInstance] = useState(null);
  const [isPanelOpen, setIsPanelOpen] = useState(true);

  const callKey = activeCall?.dispatch_id || activeCall?.id || (activeCall?.address ? activeCall.address : `${destLat},${destLng}`);

  // Automatically reset userPanned whenever the active call changes so new dispatches auto-center
  useEffect(() => {
    setUserPanned(false);
  }, [callKey]);

  const handleRouteCalculated = (coordinates) => {
    if (coordinates && coordinates.length > 1) {
      let totalDist = 0;
      for (let i = 0; i < coordinates.length - 1; i++) {
        const from = turf.point([coordinates[i][1], coordinates[i][0]]);
        const to = turf.point([coordinates[i + 1][1], coordinates[i + 1][0]]);
        totalDist += turf.distance(from, to, { units: 'kilometers' });
      }
      setRouteInfo({ distanceKm: totalDist });
    }
  };

  const routeMetrics = useMemo(() => {
    return calculateEVORouteMetrics({
      originCoords: [origin.lat, origin.lng],
      targetCoords: [destLat, destLng],
      dispatchedUnits: ['SQ1', 'E1', 'L1']
    });
  }, [origin, destLat, destLng]);

  const handleRecenter = () => {
    setUserPanned(false);
    if (mapInstance) {
      const bounds = L.latLngBounds(
        [origin.lat, origin.lng],
        [destination.lat, destination.lng]
      );
      const containerSize = mapInstance.getSize();
      const w = containerSize.x || 800;
      const h = containerSize.y || 600;

      const padTop = Math.max(45, Math.round(h * 0.12));
      const padBottom = Math.max(35, Math.round(h * 0.08));
      const padSide = Math.max(35, Math.round(w * 0.08));

      mapInstance.fitBounds(bounds, {
        paddingTopLeft: [padSide, padTop],
        paddingBottomRight: [padSide, padBottom],
        maxZoom: 17,
        animate: true
      });
    }
  };

  return (
    <div className="relative w-full h-full rounded-2xl overflow-hidden border border-slate-800 bg-slate-950 shadow-2xl">
      {/* Option A: Collapsible Left Dispatch Details & ETAs Panel */}
      <div className="absolute top-3 left-3 z-[1000] w-72 sm:w-80 bg-slate-950/90 backdrop-blur-md border border-slate-800 rounded-2xl shadow-2xl overflow-hidden transition-all duration-300">
        {/* Panel Header Toggle Bar */}
        <div 
          onClick={() => setIsPanelOpen(!isPanelOpen)}
          className="bg-slate-900 border-b border-slate-800 p-3 flex items-center justify-between cursor-pointer hover:bg-slate-850 transition"
        >
          <div className="flex items-center gap-2.5">
            <span className="text-lg">🚒</span>
            <div>
              <h3 className="text-xs font-black text-white uppercase tracking-wider">Dispatch Details & ETAs</h3>
              <p className="text-[10px] font-bold text-emerald-400 font-mono">
                From {origin.name ? origin.name.split(' (')[0] : 'Hall 1'} → {activeCall?.address || 'Target'}
              </p>
            </div>
          </div>
          <button className="text-slate-400 hover:text-white text-xs font-mono font-bold px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700">
            {isPanelOpen ? '▲' : '▼'}
          </button>
        </div>

        {/* Collapsible Panel Content Body */}
        {isPanelOpen && (
          <div className="p-3 flex flex-col gap-2.5 animate-in fade-in duration-200">
            {/* Railroad Crossing Warning Badge */}
            {routeMetrics?.railroadWarning && (
              <div className={`p-2 rounded-xl text-[9.5px] font-mono font-bold leading-snug flex items-center gap-2 border ${
                routeMetrics.railroadWarning.type === 'AVOIDED'
                  ? 'bg-emerald-950/90 border-emerald-700 text-emerald-300'
                  : 'bg-amber-950/90 border-amber-700 text-amber-300'
              }`}>
                <span>⚠️</span>
                <span>{routeMetrics.railroadWarning.badge}</span>
              </div>
            )}

            {/* Dispatched Apparatus Unit ETAs List */}
            <div className="flex flex-col gap-1.5">
              <div className="flex justify-between items-center px-1">
                <span className="text-[9px] text-slate-400 uppercase font-mono font-extrabold tracking-wider">
                  Dispatched Apparatus ETAs
                </span>
                <span className="text-[8.5px] text-sky-400 font-mono font-bold">EMTRAC Code 3</span>
              </div>

              {routeMetrics?.units?.map((u, idx) => (
                <div key={idx} className="flex justify-between items-center bg-slate-900/90 px-3 py-2 rounded-xl border border-slate-800 font-mono">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full flex-shrink-0 shadow-sm" style={{ backgroundColor: u.color }} />
                    <span className="text-white text-xs font-black">{u.unit}</span>
                    <span className="text-[8px] text-slate-400 uppercase font-extrabold bg-slate-800 px-1.5 py-0.5 rounded border border-slate-750">{u.tierKey}</span>
                  </div>
                  <div className="flex items-center gap-2.5">
                    <span className="text-slate-400 text-[10.5px]">{u.distanceKm} km</span>
                    <span className="text-emerald-400 text-xs font-black">{u.etaMinutes} min</span>
                  </div>
                </div>
              ))}
            </div>

            {/* Hydrant & Tactical Notes Bar */}
            <div className="bg-slate-900/80 border border-slate-800 p-2.5 rounded-xl flex items-center justify-between text-xs font-mono">
              <div className="flex items-center gap-2 text-sky-400 font-bold">
                <span>💧</span>
                <span className="text-[10.5px] text-slate-200">
                  {activeCall?.hydrant || activeCall?.target?.hydrant || 'City Hydrant: D-165 (42m)'}
                </span>
              </div>
              <span className="text-[9px] text-slate-400 uppercase font-bold bg-slate-800 px-1.5 py-0.5 rounded">
                NFPA 291
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Floating Re-Center Button when user pans or zooms */}
      {userPanned && (
        <button
          onClick={handleRecenter}
          className="absolute top-3 right-14 z-[1000] bg-sky-600 hover:bg-sky-500 text-white font-mono text-xs font-black px-3.5 py-2 rounded-xl shadow-xl border border-sky-400 flex items-center gap-1.5 cursor-pointer animate-pulse"
        >
          <span>🎯</span>
          <span>RE-CENTER ROUTE</span>
        </button>
      )}

      <MapContainer
        center={[destLat, destLng]}
        zoom={13}
        className="w-full h-full z-0"
        zoomControl={false}
        dragging={true}
        scrollWheelZoom={true}
        doubleClickZoom={true}
        touchZoom={true}
        ref={setMapInstance}
      >
        <MapInteractivity onPan={() => setUserPanned(true)} />
        <ZoomControl position="bottomright" />

        {/* CartoDB Voyager Navigation Basemap (Matches main landing page) */}
        <TileLayer
          attribution={BASE_LAYERS.VOYAGER.attribution}
          url={BASE_LAYERS.VOYAGER.url}
          subdomains={BASE_LAYERS.VOYAGER.subdomains}
          maxZoom={22}
        />

        {/* Coquitlam Municipal Cadastral Layer */}
        <CoquitlamOverlays visible={true} />

        {/* Station Halls Layer */}
        <StationsLayer visible={true} />

        {/* Live OSRM Emergency Response Routing Overlay */}
        <RoutingOverlay
          from={[origin.lat, origin.lng]}
          to={[destLat, destLng]}
          onRouteCalculated={handleRouteCalculated}
        />

        <Marker position={[destLat, destLng]} icon={destIcon}>
          <Popup>Target Destination: {activeCall?.address}</Popup>
        </Marker>

        <AutoFitBounds origin={origin} destination={destination} userPanned={userPanned} callKey={callKey} />
      </MapContainer>
    </div>
  );
}
