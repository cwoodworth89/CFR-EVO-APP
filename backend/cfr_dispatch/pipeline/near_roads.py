"""Near roads resolved against the roads near the placed address, not against the whole city.

Punch-list #56, operator direction 2026-08-30 ("all streets follow the same path") and
2026-09-05 ("use the confidently geocoded main address, or the map grid, to narrow the list").

The dispatcher's "near <road> and <road>" names roads close to the incident. Until now each
name was fuzzy-matched against all 1,079 street names with a threshold of 75, and 87 % of
Coquitlam's real streets have a *different* real street scoring 75 or better against them
("aberdeen avenue" to "eden avenue", 85), so a mishearing could be silently rewritten to another
genuine street. Here the candidates are the roads within NEAR_ROAD_RADIUS_M of the placed point,
or the roads crossing the zone when the address is not placed yet, and the outcome is always
reported: exact, matched by base name, substituted within the nearby set (flagged), a known
non-street descriptor, or left as heard and flagged unresolved. Never a city-wide rewrite.

**Descriptors** (2026-09-12): Locution announces things that are not streets -- "near mall
access and turning lane". They are in `public.vocabulary` as category `xstreet_descriptor`,
seeded 2026-08-23 for exactly this, but nothing read that vocabulary, so a correctly heard
descriptor counted as a near road matching nothing. Measured over the corpus: 14 of the 24
unresolved occurrences (58 %) were descriptors, 9 were mistranscriptions and 1 was a real road
just outside the radius. Operator, 2026-09-12: "I don't want turning lane or mall access road
to throw errors if that is what the system hears" and "street first, descriptor only if no
street matches".
"""
import logging
import re
from typing import Any, List, Optional

# Provenance: over the 24 verified near roads whose call was placed on the verified address
# (2026-09-05), the distance from the placed point to the named road was p50 109 m, p90 158 m,
# p99 167 m. 400 m is 2.4 times the p99, and holds about 30 roads around a downtown parcel.
NEAR_ROAD_RADIUS_M = 400

# The same 75 the city-wide matcher used, now applied to the tens of roads near the point
# instead of 1,079 names, and every use is flagged XSTREET_SUBSTITUTED and shown with a mark.
# Inherited and uncited (CLAUDE.md 6.3); the corpus has too few misheard near roads to set it
# from, and the flag plus the small set are the guard, not the number.
NEARBY_FUZZ_THRESHOLD = 75


def _norm(name: str) -> str:
    """Municipal form, upper case, without a parenthesised tag: public.roads writes
    "Chartwell Lane (PRIV)" and "Beedie Drive (Private)", and the tag is not part of the name."""
    from gis_service.normalization import normalize_street_name
    bare = re.sub(r"\s*\([^)]*\)\s*$", "", name or "")
    return normalize_street_name(bare).strip().upper()


def _base(norm: str) -> str:
    """The name without its suffix word, when the last word is a known suffix."""
    try:
        from gis_service.normalization import get_suffix_mappings
        suffixes = {k.upper() for k in get_suffix_mappings()} | {v.upper() for v in get_suffix_mappings().values()}
    except Exception:
        suffixes = set()
    words = norm.split()
    if len(words) >= 2 and words[-1] in suffixes:
        return " ".join(words[:-1])
    return norm


def match_heard_road(heard: str, candidates: List[str]) -> tuple:
    """(resolved candidate or None, how). how: exact | base | nearby-fuzzy | ambiguous | unresolved."""
    h = _norm(heard)
    if not h:
        return None, "unresolved"
    normed = [(c, _norm(c)) for c in candidates if c]
    exact = [c for c, n in normed if n == h]
    if exact:
        return exact[0], "exact"
    hb = _base(h)
    base_hits = sorted({c for c, n in normed if _base(n) == hb})
    if len(base_hits) == 1:
        return base_hits[0], "base"
    if len(base_hits) > 1:
        # Two suffix forms of one name nearby (Chartwell Green and Chartwell Lane): the heard
        # suffix did not match either, so the operator sees the heard text, not a pick.
        return None, "ambiguous"
    try:
        from thefuzz import fuzz
    except Exception:
        return None, "unresolved"
    scored = sorted(((fuzz.ratio(hb, _base(n)), c) for c, n in normed), reverse=True)
    if scored and scored[0][0] >= NEARBY_FUZZ_THRESHOLD and (len(scored) == 1 or scored[0][0] > scored[1][0]):
        return scored[0][1], "nearby-fuzzy"
    return None, "unresolved"


def _plain(name: str) -> str:
    """Upper case with runs of whitespace collapsed. Deliberately NOT the street normaliser:
    a descriptor is not a street, and normalize_street_name would rewrite "Turning Lane" to
    "Turning Ln" before it could be compared. The vocabulary already carries both spellings."""
    return " ".join(str(name or "").upper().split())


def match_descriptor(heard: str, descriptors: List[dict]) -> tuple:
    """(canonical text, kind) when the heard name is a known non-street descriptor, else (None, None).

    Operator ruling 2026-09-12: **street first, descriptor only if no street matches.** This is
    called after the street matcher has failed, never before it, because a descriptor entry can
    otherwise swallow a misheard real street -- Whisper writes "near a gate" for Agate, and if
    "a gate" were ever a descriptor the mishearing would be accepted silently. Measured over
    the 16 descriptor occurrences in the corpus (2026-09-12): the best score any of them
    reached against a real road within 400 m was 53, against the threshold of 75, so none is
    rewritten to a street before it gets here.

    `prefixed` descriptors name a specific facility with the name in front ("Summit Middle
    School Access" for "School Access"), so they match on the tail and keep the heard text --
    the facility is the useful part. `generic` and `ambiguous` match the whole name and are
    shown in the vocabulary's canonical form.
    """
    h = _plain(heard)
    if not h:
        return None, None
    for d in descriptors or []:
        term, norm, kind = _plain(d.get("term")), _plain(d.get("normalized")), d.get("kind") or "generic"
        if kind == "prefixed":
            for t in (term, norm):
                if t and h.endswith(t) and h != t:
                    return str(heard).strip(), kind
        if h in (term, norm):
            # The canonical spelling, so "Turn Ln" and "Turning Ln" both read "Turning Lane".
            return (norm or term).title(), kind
    return None, None


def resolve_near_roads(heard: List[Optional[str]], validator: Any, lat, lng, zone_id=None) -> List[Optional[dict]]:
    """One entry per heard name (None where nothing was heard):
    {"heard", "resolved", "how", "scope"}, scope being point | zone | none."""
    candidates, scope = [], "none"
    descriptors = []
    if validator is not None and hasattr(validator, "xstreet_descriptors"):
        try:
            descriptors = validator.xstreet_descriptors()
        except Exception as e:
            logging.warning(f"XStreet descriptor vocabulary unavailable: {e}")
    if validator is not None and lat is not None and lng is not None:
        try:
            candidates = validator.roads_near_point(lat, lng, NEAR_ROAD_RADIUS_M)
            scope = "point"
        except Exception as e:
            logging.warning(f"Near-road candidates by point failed: {e}")
    if not candidates and validator is not None and zone_id:
        try:
            candidates = validator.roads_in_zone(zone_id)
            scope = "zone"
        except Exception as e:
            logging.warning(f"Near-road candidates by zone failed: {e}")
    out = []
    for name in heard:
        if not name or not str(name).strip():
            out.append(None)
            continue
        resolved, how = (None, "no-candidates") if not candidates else match_heard_road(name, candidates)
        # Street first. Only a name no nearby road accounts for is offered to the descriptor
        # vocabulary (operator, 2026-09-12). "no-candidates" counts as no street matched: a
        # generic descriptor does not depend on where the call is, and the match is a literal
        # vocabulary lookup rather than a fuzzy one, so it cannot invent a street.
        if resolved is None and how in ("unresolved", "no-candidates", "ambiguous"):
            text_, kind = match_descriptor(name, descriptors)
            if text_:
                out.append({"heard": name, "resolved": text_, "how": "descriptor",
                            "kind": kind, "scope": scope})
                continue
        out.append({"heard": name, "resolved": resolved, "how": how, "scope": scope})
    return out


def apply_near_roads(x1, x2, validator, lat, lng, zone_id=None) -> dict:
    """Resolve both heard near roads and return the fields a target carries."""
    near = resolve_near_roads([x1, x2], validator, lat, lng, zone_id)

    def shown(i, heard):
        n = near[i]
        return n["resolved"] if n and n.get("resolved") else heard

    return {
        "x_street_1": shown(0, x1),
        "x_street_2": shown(1, x2),
        "x_streets_heard": [x1, x2],
        "x_streets_how": [n["how"] if n else None for n in near],
        # A descriptor is neither resolved-to-a-street nor unresolved: dispatch named a feature
        # that is not a street and the system heard it correctly, so it is not a reason to
        # review the call (operator, 2026-09-12). It stays in the XStreets field, as spoken.
        "xstreets_unresolved": sum(1 for n in near if n and not n.get("resolved")),
        "xstreets_substituted": sum(1 for n in near if n and n.get("how") == "nearby-fuzzy"),
        "xstreets_descriptors": sum(1 for n in near if n and n.get("how") == "descriptor"),
    }
