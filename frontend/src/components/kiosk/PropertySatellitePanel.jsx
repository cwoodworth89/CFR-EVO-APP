import React, { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Polygon, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { targetPinIcon } from '../map/mapIcons';
import { BASE_LAYERS } from '../MapConstants';
import { API_BASE_URL } from '../../apiClient';
import TileFrame from './TileFrame';

function StableAutoCenterAndResize({ lat, lng, polygonPositions, callKey }) {
  const map = useMap();
  const lastKeyRef = useRef(null);

  // Auto-fit property bounds and zoom out 1 step for full surrounding context
  useEffect(() => {
    if (!map || lat == null || lng == null) return;
    const currentKey = callKey || `${lat.toFixed(5)},${lng.toFixed(5)}`;
    if (lastKeyRef.current !== currentKey) {
      lastKeyRef.current = currentKey;

      if (polygonPositions && polygonPositions.length > 0) {
        try {
          const poly = L.polygon(polygonPositions);
          const bounds = poly.getBounds();
          if (bounds.isValid()) {
            map.fitBounds(bounds, { padding: [45, 45], maxZoom: 17.5, animate: false });
            const fitZoom = map.getZoom();
            // Zoom out 1 step from fitted bounds so full parcel and surrounding roads are visible
            map.setZoom(Math.max(fitZoom - 1, 15.5), { animate: false });
            return;
          }
        } catch (e) {
          console.warn('Failed to fit parcel bounds:', e);
        }
      }

      // Default fallback zoom level (16.5 instead of 18)
      map.setView([lat, lng], 16.5, { animate: false });
    }
  }, [map, lat, lng, polygonPositions, callKey]);

  useEffect(() => {
    if (!map) return;
    const timer = setTimeout(() => {
      map.invalidateSize();
    }, 200);
    return () => clearTimeout(timer);
  }, [map]);

  return null;
}

/** A tile state that is words, not a picture: the same frame, a centred message. */
function TileMessage({ tone, title, body }) {
  const colour = tone === 'amber' ? 'text-amber-400' : 'text-slate-200';
  return (
    <div className="w-full h-full flex flex-col items-center justify-center p-6 text-center">
      <h4 className={`text-sm font-black uppercase tracking-wider font-mono ${colour}`}>{title}</h4>
      <p className="text-xs text-slate-400 font-mono mt-1 max-w-xs leading-relaxed">{body}</p>
    </div>
  );
}

/**
 * The aerial tile: the City's orthophoto with the parcel outlined (artboard 3A, "AERIAL").
 * The tile is the picture; the expanded view carries the zoom control.
 */
export default function PropertySatellitePanel({ activeCall }) {
  const [isExpanded, setIsExpanded] = useState(false);

  const rawDestLat = activeCall?.lat ?? activeCall?.target?.lat ?? null;
  const rawDestLng = activeCall?.lng ?? activeCall?.target?.lng ?? null;

  const hasCoords = rawDestLat != null && rawDestLng != null &&
    !isNaN(Number(rawDestLat)) && !isNaN(Number(rawDestLng)) &&
    (Number(rawDestLat) !== 0 || Number(rawDestLng) !== 0);

  const destLat = hasCoords ? Number(rawDestLat) : null;
  const destLng = hasCoords ? Number(rawDestLng) : null;

  // Inside the City is public.city_boundary's answer, asked of the API (punch-list #87,
  // operator ruling 2026-09-15). There is no box and no client-side guess: `null` while the
  // answer is pending or unknown, and an unknown renders as unknown, never as in or out.
  const [cityCheck, setCityCheck] = useState({ key: null, within: null, settled: false });
  const coordKey = hasCoords ? `${destLat},${destLng}` : null;
  useEffect(() => {
    if (coordKey == null) return undefined;
    const controller = new AbortController();
    const params = new URLSearchParams({ lat: String(destLat), lng: String(destLng) });
    fetch(`${API_BASE_URL}/api/parcels/within-city?${params}`, { signal: controller.signal })
      .then((res) => (res.ok ? res.json() : { within_city: null }))
      .then((body) => {
        const within = typeof body?.within_city === 'boolean' ? body.within_city : null;
        setCityCheck({ key: coordKey, within, settled: true });
      })
      .catch((err) => {
        if (err?.name !== 'AbortError') setCityCheck({ key: coordKey, within: null, settled: true });
      });
    return () => controller.abort();
  }, [coordKey, destLat, destLng]);
  const cityAnswer = cityCheck.key === coordKey ? cityCheck : { within: null, settled: false };

  const callKey = activeCall?.id ? String(activeCall.id) : (activeCall?.address || (hasCoords ? `${destLat},${destLng}` : 'satellite-panel'));

  const polygonPositions = activeCall?.rings && activeCall.rings.length > 0
    ? (Array.isArray(activeCall.rings[0][0])
        ? activeCall.rings.map(ring => ring.map(([lng, lat]) => [lat, lng]))
        : [activeCall.rings.map(([lng, lat]) => [lat, lng])])
    : null;

  // Tier 1 Error State: Location Unresolved (CLAUDE.md s5)
  if (!hasCoords) {
    return (
      <TileFrame label="Aerial">
        <TileMessage tone="amber" title="Location unresolved" body="Coordinates awaiting operator verification." />
      </TileFrame>
    );
  }

  // Waiting on the boundary answer: the empty frame, so neither card nor picture flashes.
  if (!cityAnswer.settled) {
    return <TileFrame label="Aerial" />;
  }

  // The boundary answer is unknown (API or database unreachable): say so. Not Tier 1, whose
  // wording says the coordinates are unverified when they are not; not Tier 2, which would
  // call the place outside the City (CLAUDE.md s6.1).
  if (cityAnswer.within === null) {
    return (
      <TileFrame label="Aerial">
        <TileMessage tone="amber" title="City boundary check unavailable" body="Cannot confirm this location is inside the City of Coquitlam." />
      </TileFrame>
    );
  }

  // Tier 2 Error State: Not Available Outside of City (public.city_boundary said no)
  if (cityAnswer.within === false) {
    return (
      <TileFrame label="Aerial">
        <TileMessage tone="slate" title="Not available outside of city" body="7.5cm orthophotos and cadastral parcels cover the City of Coquitlam only." />
      </TileFrame>
    );
  }

  const renderMapContent = (isModal) => (
    <MapContainer
      center={[destLat, destLng]}
      zoom={16.5}
      maxZoom={BASE_LAYERS.SATELLITE.maxZoom}
      className="w-full h-full z-0"
      zoomControl={isModal}
      attributionControl={false}
    >
      {/* City of Coquitlam 7.5cm orthophoto, via the single BASE_LAYERS
          definition. This panel is where crews read rooflines and driveways, so
          it must not drift from the main map's imagery source. */}
      <TileLayer
        url={BASE_LAYERS.SATELLITE.url}
        maxNativeZoom={BASE_LAYERS.SATELLITE.maxNativeZoom}
        maxZoom={BASE_LAYERS.SATELLITE.maxZoom}
      />

      {polygonPositions && (
        <Polygon positions={polygonPositions} pathOptions={{ color: '#fbbf24', fillColor: '#f59e0b', fillOpacity: 0.35, weight: 3 }} />
      )}

      <Marker position={[destLat, destLng]} icon={targetPinIcon}>
        <Popup>Destination: {activeCall?.address || 'Target Location'}</Popup>
      </Marker>

      <StableAutoCenterAndResize lat={destLat} lng={destLng} polygonPositions={polygonPositions} callKey={callKey} />
    </MapContainer>
  );

  return (
    <>
      <TileFrame label="Aerial" onExpand={() => setIsExpanded(true)} expandTitle="Open the full-screen aerial view">
        {renderMapContent(false)}
        <div className="absolute bottom-1.5 left-2 text-[9px] text-slate-400 font-mono bg-slate-950/80 backdrop-blur px-2 py-0.5 rounded border border-slate-800/80 z-[1000] pointer-events-none opacity-80">
          WGS84: {destLat.toFixed(5)}, {destLng.toFixed(5)}
        </div>
      </TileFrame>

      {/* Popout Full-Screen Modal */}
      {isExpanded && (
        <div className="fixed inset-0 z-[9999] bg-slate-950/95 backdrop-blur-md p-4 sm:p-8 flex flex-col animate-in fade-in duration-200">
          <div className="flex items-center justify-between mb-3 bg-slate-900 border border-slate-800 p-3 rounded-xl shadow-lg">
            <div>
              <h3 className="text-base font-bold text-white uppercase tracking-wide font-mono">Aerial · expanded</h3>
              <p className="text-xs text-amber-400 font-mono">{activeCall?.address || 'Target Property'}</p>
            </div>
            <button
              onClick={() => setIsExpanded(false)}
              className="bg-slate-50 hover:bg-white text-slate-950 font-mono font-extrabold text-xs tracking-[0.1em] uppercase px-4 py-2.5 touch:py-3 rounded-lg transition shadow cursor-pointer"
            >
              Collapse
            </button>
          </div>

          <div className="flex-1 w-full rounded-2xl overflow-hidden border-2 border-amber-500/50 shadow-2xl relative">
            {renderMapContent(true)}
          </div>
        </div>
      )}
    </>
  );
}
