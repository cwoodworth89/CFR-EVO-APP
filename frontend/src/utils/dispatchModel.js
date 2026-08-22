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

    priority_code: record.priority_code,
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

/** Whether a call carries usable coordinates. */
export function hasCoordinates(call) {
  return !!call
    && call.lat != null && call.lng != null
    && !Number.isNaN(Number(call.lat)) && !Number.isNaN(Number(call.lng));
}
