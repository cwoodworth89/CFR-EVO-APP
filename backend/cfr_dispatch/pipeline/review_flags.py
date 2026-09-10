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
BLOCK_MIDPOINT = "BLOCK_MIDPOINT"
NO_TALK_GROUP = "NO_TALK_GROUP"
NO_MAP_GRID = "NO_MAP_GRID"
GRID_MISMATCH = "GRID_MISMATCH"
XSTREET_UNRESOLVED = "XSTREET_UNRESOLVED"
XSTREET_SUBSTITUTED = "XSTREET_SUBSTITUTED"
NO_UNITS = "NO_UNITS"
UNKNOWN_CALL_TYPE = "UNKNOWN_CALL_TYPE"
RESPONSE_TYPE_UNKNOWN = "RESPONSE_TYPE_UNKNOWN"

# Operator-facing wording, kept beside the identifiers so the two cannot drift.
FLAG_LABELS = {
    LOCATION_UNRESOLVED: "Address could not be located",
    LOCATION_SUBSTITUTED: "Location was substituted by the resolver",
    STREET_SECTION_ONLY: "Street section only — no point location",
    BLOCK_MIDPOINT: "Announced as a block; the pin is the block's middle, not an address",
    NO_TALK_GROUP: "No talk group announced or transcribed",
    NO_MAP_GRID: "No map grid announced or transcribed",
    GRID_MISMATCH: "Announced map grid differs from the zone the address sits in",
    XSTREET_UNRESOLVED: "A near road as heard matches no road near the address",
    XSTREET_SUBSTITUTED: "A near road was matched to a nearby road by spelling; check it",
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
                         resolution_note=None, location_type=None, derived_map_grid=None,
                         xstreets_unresolved=0, xstreets_substituted=0):
    """Return the sorted list of flags that apply to one dispatch.

    Pure and keyword-only: every input is passed explicitly so this can be tested
    without constructing a payload, and so a caller cannot silently pass the wrong
    positional argument.
    """
    flags = []

    kind = str(location_type or "").strip()
    if lat is None or lng is None:
        flags.append(LOCATION_UNRESOLVED)
    # A block's middle carries a resolution_note (it raises the kiosk's amber banner) but
    # it is not a substitution: the dispatcher named the block and the pin is where the
    # block is. One flag per fact, BLOCK_MIDPOINT below (#76).
    if not _blank(resolution_note) and kind != "block":
        flags.append(LOCATION_SUBSTITUTED)
    if kind == "street_section":
        flags.append(STREET_SECTION_ONLY)
    if kind == "block":
        flags.append(BLOCK_MIDPOINT)

    if _blank(radio_channel):
        flags.append(NO_TALK_GROUP)
    if _blank(map_grid):
        flags.append(NO_MAP_GRID)
    # Phase 1 published the parcel's zone; phase 2 heard a different grid. Either the
    # dispatcher assigned across a zone line or the transcript is wrong; a person decides
    # (punch-list #72). Numeric strings compare without leading zeros, as round_comparison does.
    if (not _blank(map_grid) and not _blank(derived_map_grid)
            and str(map_grid).strip().lstrip("0") != str(derived_map_grid).strip().lstrip("0")):
        flags.append(GRID_MISMATCH)
    # Near roads (#56): a name left as heard, and a name matched by spelling within the nearby set.
    if xstreets_unresolved:
        flags.append(XSTREET_UNRESOLVED)
    if xstreets_substituted:
        flags.append(XSTREET_SUBSTITUTED)

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
