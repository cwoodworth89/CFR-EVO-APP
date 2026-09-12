/**
 * Operator-facing wording for the named review flags (punch-list #45).
 *
 * Mirrors FLAG_LABELS in backend/cfr_dispatch/pipeline/review_flags.py. Two copies of
 * one fact, which is a known hazard in this codebase -- but the alternative is an API
 * round-trip to render a tooltip. Keep them in step: the backend test
 * test_every_flag_has_operator_facing_wording fails if a flag has no label there, and
 * an unknown key here falls through to the raw identifier rather than rendering blank,
 * so a drifted flag is visible rather than silent.
 */
export const FLAG_LABELS = {
  LOCATION_UNRESOLVED: 'Address could not be located',
  LOCATION_SUBSTITUTED: 'Location was substituted by the resolver',
  STREET_SECTION_ONLY: 'Street section only — no point location',
  BLOCK_MIDPOINT: "Announced as a block; the pin is the block's middle, not an address",
  NO_TALK_GROUP: 'Talk group unknown — none announced, or not transcribed',
  NO_MAP_GRID: 'Map grid unknown — none announced, or not transcribed',
  GRID_MISMATCH: 'Announced map grid differs from the zone the address sits in',
  XSTREET_UNRESOLVED: 'A near road as heard matches no road near the address',
  XSTREET_SUBSTITUTED: 'A near road was matched to a nearby road by spelling; check it',
  NO_UNITS: 'No responding units identified',
  UNKNOWN_CALL_TYPE: 'Call type missing or generic',
  RESPONSE_TYPE_UNKNOWN: 'Response type not announced or not transcribed',
};

/**
 * The verified column whose value rules each flag. A flag is the system saying "look at
 * this"; once the operator has written the answer into the verified column, the look has
 * happened and the flag is ruled -- it stops counting, and the review shows it struck
 * through with the ruling beside it (operator, 2026-09-06: "Can I rule one way or another
 * and the system won't flag anymore?"). The notes for the ruling go in review_notes as
 * before. The flags themselves are never rewritten: they record what the system saw.
 */
export const FLAG_RULED_BY = {
  GRID_MISMATCH: 'verified_map_grid',
  NO_MAP_GRID: 'verified_map_grid',
  XSTREET_UNRESOLVED: 'verified_x_street_1',
  XSTREET_SUBSTITUTED: 'verified_x_street_1',
  NO_TALK_GROUP: 'verified_talkgroup',
  RESPONSE_TYPE_UNKNOWN: 'verified_response_type',
  NO_UNITS: 'verified_units',
  UNKNOWN_CALL_TYPE: 'verified_incident',
  LOCATION_UNRESOLVED: 'verified_address',
  LOCATION_SUBSTITUTED: 'verified_address',
  STREET_SECTION_ONLY: 'verified_address',
  BLOCK_MIDPOINT: 'verified_address',
};

/** The box on the review form whose value rules a flag, in the operator's words. */
const RULED_BY_LABEL = {
  verified_map_grid: 'the map grid box',
  verified_x_street_1: 'the near roads',
  verified_talkgroup: 'the talk group',
  verified_response_type: 'the response type',
  verified_units: 'the units',
  verified_incident: 'the incident type',
  verified_address: 'the address',
};

/** "ruled by the map grid box", or '' for a flag nothing rules. Shown beside each open
 *  flag so the operator knows which box to fill (ux_notes, review screen, 2026-09-08). */
export function flagRuledByLabel(flag) {
  const field = FLAG_RULED_BY[flag];
  return field && RULED_BY_LABEL[field] ? `ruled by ${RULED_BY_LABEL[field]}` : '';
}

function rulingFor(call, flag) {
  const field = FLAG_RULED_BY[flag];
  if (!field) return null;
  const value = call?.[field] ?? call?.target?.[field];
  if (value == null) return null;
  if (Array.isArray(value)) return value.length ? value.join(', ') : null;
  const text = String(value).trim();
  return text ? text : null;
}

/** Every flag the system raised on a record, ruled or not. */
export function getAllReviewFlags(call) {
  if (!call) return [];
  const flags = call.review_flags ?? call.target?.review_flags;
  return Array.isArray(flags) ? flags : [];
}

/** Flags still open: raised by the system and not yet ruled by a verified value. */
export function getReviewFlags(call) {
  return getAllReviewFlags(call).filter(f => rulingFor(call, f) == null);
}

/** Flags the operator has ruled, with the ruling: [{ flag, ruling }]. */
export function getRuledFlags(call) {
  return getAllReviewFlags(call)
    .map(flag => ({ flag, ruling: rulingFor(call, flag) }))
    .filter(x => x.ruling != null);
}

/** Operator-facing label, falling back to the raw key so drift is visible. */
export function flagLabel(flag) {
  return FLAG_LABELS[flag] || flag;
}
