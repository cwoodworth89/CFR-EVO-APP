"""Named review flags — the reasons the system believes a dispatch needs a look.

Replaces `confidence_score` (punch-list #45). That was a metadata-completeness score
wearing a confidence label: the geocoder's score minus 30 for no coordinates, 20 for
no units, 15 for no map grid, 15 for no talk group. So a call with a perfectly
correct address but no transcribed talk group scored 85, while a call the geocoder
resolved confidently to the WRONG address scored 100.

Three structural defects it could not be tuned out of:

  * It conflated "is the address right?" with "did every field transcribe?", so
    neither could be read off the result.
  * The penalties had no provenance (CLAUDE.md 6.3) and were not commensurable --
    subtracting "missing talk group" from "geocoder certainty" gives no unit.
  * It DESTROYED the information it consumed: by the time the operator saw 85,
    which field was missing had been thrown away.

A flag list keeps that information. Each flag names one concrete condition the
reviewer can confirm or refute, and a refuted flag is a false positive WITH A NAME --
which is what improves the detector. A score can never give that, because there is
nothing specific to disagree with.

NO SEVERITY TIERS (operator decision 2026-08-29). Every flag counts the same; the
kiosk and review row show a flat total. Adding weights would reintroduce exactly the
unsourced-constant problem this replaces.

Measured across 491 non-PA dispatches before adopting this: 391 (80%) carry zero
flags, 91 carry one, 9 carry two or more. Sparse enough that a flag means something.
"""

# Flag identifiers. Stored in target.review_flags; the UI maps them to prose.
# Names are the contract -- the HITL confirm/refute record keys off them -- so
# rename only with a migration.
LOCATION_UNRESOLVED = "LOCATION_UNRESOLVED"
LOCATION_SUBSTITUTED = "LOCATION_SUBSTITUTED"
STREET_SECTION_ONLY = "STREET_SECTION_ONLY"
NO_TALK_GROUP = "NO_TALK_GROUP"
NO_MAP_GRID = "NO_MAP_GRID"
NO_UNITS = "NO_UNITS"
UNKNOWN_CALL_TYPE = "UNKNOWN_CALL_TYPE"
RESPONSE_TYPE_UNKNOWN = "RESPONSE_TYPE_UNKNOWN"

# Operator-facing wording, kept beside the identifiers so the two cannot drift.
FLAG_LABELS = {
    LOCATION_UNRESOLVED: "Address could not be located",
    LOCATION_SUBSTITUTED: "Location was substituted by the resolver",
    STREET_SECTION_ONLY: "Street section only — no point location",
    NO_TALK_GROUP: "No talk group announced or transcribed",
    NO_MAP_GRID: "No map grid announced or transcribed",
    NO_UNITS: "No responding units identified",
    UNKNOWN_CALL_TYPE: "Call type missing or generic",
    RESPONSE_TYPE_UNKNOWN: "Response type not announced or not transcribed",
}

# Incident strings that mean "we did not get a call type" rather than naming one.
_GENERIC_INCIDENTS = {"", "unknown incident", "emergency dispatch"}


def _blank(value):
    """True when a field carries no usable value.

    Treats the literal strings "none"/"null" as blank: several upstream paths
    stringify a missing value rather than passing None, so a bare falsiness check
    would let "None" through as if it were a real talk group.
    """
    if value is None:
        return True
    text = str(value).strip()
    return text == "" or text.lower() in ("none", "null")


def compute_review_flags(*, lat, lng, responding_units, incident_type,
                         map_grid, radio_channel, response_type,
                         resolution_note=None, location_type=None):
    """Return the sorted list of flags that apply to one dispatch.

    Pure and keyword-only: every input is passed explicitly so this can be tested
    without constructing a payload, and so a caller cannot silently pass the wrong
    positional argument.
    """
    flags = []

    if lat is None or lng is None:
        flags.append(LOCATION_UNRESOLVED)
    if not _blank(resolution_note):
        flags.append(LOCATION_SUBSTITUTED)
    if str(location_type or "").strip() == "street_section":
        flags.append(STREET_SECTION_ONLY)

    if _blank(radio_channel):
        flags.append(NO_TALK_GROUP)
    if _blank(map_grid):
        flags.append(NO_MAP_GRID)

    units = [u for u in (responding_units or []) if not _blank(u)]
    if not units or (len(units) == 1 and str(units[0]).strip().lower() == "unknown unit"):
        flags.append(NO_UNITS)

    if str(incident_type or "").strip().lower() in _GENERIC_INCIDENTS:
        flags.append(UNKNOWN_CALL_TYPE)

    # Distinct from routine. An unannounced response type is a gap to show, not a
    # value to assume (punch-list #31).
    if _blank(response_type):
        flags.append(RESPONSE_TYPE_UNKNOWN)

    return sorted(flags)
