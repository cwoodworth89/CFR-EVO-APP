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
  NO_TALK_GROUP: 'No talk group announced or transcribed',
  NO_MAP_GRID: 'No map grid announced or transcribed',
  NO_UNITS: 'No responding units identified',
  UNKNOWN_CALL_TYPE: 'Call type missing or generic',
  RESPONSE_TYPE_UNKNOWN: 'Response type not announced or not transcribed',
};

/** Flags on a record, from either the flattened call or the raw target. */
export function getReviewFlags(call) {
  if (!call) return [];
  const flags = call.review_flags ?? call.target?.review_flags;
  return Array.isArray(flags) ? flags : [];
}

/** Operator-facing label, falling back to the raw key so drift is visible. */
export function flagLabel(flag) {
  return FLAG_LABELS[flag] || flag;
}
