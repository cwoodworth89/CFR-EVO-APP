/**
 * The arrival point applied to the call on screen (punch list #94).
 *
 * A saved arrival point already governs every later call to the address: the resolver picks
 * the destination as entrance -> computed frontage -> centroid
 * (services/gis/src/gis_service/address_resolver.py, `dest_lat = entrance or front or
 * centroid`). Operator, 2026-09-17, 1145 Heffley Cres: setting one from a review replay and
 * closing the editor "the route jumps back", with the pin never having moved. Read as a bug:
 * the save should apply to the call on screen now, not only to the next one.
 *
 * So the call on screen takes the destination the resolver would give the NEXT call, from the
 * parcel row the save returned -- the same precedence, not a second rule. That also settles a
 * cleared arrival point without a new choice: with no entrance the resolver falls back to the
 * computed frontage, and so does the screen.
 *
 * Pure, so the transition is tested (tests/arrivalTarget.test.mjs). Nothing here writes the
 * dispatch record; it is the on-screen call only.
 */

const isCoord = (lat, lng) => {
  const a = Number(lat);
  const b = Number(lng);
  return lat != null && lng != null && Number.isFinite(a) && Number.isFinite(b) && !(a === 0 && b === 0);
};

/**
 * The destination the resolver would pick for this parcel row (serialize_parcel shape:
 * entrance_lat/lng, front_lat/lng, and lat/lng as the centroid), or null when the row has
 * none of the three.
 */
export function resolverTargetFromParcel(parcel) {
  if (!parcel) return null;
  if (isCoord(parcel.entrance_lat, parcel.entrance_lng)) {
    return {
      lat: Number(parcel.entrance_lat), lng: Number(parcel.entrance_lng),
      arrival_point: 'entrance', entrance_note: parcel.entrance_note || null,
    };
  }
  if (isCoord(parcel.front_lat, parcel.front_lng)) {
    return { lat: Number(parcel.front_lat), lng: Number(parcel.front_lng), arrival_point: 'front', entrance_note: null };
  }
  if (isCoord(parcel.lat, parcel.lng)) {
    return { lat: Number(parcel.lat), lng: Number(parcel.lng), arrival_point: 'centroid', entrance_note: null };
  }
  return null;
}

/**
 * The call with its destination moved to `target`: `lat`/`lng` and the same fields on `target`,
 * which is where every panel reads them. Everything else -- address, units, the recorded
 * routing_metrics -- is left as recorded. Returns the call unchanged when there is no target,
 * or when the call is an ambiguous junction (its candidates are the choice there, and an
 * arrival point belongs to a parcel).
 */
export function applyArrivalToCall(call, target) {
  if (!call || !target || !isCoord(target.lat, target.lng)) return call;
  const candidates = call.candidates ?? call.target?.candidates;
  if (Array.isArray(candidates) && candidates.length > 1) return call;
  // Already there (a call recorded at the point the resolver still gives): the same call, so
  // nothing downstream reads it as moved -- the header keeps the recorded ETAs.
  const recLat = call.lat ?? call.target?.lat;
  const recLng = call.lng ?? call.target?.lng;
  if (isCoord(recLat, recLng) && Number(recLat) === target.lat && Number(recLng) === target.lng
      && (call.target?.arrival_point ?? null) === target.arrival_point) {
    return call;
  }
  return {
    ...call,
    lat: target.lat,
    lng: target.lng,
    target: {
      ...(call.target || {}),
      lat: target.lat,
      lng: target.lng,
      arrival_point: target.arrival_point,
      entrance_note: target.entrance_note,
    },
  };
}

/** The key a route result is tagged with: the destination it was computed to. */
export const destinationKey = (lat, lng) => (lat == null || lng == null ? '' : `${Number(lat)},${Number(lng)}`);

/**
 * The header's unit ETAs for a call whose destination has been moved on screen (#94). Operator,
 * 2026-09-17: "Update the ETA. This is informational and not statistical. Run time truths are
 * stored in the CAD software using truck GPS."
 *
 * Each unit keeps its recorded hall (routing_metrics origin_hall); its ETA and road distance are
 * the router's live answer from that hall to the moved destination (`/api/route`, the same
 * eta_minutes and distance_km the route pill shows -- CLAUDE.md 6.2, nothing derived). Unknown
 * until that hall's route answers, and unknown for good if the answer is degraded (no router:
 * great-circle distance, no ETA) or never comes. The recorded figure for the old point is never
 * shown for the new one.
 *
 * `hallStats`: { [hallId]: { etaMinutes, distanceKm, degraded } } for the moved destination only.
 */
export function unitEtasForMovedCall(persistedMetrics, hallStats) {
  if (!Array.isArray(persistedMetrics)) return [];
  const stats = hallStats || {};
  return persistedMetrics.map((m) => {
    const hallId = m?.origin_hall != null ? String(m.origin_hall) : null;
    const live = hallId != null ? stats[hallId] : null;
    const usable = live && !live.degraded;
    return {
      unit: m?.unit,
      hallId,
      etaMin: usable && live.etaMinutes != null ? live.etaMinutes : null,
      distKm: usable && live.distanceKm != null ? live.distanceKm : null,
    };
  });
}

const normalAddress = (s) => String(s || '').replace(/\s+/g, ' ').trim().toUpperCase();

/**
 * The target the call on screen takes, derived every time the call is shown -- nothing held
 * in session (#94). Operator, 2026-09-17: the pin goes wherever the route goes, and "we lost
 * our marker placement again" after replaying another call and coming back. The stored point
 * lived in KioskView state, which unmounts when a replay ends (App.jsx mode switch), while
 * the route read the parcel's entrance fresh each time; the two parted on return.
 *
 * The rule: the resolver's answer for this address NOW, from the parcel row the arrival panel
 * already looks up (resolverTargetFromParcel), applied at load, after a save, after a clear.
 * Three guards, each so a pin is never moved onto something that is not this call's property:
 *   * the parcel row's address must be the call's own lookup address -- the read lookup falls
 *     back to a partial ILIKE match (api/routers/parcels.py _address_row), and 40 rows match
 *     "%1145 Heffley%";
 *   * the call must have been placed on a parcel (a recorded arrival_point, or parcel rings) --
 *     a junction, block or street section keeps its own point;
 *   * the row must give a point (resolverTargetFromParcel non-null).
 * Null when any guard fails: the call shows as recorded.
 */
export function onScreenArrivalTarget(call, parcel, lookupAddress) {
  if (!call || !parcel) return null;
  const key = normalAddress(lookupAddress);
  if (!key || normalAddress(parcel.address) !== key) return null;
  const t = call.target || {};
  const rings = t.rings ?? call.rings;
  const placedOnParcel = ['entrance', 'front', 'centroid'].includes(t.arrival_point)
    || (Array.isArray(rings) && rings.length > 0);
  if (!placedOnParcel) return null;
  return resolverTargetFromParcel(parcel);
}
