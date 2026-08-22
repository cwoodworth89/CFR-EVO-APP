/**
 * Constants for the HITL verification sidebar.
 *
 * Extracted from VerificationSidebar.jsx for `react-refresh/only-export-components`.
 */

// ⚠️ DUPLICATE OF public.vocabulary (category 'radio_channel'), which holds the same
// eight entries and is what the dispatch parser matches against. The two have already
// drifted in format -- the database stores "Talk Group 5 Coquitlam" where this stores
// "5", and "Talk Group 10 Combined Response Coquitlam" where this stores
// "10 Combined Response".
//
// This is the same defect class as the street-suffix vocabulary that was moved into the
// database on 2026-08-22: two hand-maintained lists of one fact, free to diverge, with
// nothing reporting it when they do. The operator's HITL dropdown reads this list while
// the parser reads the database, so a talk group change corrects one and not the other.
//
// Should be fetched from the API instead. Tracked as punch-list #20; left in place here
// rather than changed as a side effect of a lint extraction.
export const TALK_GROUPS = [
  "5",
  "6",
  "7",
  "8",
  "9",
  "10 Combined Response",
  "Combined Venue Port Mann",
  "Combined Venue Transit System"
];

export const toTitleCase = (str) => {
  if (!str) return '';
  return str.replace(/\b\w/g, c => c.toUpperCase());
};
