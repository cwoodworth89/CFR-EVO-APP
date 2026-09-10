import React, { useEffect, useState, useRef, useMemo, useCallback } from 'react';
import { Marker, Popup, Polygon, Polyline, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import { altCandidatePinIcon, targetPinIcon } from '../map/mapIcons';
import HallRoutesOverlay from '../map/HallRoutesOverlay';
import MapSurface from '../map/MapSurface';
import RoadClosuresLayer from '../map/RoadClosuresLayer';
import { useRoadClosures } from '../../hooks/useRoadClosures';
import { BASE_LAYERS, CADASTRAL_MIN_ZOOM } from '../MapConstants';
import { useRouteHydrants } from '../../hooks/useRouteHydrants';
import PickedHydrantsLayer from '../map/PickedHydrantsLayer';
import { hydrantCardModel } from '../../utils/hydrantCard';
import { routeFitOptions, snapFitOptions } from '../map/fitPadding';

// The chrome over the map (artboard 3A of the operator's Claude Design canvas): the route
// pill top left, the control stack top right in one fixed order, the hydrant card bottom
// left. Each sits Tailwind's spacing-3 (12 px) in from the map's edge; the fits measure the
// stack and the card and add this inset, so the route is never under either.
const OVERLAY_INSET_PX = 12;
const CONTROL = 'bg-slate-950 border border-slate-700 hover:border-slate-500 rounded-lg px-4 py-3 lg:px-5 lg:py-3.5 touch:py-4 font-mono font-extrabold text-xs lg:text-sm tracking-[0.1em] uppercase shadow-lg transition whitespace-nowrap';
const ZOOM_BTN = 'w-12 h-12 xl:w-14 xl:h-14 bg-slate-950 border border-slate-700 hover:border-slate-500 rounded-lg text-slate-50 font-sans text-2xl leading-none shadow-lg cursor-pointer';

/** The route pill's text: OSRM's figures for the drawn home route, or the unknown marks. */
function routePillText(summary) {
  if (!summary) return 'ROUTE · -- KM · -- MIN';
  const km = summary.distanceKm != null ? `${Number(summary.distanceKm).toFixed(1)} KM` : '-- KM';
  const min = summary.etaMinutes != null ? `${Math.round(Number(summary.etaMinutes))} MIN` : '-- MIN';
  // A degraded answer is a straight-line distance with no router behind it: say so
  // (docs/ux_notes.md section 4, "straight-line on a distance that is one").
  return `${summary.degraded ? 'STRAIGHT-LINE' : 'ROUTE'} · ${km} · ${min}`;
}

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
function AutoFitBounds({ origin, destination, callKey, fittingRef, getOverlays }) {
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

    // Padding measured from the container and what floats over it (map/fitPadding.js): the
    // control stack at the right and the hydrant card at the bottom, so the destination pin
    // is never under either (operator, 2026-09-06: "it covers up the destination").
    markFitting(map, fittingRef);
    map.fitBounds(bounds, routeFitOptions(map, { overlays: getOverlays?.(), maxZoom: 17, animate: true }));
  }, [map, origin, destination, callKey, fittingRef, getOverlays]);

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

export default function RouteOverviewPanel({ activeCall, stationHall, compact = false, onHydrantModel = null, snapRequest = 0 }) {
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
  // 'route': the whole run from the hall; 'call': the final approach, close in, with the
  // parcel and the picked hydrants (operator, 2026-09-08). SNAP TO CALL and RE-CENTRE sit
  // in the control stack; RE-CENTRE is live only once the view has left the route.
  const [viewMode, setViewMode] = useState('route');
  const fittingRef = useRef(false);
  // What floats over the map, measured for the fits: the control stack (right) and the
  // hydrant card (bottom). Nothing is written as a literal (map/fitPadding.js).
  const controlsRef = useRef(null);
  const getOverlays = useCallback(() => ({
    right: controlsRef.current ? controlsRef.current.offsetWidth + OVERLAY_INSET_PX : 0,
  }), []);
  // The route as drawn, reported by RoutingOverlay; the hydrant picker measures along it.
  const [routeCoords, setRouteCoords] = useState([]);
  // OSRM's distance and duration for that drawn route, for the pill (CLAUDE.md s6.2).
  const [routeSummary, setRouteSummary] = useState(null);
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
    setRouteSummary(null);
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

  // The persisted OSRM routing_metrics name the responding halls, one route line each. The
  // per-unit ETAs they carry are read by the header (ActiveAlertBanner), not here.
  const persistedUnitMetrics = useMemo(
    () => activeCall?.routing_metrics || activeCall?.target?.routing_metrics || [],
    [activeCall]
  );

  // The hydrant card's words, from the picker's answer (utils/hydrantCard.js).
  const hydrantModel = useMemo(
    () => hydrantCardModel({ hasCoords: hasValidCoords, hydrants: routeHydrants }),
    [hasValidCoords, routeHydrants]
  );

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
        mapInstance.fitBounds(bounds, routeFitOptions(mapInstance, { overlays: getOverlays(), maxZoom: 17, animate: true }));
      } else {
        mapInstance.setView([origin.lat, origin.lng], 13, { animate: true });
      }
    }
  };

  // Snap to the call: the parcel and the picked hydrants, close in, so the final approach
  // reads at a glance. The bounds are the destination plus every pick, so a hydrant 300 m
  // back on the approach is still on screen; with no picks it is the destination at zoom 18.
  // Capped at 18: the deepest zoom the street tiles were crawled to, and the cadastral and
  // hydrant layers both draw there. The control stack and the hydrant card pad their edges,
  // as the route fit does, so the parcel is never under either.
  const snapToCall = () => {
    if (!mapInstance || !hasValidCoords || !destination) return;
    setUserPanned(false);
    setViewMode('call');
    markFitting(mapInstance, fittingRef);
    const points = [[destination.lat, destination.lng]];
    for (const h of routeHydrants.picks) {
      if (h.lat != null && h.lng != null) points.push([Number(h.lat), Number(h.lng)]);
    }
    // An announced block or a street section: the whole named stretch is the thing to
    // see, not just the pin at its middle (#76).
    if (Array.isArray(activeCall?.segment)) {
      for (const line of activeCall.segment) {
        for (const pt of line) {
          if (Array.isArray(pt) && pt.length >= 2) points.push([Number(pt[1]), Number(pt[0])]);
        }
      }
    }
    // Instant, not animated: a snap is a cut, and an animated four-level zoom sits at
    // Leaflet's animation threshold and is scheduled on requestAnimationFrame, which is
    // where it can fail to start (measured on the workstation, 2026-09-08).
    if (points.length === 1) {
      mapInstance.setView(points[0], 18, { animate: false });
    } else {
      mapInstance.fitBounds(L.latLngBounds(points), snapFitOptions(mapInstance, { overlays: getOverlays(), maxZoom: 18, animate: false }));
    }
  };

  // RE-CENTRE has something to do once the view has left the route: a drag, a wheel, or a snap.
  const offRoute = userPanned || viewMode === 'call';

  // The hydrant card lives in the header now (operator, 2026-09-10), but the picks are
  // measured here, along the route this map drew, so the model goes up. TAP TO ZOOM comes
  // back down as a handle on this panel's own SNAP TO CALL: the header needs no map of its
  // own, and the pin can no longer be covered by a card that is not over the map.
  useEffect(() => {
    if (onHydrantModel) onHydrantModel(hydrantModel);
  }, [hydrantModel, onHydrantModel]);

  // TAP TO ZOOM on the header's hydrant card asks this map to snap. A counter rather than a
  // handle passed upward: writing a function into a prop ref is the crash-lint's
  // react-hooks/immutability rule, and a counter says "asked again" without one.
  const lastSnapRequest = useRef(snapRequest);
  useEffect(() => {
    if (snapRequest === lastSnapRequest.current) return;
    lastSnapRequest.current = snapRequest;
    if (hasValidCoords) snapToCall();
  });


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

      {/* The three amber cards that used to float here -- street section, approximate
          location, unresolved location -- are banners above the header now (KioskView).
          The unresolved one repeated the banner already at the top of the screen, and all
          three sat over the route: "there is also a floating/pulsing amber banner that's
          been popping up in the main map board ... we can remove that since we're using the
          above header banners" (operator, 2026-09-10). Nothing floats over this map now
          except the route pill and the control stack, both in its top corners. */}

      {/* The route pill: OSRM's distance and duration for the drawn home route, the router's
          own figures and never a recomputation (CLAUDE.md s6.2). Until the route arrives, or
          when the record has no location, the marks say so. */}
      <div className="absolute top-3 left-3 z-[1000] pointer-events-none select-none bg-slate-950 border border-slate-800 rounded-md px-3 py-2 font-mono font-bold text-[11px] lg:text-xs tracking-[0.1em] uppercase text-slate-50 shadow-lg">
        {hasValidCoords ? routePillText(routeSummary) : 'ROUTE · AWAITING LOCATION'}
      </div>

      {/* The control stack, top right, the console's mirrored (artboard 3A): the zoom readout,
          SNAP TO CALL, RE-CENTRE, and the zoom buttons, in one fixed order so each is in the
          same place at 03:00. RE-CENTRE is dim until a drag, a wheel or a snap has moved the
          view off the route (operator, 2026-09-06: it used to shout on every call). On a phone
          the readout and the zoom buttons go: pinch does that. */}
      {hasValidCoords && (
        <div ref={controlsRef} className="absolute top-3 right-3 z-[1000] flex flex-col items-end gap-2">
          {!compact && (
            <div className="pointer-events-none select-none flex items-center gap-2 bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5">
              <span className="font-mono font-bold text-[10px] tracking-[0.14em] text-slate-400">ZOOM</span>
              <span className="font-mono font-extrabold text-xs text-amber-400">{Number(mapZoom).toFixed(1)}</span>
            </div>
          )}
          <button
            type="button"
            onClick={snapToCall}
            title="Close in on the parcel and the picked hydrants"
            className={`${CONTROL} cursor-pointer ${viewMode === 'call' ? 'text-slate-400' : 'text-slate-50'}`}
          >
            Snap to call
          </button>
          <button
            type="button"
            onClick={handleRecenter}
            disabled={!offRoute}
            aria-disabled={!offRoute}
            title="Back to the whole route from the hall"
            className={`${CONTROL} ${offRoute ? 'text-slate-50 cursor-pointer' : 'text-slate-500 cursor-default'}`}
          >
            Re-centre
          </button>
          {!compact && (
            <div className="flex flex-col gap-2 mt-1">
              <button type="button" aria-label="Zoom in" onClick={() => mapInstance?.zoomIn()} className={ZOOM_BTN}>+</button>
              <button type="button" aria-label="Zoom out" onClick={() => mapInstance?.zoomOut()} className={ZOOM_BTN}>−</button>
            </div>
          )}
        </div>
      )}

      <MapSurface
        center={hasValidCoords ? [destLat, destLng] : [origin.lat, origin.lng]}
        zoom={13}
        className="w-full h-full z-0"
        mapRef={setMapInstance}
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

        {/* An announced block (#76) or a street section: the stretch of road the dispatcher
            named, amber and dashed as the workstation draws it, so the pin at its middle
            reads as "somewhere along here" rather than as an address. */}
        {(activeCall?.location_type === 'block' || activeCall?.location_type === 'street_section')
          && Array.isArray(activeCall.segment)
          && activeCall.segment.map((line, i) => (
            <Polyline
              key={`announced-stretch-${i}`}
              positions={line.map(([lng, lat]) => [lat, lng])}
              pathOptions={{ color: '#f59e0b', weight: 10, opacity: 0.75, dashArray: '14,10', lineCap: 'round' }}
              interactive={false}
            />
          ))}

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
            onHomeRouteCalculated={(coords, summary) => { setRouteCoords(coords); setRouteSummary(summary || null); }}
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
            getOverlays={getOverlays}
          />
        )}
      </MapSurface>
    </div>
  );
}

