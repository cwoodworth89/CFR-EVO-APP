import React, { useEffect, useState, useRef, useMemo } from 'react';
import { Marker, Popup, Polygon, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import { altCandidatePinIcon, targetPinIcon } from '../map/mapIcons';
import HallRoutesOverlay from '../map/HallRoutesOverlay';
import { hallColour, UNASSIGNED_HALL_COLOUR } from '../MapConstants';
import MapSurface from '../map/MapSurface';
import RoadClosuresLayer from '../map/RoadClosuresLayer';
import { useRoadClosures } from '../../hooks/useRoadClosures';
import { BASE_LAYERS, CADASTRAL_MIN_ZOOM } from '../MapConstants';
import { calculateEVORouteMetrics } from '../../utils/EVORoutingEngine';
import StreetSectionBanner from './StreetSectionBanner';
import ApproximateLocationBanner from './ApproximateLocationBanner';
import { useRouteHydrants } from '../../hooks/useRouteHydrants';
import PickedHydrantsLayer from '../map/PickedHydrantsLayer';
import { TIER } from '../../utils/routeHydrants';
import { routeFitOptions, snapFitOptions } from '../map/fitPadding';

// Dynamic Screen-Aware Route Auto-Fitter (Fills 85-90% of Map Container Area)
// A programmatic fit fires the same zoomstart the user's scroll wheel does, so the
// RE-CENTER button used to appear on every call before anyone touched the map (operator,
// 2026-09-06). The fit raises `fittingRef` for its duration and MapInteractivity ignores
// zoom events while it is up. A drag is always the user.
function markFitting(map, fittingRef) {
  if (!fittingRef) return;
  fittingRef.current = true;
  map.once('moveend', () => { fittingRef.current = false; });
  // A fit that changes nothing never fires moveend; release the flag anyway.
  setTimeout(() => { fittingRef.current = false; }, 800);
}

// Fits the route ONCE per call. Every later move of the map is the operator's: a drag, the
// RE-CENTER button, or SNAP TO CALL, and this effect must not undo them. Until 2026-09-08 it
// re-ran on every render (`destination` was a fresh object each time) and refitted whenever
// `userPanned` was false, so SNAP TO CALL flew to the parcel and was flown straight back --
// "the map blinks like it should do something but it doesn't move" (operator,
// DISP-2026-CE3851).
function AutoFitBounds({ origin, destination, callKey, fittingRef, panelRef, compact = false }) {
  const map = useMap();
  const lastKeyRef = useRef(null);

  useEffect(() => {
    if (!map || !origin || !destination || destination.lat == null || destination.lng == null) return;

    const currentKey = callKey || `${destination.lat},${destination.lng}`;
    if (lastKeyRef.current === currentKey) return;
    lastKeyRef.current = currentKey;

    const bounds = L.latLngBounds(
      [origin.lat, origin.lng],
      [destination.lat, destination.lng]
    );

    // Padding measured from the container and the details box (map/fitPadding.js): the
    // box floats over the top-left of the map on the hall display and across the top on a
    // phone, and the fit keeps the whole route clear of it either way, so the destination
    // pin is never under the box (operator, 2026-09-06: "it covers up the destination").
    markFitting(map, fittingRef);
    map.fitBounds(bounds, routeFitOptions(map, {
      panelEl: panelRef?.current, panelSide: compact ? 'top' : 'left', maxZoom: 17, animate: true,
    }));
  }, [map, origin, destination, callKey, fittingRef, panelRef, compact]);

  return null;
}

// Reports the map's zoom to the panel, for the layers that only make sense once the
// cadastral lines are on screen.
function ZoomWatcher({ onZoom }) {
  const map = useMap();
  useEffect(() => {
    const sync = () => onZoom(map.getZoom());
    map.on('zoomend', sync);
    sync();
    return () => map.off('zoomend', sync);
  }, [map, onZoom]);
  return null;
}

// Interactivity listener to detect manual pan/zoom
function MapInteractivity({ onPan, fittingRef }) {
  useMapEvents({
    dragstart: () => onPan && onPan(),
    zoomstart: () => { if (fittingRef?.current) return; if (onPan) onPan(); }
  });
  return null;
}

export default function RouteOverviewPanel({ activeCall, stationHall, compact = false }) {
  // Stable identity: a fresh literal here re-triggers every downstream useMemo.
  // Hall 1 front-apron GPS, mirrors FIRE_HALLS["1"] / STATIONS[0].
  const origin = useMemo(() => stationHall || {
    id: '1',
    lat: 49.29109654571679,
    lng: -122.79072561861948,
    name: 'Hall 1 (1300 Pinetree Way)'
  }, [stationHall]);

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
  // Stable identity: a fresh object every render re-ran every effect that lists it.
  const destination = useMemo(() => (hasValidCoords ? { lat: destLat, lng: destLng } : null), [hasValidCoords, destLat, destLng]);

  // All severities, active now. No filter controls on the dispatch map by design.
  const { activeClosures } = useRoadClosures({
    filterNoAccess: true, filterAccessOnly: true, filterCaution: true,
    showActiveNow: true, showNext24h: false, showNext7d: false,
  });

  const [userPanned, setUserPanned] = useState(false);
  const [mapInstance, setMapInstance] = useState(null);
  // Open on the hall display; closed to its header on a phone, where the box spans the
  // top of a map that is already only half the screen.
  const [isPanelOpen, setIsPanelOpen] = useState(() => !compact);
  // 'route': the whole run from the hall; 'call': the final approach, close in, with the
  // parcel and the picked hydrants. One button flips between them (operator, 2026-09-08).
  const [viewMode, setViewMode] = useState('route');
  const fittingRef = useRef(false);
  const panelRef = useRef(null);
  // The route as drawn, reported by RoutingOverlay; the hydrant picker measures along it.
  const [routeCoords, setRouteCoords] = useState([]);
  const [mapZoom, setMapZoom] = useState(13);

  // Reset view state when the active call changes.
  //
  // Adjusted during render rather than in an effect: React's documented pattern for
  // "reset state when a prop changes". An effect would paint the previous call's pan
  // state for one frame, then re-render -- a visible flicker on the apparatus bay
  // display at the exact moment a new dispatch lands.
  const [prevCallKey, setPrevCallKey] = useState(callKey);
  if (callKey !== prevCallKey) {
    setPrevCallKey(callKey);
    setUserPanned(false);
    setSelectedCandidateIdx(0);
    setRouteCoords([]);
    setViewMode('route');
  }

  // The hydrants a driver should see, by the operator's rule (utils/routeHydrants.js):
  // along the route within 300 ft of arrival first, then around the address, then within
  // the 1,000 ft supply lay, else a warning. Punch-list #74.
  const routeHydrants = useRouteHydrants(destLat, destLng, routeCoords);

  // The parcel outline for the map, [lat, lng] rings from the call's [lng, lat] rings.
  const parcelRings = useMemo(() => {
    const rings = activeCall?.rings?.length ? activeCall.rings : activeCall?.target?.rings;
    if (!Array.isArray(rings) || rings.length === 0) return null;
    const asLatLng = Array.isArray(rings[0]?.[0])
      ? rings.map(ring => ring.map(([lng, lat]) => [lat, lng]))
      : [rings.map(([lng, lat]) => [lat, lng])];
    return asLatLng;
  }, [activeCall]);
  const hydrantHighlightIds = useMemo(() => new Set(routeHydrants.picks.map(h => h.gisId)), [routeHydrants]);

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
  const persistedUnitMetrics = useMemo(
    () => activeCall?.routing_metrics || activeCall?.target?.routing_metrics || [],
    [activeCall]
  );

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
    setViewMode('route');
    if (mapInstance) {
      markFitting(mapInstance, fittingRef);
      if (hasValidCoords && destination) {
        const bounds = L.latLngBounds(
          [origin.lat, origin.lng],
          [destination.lat, destination.lng]
        );
        mapInstance.fitBounds(bounds, routeFitOptions(mapInstance, {
          panelEl: panelRef.current, panelSide: compact ? 'top' : 'left', maxZoom: 17, animate: true,
        }));
      } else {
        mapInstance.setView([origin.lat, origin.lng], 13, { animate: true });
      }
    }
  };

  // Snap to the call: the parcel and the picked hydrants, close in, so the final approach
  // reads at a glance. The bounds are the destination plus every pick, so a hydrant 300 m
  // back on the approach is still on screen; with no picks it is the destination at zoom 18.
  // Capped at 18: the deepest zoom the street tiles were crawled to, and the cadastral and
  // hydrant layers both draw there. The details box's width pads the left edge, as the
  // route fit does, so the parcel is never under it.
  const snapToCall = () => {
    if (!mapInstance || !hasValidCoords || !destination) return;
    setUserPanned(false);
    setViewMode('call');
    markFitting(mapInstance, fittingRef);
    const points = [[destination.lat, destination.lng]];
    for (const h of routeHydrants.picks) {
      if (h.lat != null && h.lng != null) points.push([Number(h.lat), Number(h.lng)]);
    }
    // Instant, not animated: a snap is a cut, and an animated four-level zoom sits at
    // Leaflet's animation threshold and is scheduled on requestAnimationFrame, which is
    // where it can fail to start (measured on the workstation, 2026-09-08).
    if (points.length === 1) {
      mapInstance.setView(points[0], 18, { animate: false });
    } else {
      mapInstance.fitBounds(L.latLngBounds(points), snapFitOptions(mapInstance, {
        panelEl: panelRef.current, panelSide: compact ? 'top' : 'left', maxZoom: 18, animate: false,
      }));
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

      {/* Street section: resolved to a stretch of road, not a point. A third state --
          neither a located incident nor an unresolved one -- so it gets its own card. */}
      {activeCall?.location_type === 'street_section' && (
        <div className={`absolute inset-x-4 ${compact ? 'top-32' : 'top-20'} z-[1000] mx-auto max-w-lg`}>
          <StreetSectionBanner activeCall={activeCall} />
        </div>
      )}

      {/* Amber warning for a location the geocoder could only place approximately.
          Distinct from the unresolved case below: coordinates exist and routing runs,
          but the pin is a substitution and the crew must be told so. */}
      {hasValidCoords && activeCall?.resolution_note && (
        <div className={`absolute inset-x-4 ${compact ? 'top-32' : 'top-20'} z-[1000] mx-auto max-w-lg`}>
          <ApproximateLocationBanner activeCall={activeCall} />
        </div>
      )}

      {/* High-Visibility Amber Warning Box for Unresolved Incident Location */}
      {!hasValidCoords && (
        <div className={`absolute inset-x-4 ${compact ? 'top-32' : 'top-20'} z-[1000] mx-auto max-w-lg bg-amber-950/95 border-2 border-amber-500 text-amber-200 p-4 rounded-2xl shadow-2xl backdrop-blur-md flex items-center gap-3 motion-safe:animate-pulse`}>
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
      <div ref={panelRef} className={`absolute z-[1000] bg-slate-950/90 backdrop-blur-md border border-slate-800 rounded-2xl shadow-2xl overflow-hidden transition-all duration-300 ${compact ? 'top-14 inset-x-2' : 'top-3 left-3 w-72 sm:w-80'}`}>
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
          <div className={`p-3 flex flex-col gap-2.5 animate-in fade-in duration-200 ${compact ? 'max-h-[36dvh] overflow-y-auto' : ''}`}>
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
                    {/* The unit's hall colour, the same as its route line; slate when the record
                        carries no metrics for it (no hall is guessed). */}
                    <span className="w-2.5 h-2.5 rounded-full flex-shrink-0 shadow-sm" title={u.hall ? `Hall ${u.hall}` : 'hall unknown'} style={{ backgroundColor: u.hall ? hallColour(u.hall) : UNASSIGNED_HALL_COLOUR }} />
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

            {/* An operator-set arrival point: say so, and why, so the crew reads the pin as a
                ruling rather than a wrong guess (punch-list #49). */}
            {(activeCall?.target?.arrival_point === 'entrance') && (
              <div className="bg-emerald-950/60 border border-emerald-700/70 p-2.5 rounded-xl text-xs font-mono text-emerald-200">
                <span className="font-black">🚒 ARRIVAL POINT SET BY OPERATOR</span>
                {activeCall?.target?.entrance_note && <span className="italic"> — {activeCall.target.entrance_note}</span>}
              </div>
            )}

            {/* Hydrant & Tactical Notes Bar.
                Previously fell back to the literal string 'City Hydrant: D-165 (42m)'.
                No dispatch has ever carried a `hydrant` field -- the backend does not emit
                one -- so that invented hydrant and distance were shown on every call
                (CLAUDE.md §6.1, punch-list #24). */}
            <div className="bg-slate-900/80 border border-slate-800 p-2.5 rounded-xl flex items-center justify-between text-xs font-mono">
              <div className="flex items-center gap-2 text-sky-400 font-bold">
                <span>💧</span>
                <span className="text-[10.5px] text-slate-200">
                  {/* From public.hydrants around the destination, by the operator's rule
                      (utils/routeHydrants.js); NFPA 291 class as rated by the City. Never
                      from the dispatch record, which carries no hydrant (#24, #74). */}
                  {!hasValidCoords ? (
                    <span className="text-slate-500 italic">Awaiting location</span>
                  ) : routeHydrants.failed ? (
                    <span className="text-red-400 italic">Hydrant lookup failed</span>
                  ) : routeHydrants.loading ? (
                    <span className="text-slate-500 italic">Hydrant inventory loading…</span>
                  ) : routeHydrants.tier === TIER.NONE ? (
                    <span className="text-amber-300 font-black">⚠️ NO HYDRANT WITHIN 1,000 FT</span>
                  ) : (
                    <span className="flex flex-col gap-0.5">
                      {routeHydrants.picks.map((h, i) => (
                        <span key={h.gisId}>
                          <span className="text-slate-500">{i + 1}. </span>
                          <span className="text-white font-black">{h.gisId}</span>
                          <span className="text-sky-300"> {h.flowClass || 'UNRATED'}</span>
                          {String(h.status || '').toUpperCase() === 'PRIVATE' && <span className="text-amber-400"> PRIVATE</span>}
                          <span className="text-slate-400">
                            {h.how === TIER.DOORSTEP
                              ? ` · ${h.distance} m from the address, within a 50 ft roll`
                              : h.how === TIER.APPROACH
                              ? ` · ${h.distance} m before arrival, on the route${h.longLay ? ' — LONG LAY (500 ft+): relay, or the closer one' : ''}`
                              : h.closerAlternative
                                ? ` · ${h.distance} m from the address, off route: the closer option`
                                : h.how === TIER.NEAR
                                ? ` · ${h.distance} m from the address${i === 0 ? (routeHydrants.routeKnown ? ', none on the approach within 1,000 ft' : ', route pending') : ''}`
                                : ` · ${h.distance} m, within the 1,000 ft supply lay; none within 300 ft`}
                          </span>
                        </span>
                      ))}
                    </span>
                  )}
                </span>
              </div>
              <span className="text-[9px] text-slate-400 uppercase font-bold bg-slate-800 px-1.5 py-0.5 rounded">
                NFPA 291
              </span>
            </div>
          </div>
        )}
      </div>

      {/* One button, two states: SNAP TO CALL brings the final approach in close; RESET VIEW
          returns to the whole route. Always shown while the call has a location
          (operator, 2026-09-08: "it can flip back and forth"). */}
      {hasValidCoords && (
        <button
          onClick={viewMode === 'call' ? handleRecenter : snapToCall}
          title={viewMode === 'call' ? 'Back to the whole route from the hall' : 'Close in on the parcel and the picked hydrants'}
          className={`absolute top-3 ${compact ? 'right-3' : 'right-14'} z-[1000] font-mono text-xs font-black px-3.5 py-2 touch:py-2.5 rounded-xl shadow-xl border flex items-center gap-1.5 cursor-pointer ${
            viewMode === 'call'
              ? 'bg-slate-900/95 hover:bg-slate-800 text-sky-300 border-sky-700'
              : 'bg-amber-500 hover:bg-amber-400 text-slate-950 border-amber-300'
          }`}
        >
          <span>{viewMode === 'call' ? '🗺️' : '🎯'}</span>
          <span>{viewMode === 'call' ? 'RESET VIEW' : 'SNAP TO CALL'}</span>
        </button>
      )}

      {/* Floating Re-Center Button when the user pans or zooms away from the route */}
      {userPanned && viewMode === 'route' && (
        <button
          onClick={handleRecenter}
          className={`absolute ${compact ? 'top-3 left-3' : 'top-14 right-14'} z-[1000] bg-sky-600 hover:bg-sky-500 text-white font-mono text-xs font-black px-3.5 py-2 touch:py-2.5 rounded-xl shadow-xl border border-sky-400 flex items-center gap-1.5 cursor-pointer motion-safe:animate-pulse`}
        >
          <span>🎯</span>
          <span>RE-CENTER ROUTE</span>
        </button>
      )}

      <MapSurface
        center={hasValidCoords ? [destLat, destLng] : [origin.lat, origin.lng]}
        zoom={13}
        className="w-full h-full z-0"
        mapRef={setMapInstance}
        zoomControl
        baseStyle="STREET"
        streetLabels
        showCadastral
        showFireHalls
        // Every hydrant, but only once the map is zoomed in to neighbourhood scale: with no
        // target passed, the layer draws from zoom 16 (operator, 2026-09-07: "show ALL the
        // hydrants on the main route map, but only at a certain close in zoom"). At the
        // route's own zoom only the numbered picks show. The picks are also handed to the
        // layer so it pulses them rather than its own nearest.
        showHydrants
        hydrantHighlightIds={hydrantHighlightIds}
      >
        <MapInteractivity onPan={() => setUserPanned(true)} fittingRef={fittingRef} />
        <ZoomWatcher onZoom={setMapZoom} />

        {/* The parcel outline, soft blue, as the workstation draws it: rings of [lng, lat]
            from the resolver (operator, 2026-09-08: "the target parcel had a soft blue
            shading"). No rings, no outline -- a junction or a withheld location draws none. */}
        {parcelRings && mapZoom >= CADASTRAL_MIN_ZOOM && (
          <Polygon
            positions={parcelRings}
            pathOptions={{ color: '#0284c7', fillColor: '#38bdf8', fillOpacity: 0.15, weight: 2, dashArray: '4,4' }}
            interactive={false}
          />
        )}

        {/* The recommended hydrants as numbered badges, at every zoom (#74). */}
        <PickedHydrantsLayer picks={routeHydrants.picks} />

        {/* Road closures. A closure matters most when apparatus is being routed through
            it, so the dispatch map shows them too -- they were previously standby-only.
            All severities and the active-now window; the console's filter controls are
            deliberately not reproduced here, because a driver should not be able to hide
            a closure. Highlighting the ones that actually intersect the route is the next
            step and is tracked separately. */}
        <RoadClosuresLayer
          closures={activeClosures}
          visible
          selectedClosure={null}
          onSelect={() => {}}
        />

        {/* Every responding hall's route, the home hall's on top and solid; only the home
            route reports its coordinates, for the hydrant picker and the fit. */}
        {hasValidCoords && (
          <HallRoutesOverlay
            dest={[destLat, destLng]}
            homeHall={origin.id || '1'}
            routingMetrics={persistedUnitMetrics}
            onHomeRouteCalculated={setRouteCoords}
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
                  icon={isSelected ? targetPinIcon : altCandidatePinIcon}
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
            <Marker position={[destLat, destLng]} icon={targetPinIcon}>
              <Popup>Target Destination: {activeCall?.address || 'Incident Location'}</Popup>
            </Marker>
          )
        )}

        {hasValidCoords && (
          <AutoFitBounds
            origin={origin}
            destination={destination}
            callKey={`${callKey}-${selectedCandidateIdx}`}
            fittingRef={fittingRef}
            panelRef={panelRef}
            compact={compact}
          />
        )}
      </MapSurface>
    </div>
  );
}

