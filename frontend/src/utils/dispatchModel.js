/**
 * One shape for a dispatch, derived from one database record.
 *
 * There were two. `MapBoard` worked from `activeDispatch` and a `target` object; the
 * kiosk worked from `activeCall` with the fields flattened; and `App.jsx:handleReviewCall`
 * translated by hand between them. Adding the street-section fields on 2026-08-22 meant
 * editing that translation on top of the geocoder, the payload builder and the panels — a
 * field added to a dispatch should not need copying between two representations of it.
 *
 * This module is the single translation, kept pure so it can be run over the real dispatch
 * corpus and diffed. See docs/architecture/unified_map_surface.md.
 *
 * NOTHING HERE INVENTS A VALUE. Unresolved coordinates stay `null` so the kiosk raises the
 * §5 Tier 1 card rather than routing to a guess, and every `||` fallback below chooses
 * between fields that are actually present, never a default that stands in for missing
 * data (CLAUDE.md §6.1).
 */

/** Units, preferring the operator's verified list over what the parser heard. */
export function resolveUnits(record) {
  if (!record) return [];
  const verified = record.verified_units;
  if (Array.isArray(verified) && verified.length > 0) return verified;
  const responding = record.responding_units;
  if (Array.isArray(responding) && responding.length > 0) return responding;
  return [];
}

/**
 * Normalise a database dispatch record into the shape every surface consumes.
 *
 * Accepts either a raw row or an MQTT payload wrapper (`{ rawRecord }`).
 */
export function toActiveCall(input, { apiBaseUrl = '' } = {}) {
  if (!input) return null;
  const record = input.rawRecord || input;
  const target = record.target || {};

  // Audio is stored as a server-relative path; the kiosk may be a different origin.
  let audioUrl = record.audio_url || '';
  if (audioUrl && !audioUrl.startsWith('http') && apiBaseUrl) {
    audioUrl = `${apiBaseUrl}${audioUrl.startsWith('/') ? '' : '/'}${audioUrl}`;
  }

  return {
    ...record,
    id: record.id,
    dispatch_id: record.dispatch_id,

    // Operator verification wins over the parsed value wherever it exists.
    address: record.verified_address || target.address || record.address || null,
    incident_type: record.verified_incident || record.incident_type || null,
    responding_units: resolveUnits(record),

    subaddress: target.subaddress || '',
    intersection: target.intersection || '',

    // Coordinates propagate as null when unresolved. Do not add a fallback here.
    lat: target.lat ?? record.lat ?? null,
    lng: target.lng ?? record.lng ?? null,
    rings: target.rings || record.rings || [],

    // Street-section fields. A "<street> and <street>" dispatch has no point location;
    // these drive the amber section banner and the highlighted polyline, and dropping
    // them makes the section's representative midpoint look like an exact match.
    location_type: target.location_type || null,
    segment: target.segment || null,
    endpoints: target.endpoints || null,
    length_m: target.length_m ?? null,
    street: target.street || null,
    resolution_note: target.resolution_note || null,
    // The address as dispatched, when the resolver routed somewhere else. Paired with
    // resolution_note by the substituting resolvers so the amber banner can show both
    // what was called in and where the pin actually is.
    requested_address: target.requested_address || null,

    priority_code: record.priority_code,
    // Confidence cutoff of 90 — measured on this system 2026-08-23 (CLAUDE.md §6.3 tier 3),
    // NOT a standard. It was inherited without provenance; this analysis was run to decide
    // whether to keep it, and it is RETAINED PROVISIONALLY pending more HITL reviews.
    //
    // Against 202 reviewed calls, comparing the system address to the operator's
    // verified_address after normalising suffixes, unit numbers and "(street centroid)"
    // annotations — i.e. "would the crew have reached the right address":
    //
    //   score 0     10 reviewed   100% wrong      (hard resolution failures)
    //   score 45-78 20 reviewed    60% wrong
    //   score 81-89 15 reviewed     0% wrong
    //   score 91-96  9 reviewed     0% wrong
    //   score 100   148 reviewed    8% wrong
    //
    // The break is at 80, not 90 — 81-89 was flawless on address. A cut at 90 is therefore
    // CONSERVATIVE (it flags a band that has not actually failed) rather than wrong, which is
    // the safe direction for a warning. Not moved to 80 because 81-89 has only 15 reviewed
    // calls, and because score 100 still misses 8%, so confidence is not a complete proxy for
    // geocode correctness. Tracked for revision in punch-list #32.
    verify_location: record.verify_location
      ?? (record.confidence_score ? record.confidence_score >= 90 : true),
    map_grid: target.verified_map_grid || target.map_grid || '',
    radio_channel: target.verified_talkgroup || target.radio_channel || '',
    tone_name: target.tone_name || '',

    created_at: record.created_at || record.timestamp || null,
    audio_url: audioUrl,
    raw_transcript: record.raw_transcript || '',
    sanitized_transcript: record.sanitized_transcript || '',
    is_test: Boolean(record.is_test ?? target.is_test ?? false),

    // Kept so callers that need an untouched row still have one.
    rawRecord: record,
  };
}

/**
 * The map target for a call: the `target` object when the record has one, otherwise a
 * minimal one built from the flattened fields.
 *
 * Returns null when there is nothing to point at. Coordinates stay null when unresolved —
 * these two fields previously fell back to COQUITLAM_CENTER, which put the incident at
 * City Centre inside the bounds check, so no Tier 1 warning fired (punch-list #2).
 */
export function toMapTarget(call) {
  if (!call) return null;
  if (call.target) return call.target;
  if (!call.address) return null;
  return {
    address: call.address,
    lat: call.lat ?? null,
    lng: call.lng ?? null,
  };
}

/** Whether two records describe the same dispatch. */
export function isSameDispatch(a, b) {
  if (!a || !b) return false;
  if (a.dispatch_id && b.dispatch_id) return a.dispatch_id === b.dispatch_id;
  return a.id != null && a.id === b.id;
}

// Fields the operator can actually SEE on the kiosk. A re-broadcast that changes
// none of these has changed nothing as far as the crew is concerned, whatever else
// moved in the payload (timestamps, confidence, audio_url, routing internals).
//
// Deliberately excludes routing_metrics: OSRM re-runs on every rebuild and can
// return a different duration by a second for an identical call, which would make
// the badge fire on noise -- exactly what this is meant to stop.
const OPERATOR_VISIBLE_FIELDS = [
  'address',
  'incident_type',
  'responding_units',
  'subaddress',
  'intersection',
  'lat',
  'lng',
  'map_grid',
  'radio_channel',
  'response_type',
  'location_type',
  'requested_address',
  'resolution_note',
];

function sameValue(a, b) {
  if (Array.isArray(a) || Array.isArray(b)) {
    const ax = Array.isArray(a) ? a : [];
    const bx = Array.isArray(b) ? b : [];
    return ax.length === bx.length
      && ax.every((v, i) => String(v ?? '').trim() === String(bx[i] ?? '').trim());
  }
  // null, undefined and '' all mean "not present" and must not read as a change.
  const an = a ?? '';
  const bn = b ?? '';
  if (an === '' && bn === '') return true;
  if (typeof an === 'number' || typeof bn === 'number') {
    const af = Number(an);
    const bf = Number(bn);
    if (!Number.isNaN(af) && !Number.isNaN(bf)) return af === bf;
  }
  return String(an).trim() === String(bn).trim();
}

/**
 * Names of the operator-visible fields that differ between two records.
 *
 * Empty array => nothing the crew can see has changed, so the kiosk must NOT
 * announce an update. MQTT QoS 1 is at-least-once, so a duplicate delivery of an
 * identical payload is the contract, not an anomaly; the two-phase pipeline also
 * re-broadcasts after correcting the address and grid. Previously the kiosk
 * flashed "UPDATED" on ANY re-delivery, so it claimed a change had happened when
 * often none had -- an operational claim with nothing behind it (CLAUDE.md 6.1).
 * Punch-list #34.
 *
 * Returns the field list rather than a boolean so the badge can say WHAT changed.
 */
export function getVisibleChanges(current, incoming) {
  if (!current || !incoming) return [];
  return OPERATOR_VISIBLE_FIELDS.filter(
    (f) => !sameValue(current[f], incoming[f])
  );
}

/** Whether a call carries usable coordinates. */
export function hasCoordinates(call) {
  return !!call
    && call.lat != null && call.lng != null
    && !Number.isNaN(Number(call.lat)) && !Number.isNaN(Number(call.lng));
}
