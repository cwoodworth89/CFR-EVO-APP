/**
 * Constants for the HITL verification sidebar.
 *
 * Extracted from VerificationSidebar.jsx for `react-refresh/only-export-components`.
 */

// The talk-group list used to live here; the review sidebar reads it from
// /api/vocabulary?category=radio_channel now, the same rows the parser matches (punch-list #20).

export const toTitleCase = (str) => {
  if (!str) return '';
  return str.replace(/\b\w/g, c => c.toUpperCase());
};
