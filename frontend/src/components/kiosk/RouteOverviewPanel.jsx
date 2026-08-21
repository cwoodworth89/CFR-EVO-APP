import React, { useEffect, useState, useRef, useMemo } from 'react';
import { MapContainer, Marker, Popup, useMap, useMapEvents, ZoomControl } from 'react-leaflet';
import L from 'leaflet';
import * as turf from '@turf/turf';
import { RoutingOverlay } from '../RoutingOverlay';
import { BaseMap, CoquitlamOverlays, StationsLayer, HydrantsLayer } from '../MapLayers';
import { BASE_LAYERS } from '../MapConstants';
import { calculateEVORouteMetrics } from '../../utils/EVORoutingEngine';

// Dynamic Screen-Aware Route Auto-Fitter (Fills 85-90% of Map Container Area)
function AutoFitBounds({ origin, destination, userPanned, callKey }) {
  const map = useMap();
  const lastKeyRef = useRef(null);

  useEffect(() => {
    if (!map || !origin || !destination || destination.lat == null || destination.lng == null) return;

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

// Destination Target Icon (Gold)
const destIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-gold.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

// Alternate Candidate Target Icon (Sky Blue)
const altCandidateIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png',
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

  // Extract raw candidates if present (e.g. dual junction ambiguity)
  const rawCandidates = (activeCall?.candidates && Array.isArray(activeCall.candidates) && activeCall.candidates.length > 1)
    ? activeCall.candidates
    : (activeCall?.target?.candidates && Array.isArray(activeCall.target.candidates) && activeCall.target.candidates.length > 1)
    ? activeCall.target.candidates
    : null;

  const candidates = useMemo(() => {
    if (!rawCandidates) return null;
    return rawCandidates.map((c, i) => ({
      lat: c.lat ?? c.y ?? null,
      lng: c.lng ?? c.x ?? null,
      label: c.label || c.address || c.intersection || c.name || `Junction ${i + 1}`,
      raw: c
    })).filter(c => c.lat != null && c.lng != null);
  }, [rawCandidates]);

  const [selectedCandidateIdx, setSelectedCandidateIdx] = useState(0);

  const callKey = activeCall?.dispatch_id || activeCall?.id || (activeCall?.address ? activeCall.address : 'active-call');

  const activeCandidate = (candidates && candidates.length > selectedCandidateIdx)
    ? candidates[selectedCandidateIdx]
    : null;

  const rawDestLat = activeCandidate
    ? activeCandidate.lat
    : (activeCall?.lat ?? activeCall?.target?.lat ?? null);

  const rawDestLng = activeCandidate
    ? activeCandidate.lng
    : (activeCall?.lng ?? activeCall?.target?.lng ?? null);

  const hasValidCoords = rawDestLat != null && rawDestLng != null &&
    !isNaN(Number(rawDestLat)) && !isNaN(Number(rawDestLng)) &&
    (Number(rawDestLat) !== 0 || Number(rawDestLng) !== 0);

  const destLat = hasValidCoords ? Number(rawDestLat) : null;
  const destLng = hasValidCoords ? Number(rawDestLng) : null;
  const destination = hasValidCoords ? { lat: destLat, lng: destLng } : null;

  const [routeInfo, setRouteInfo] = useState(null);
  const [userPanned, setUserPanned] = useState(false);
  const [mapInstance, setMapInstance] = useState(null);
  const [isPanelOpen, setIsPanelOpen] = useState(true);

  // Automatically reset view state whenever the active call changes.
  // Must sit after the useState declarations above: referencing setUserPanned
  // earlier hit the temporal dead zone and threw on every new dispatch.
  useEffect(() => {
    setUserPanned(false);
    setSelectedCandidateIdx(0);
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

  // Dynamic responding units resolution
  const unitsToRoute = useMemo(() => {
    const units = activeCall?.responding_units ||
      activeCall?.verified_units ||
      activeCall?.units ||
      activeCall?.raw_units ||
      activeCall?.target?.responding_units ||
      activeCall?.target?.units;

    if (Array.isArray(units) && units.length > 0) return units;
    if (typeof units === 'string' && units.trim().length > 0) {
      return units.split(',').map((u) => u.trim()).filter(Boolean);
    }
    // No units in the dispatch record: route nothing rather than inventing apparatus.
    return [];
  }, [activeCall]);

  // ETAs come from the backend's persisted OSRM routing_metrics, never from a
  // client-side estimate.
  const persistedUnitMetrics = activeCall?.routing_metrics || activeCall?.target?.routing_metrics || [];

  const routeMetrics = useMemo(() => {
    if (!hasValidCoords) return null;
    return calculateEVORouteMetrics({
      originCoords: [origin.lat, origin.lng],
      targetCoords: [destLat, destLng],
      dispatchedUnits: unitsToRoute,
      unitMetrics: persistedUnitMetrics
    });
  }, [origin, destLat, destLng, hasValidCoords, unitsToRoute, persistedUnitMetrics]);

  const handleRecenter = () => {
    setUserPanned(false);
    if (mapInstance) {
      if (hasValidCoords && destination) {
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
      } else {
        mapInstance.setView([origin.lat, origin.lng], 13, { animate: true });
      }
    }
  };

  const targetAddressDisplay = activeCandidate?.label || activeCall?.address || activeCall?.target?.address || 'Target';

  return (
    <div className="relative w-full h-full rounded-2xl overflow-hidden border border-slate-800 bg-slate-950 shadow-2xl">
      {/* Interactive Dual Junction Ambiguity Banner */}
      {candidates && candidates.length > 1 && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-[1001] bg-slate-950/95 border-2 border-amber-500 rounded-2xl shadow-2xl p-2.5 px-4 backdrop-blur-md flex flex-col items-center gap-2 max-w-[90%] sm:max-w-xl animate-in fade-in duration-200">
          <div className="flex items-center gap-2 text-amber-400 font-mono text-xs font-black tracking-wider uppercase">
            <span>⚠️</span>
            <span>DUAL JUNCTION AMBIGUITY ({candidates.length} JUNCTIONS IN AREA)</span>
          </div>
          <div className="flex items-center gap-2 flex-wrap justify-center">
            {candidates.map((cand, idx) => {
              const isSelected = idx === selectedCandidateIdx;
              return (
                <button
                  key={idx}
                  onClick={() => {
                    setSelectedCandidateIdx(idx);
                    setUserPanned(false);
                  }}
                  className={`px-3 py-1.5 rounded-xl font-mono text-xs font-bold transition flex items-center gap-1.5 shadow cursor-pointer border ${
                    isSelected
                      ? 'bg-amber-500 text-slate-950 border-amber-400 ring-2 ring-amber-400 font-black'
                      : 'bg-slate-900 hover:bg-slate-800 text-sky-400 border-slate-700 hover:border-sky-500'
                  }`}
                >
                  <span>[{idx + 1}]</span>
                  <span>{cand.label}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* High-Visibility Amber Warning Box for Unresolved Incident Location */}
      {!hasValidCoords && (
        <div className="absolute inset-x-4 top-20 z-[1000] mx-auto max-w-lg bg-amber-950/95 border-2 border-amber-500 text-amber-200 p-4 rounded-2xl shadow-2xl backdrop-blur-md flex items-center gap-3 animate-pulse">
          <span className="text-3xl">⚠️</span>
          <div>
            <h4 className="text-sm font-black tracking-wider text-amber-300 uppercase font-mono">
              UNRESOLVED INCIDENT LOCATION — ROUTING PAUSED
            </h4>
            <p className="text-xs font-mono text-amber-100/90 mt-0.5">
              Address: &quot;{activeCall?.address || activeCall?.target?.address || 'Unknown'}&quot;
            </p>
          </div>
        </div>
      )}

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
                From {origin.name ? origin.name.split(' (')[0] : 'Hall 1'} → {targetAddressDisplay}
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
            {/* Dispatched Apparatus Unit ETAs List */}
            <div className="flex flex-col gap-1.5">
              <div className="flex justify-between items-center px-1">
                <span className="text-[9px] text-slate-400 uppercase font-mono font-extrabold tracking-wider">
                  Dispatched Apparatus ETAs
                </span>
                <span className="text-[8.5px] text-sky-400 font-mono font-bold">OSRM</span>
              </div>

              {routeMetrics?.units?.map((u, idx) => (
                <div key={idx} className="flex justify-between items-center bg-slate-900/90 px-3 py-2 rounded-xl border border-slate-800 font-mono">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full flex-shrink-0 shadow-sm" style={{ backgroundColor: u.color }} />
                    <span className="text-white text-xs font-black">{u.unit}</span>
                    <span className="text-[8px] text-slate-400 uppercase font-extrabold bg-slate-800 px-1.5 py-0.5 rounded border border-slate-750">{u.tierKey}</span>
                  </div>
                  <div className="flex items-center gap-2.5">
                    <span className="text-slate-400 text-[10.5px]">{u.distanceKm != null ? `${u.distanceKm} km` : '-- km'}</span>
                    <span className="text-emerald-400 text-xs font-black">{u.etaMinutes != null ? `${u.etaMinutes} min` : '-- min'}</span>
                  </div>
                </div>
              ))}

              {!hasValidCoords && (
                <div className="p-2.5 rounded-xl bg-amber-950/40 border border-amber-800/40 text-amber-300 text-[10px] font-mono text-center">
                  ⚠️ Routing paused — awaiting location
                </div>
              )}
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
        center={hasValidCoords ? [destLat, destLng] : [origin.lat, origin.lng]}
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

        {/* Offline-First Navigation Basemap (Prioritizes local :8081 tile server with graceful online fallback) */}
        <BaseMap style="VOYAGER" />

        {/* Coquitlam Municipal Cadastral Layer */}
        <CoquitlamOverlays visible={true} />

        {/* Station Halls Layer */}
        <StationsLayer visible={true} />

        {/* Live OSRM Emergency Response Routing Overlay */}
        {hasValidCoords && (
          <RoutingOverlay
            from={[origin.lat, origin.lng]}
            to={[destLat, destLng]}
            onRouteCalculated={handleRouteCalculated}
          />
        )}

        {/* Candidate or Single Target Markers */}
        {hasValidCoords && (
          candidates && candidates.length > 1 ? (
            candidates.map((cand, idx) => {
              const isSelected = idx === selectedCandidateIdx;
              return (
                <Marker
                  key={idx}
                  position={[cand.lat, cand.lng]}
                  icon={isSelected ? destIcon : altCandidateIcon}
                  eventHandlers={{
                    click: () => {
                      setSelectedCandidateIdx(idx);
                      setUserPanned(false);
                    }
                  }}
                >
                  <Popup>
                    <div className="font-mono text-xs">
                      <div className="font-bold text-amber-500 uppercase">
                        {isSelected ? '★ Active Destination' : 'Alternate Candidate'} [{idx + 1}]
                      </div>
                      <div className="text-slate-900 mt-0.5">{cand.label}</div>
                      {!isSelected && (
                        <button
                          onClick={() => {
                            setSelectedCandidateIdx(idx);
                            setUserPanned(false);
                          }}
                          className="mt-1.5 px-2 py-1 bg-sky-600 hover:bg-sky-500 text-white rounded text-[10px] font-bold cursor-pointer"
                        >
                          Switch Route Here
                        </button>
                      )}
                    </div>
                  </Popup>
                </Marker>
              );
            })
          ) : (
            <Marker position={[destLat, destLng]} icon={destIcon}>
              <Popup>Target Destination: {activeCall?.address || 'Incident Location'}</Popup>
            </Marker>
          )
        )}

        {hasValidCoords && (
          <AutoFitBounds
            origin={origin}
            destination={destination}
            userPanned={userPanned}
            callKey={`${callKey}-${selectedCandidateIdx}`}
          />
        )}
      </MapContainer>
    </div>
  );
}

