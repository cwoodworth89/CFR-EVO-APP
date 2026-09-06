"""Near roads resolved against the roads near the placed address, not against the whole city.

Punch-list #56, operator direction 2026-08-30 ("all streets follow the same path") and
2026-09-05 ("use the confidently geocoded main address, or the map grid, to narrow the list").

The dispatcher's "near <road> and <road>" names roads close to the incident. Until now each
name was fuzzy-matched against all 1,079 street names with a threshold of 75, and 87 % of
Coquitlam's real streets have a *different* real street scoring 75 or better against them
("aberdeen avenue" to "eden avenue", 85), so a mishearing could be silently rewritten to another
genuine street. Here the candidates are the roads within NEAR_ROAD_RADIUS_M of the placed point,
or the roads crossing the zone when the address is not placed yet, and the outcome is always
reported: exact, matched by base name, substituted within the nearby set (flagged), or left as
heard and flagged unresolved. Never a city-wide rewrite.
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


def resolve_near_roads(heard: List[Optional[str]], validator: Any, lat, lng, zone_id=None) -> List[Optional[dict]]:
    """One entry per heard name (None where nothing was heard):
    {"heard", "resolved", "how", "scope"}, scope being point | zone | none."""
    candidates, scope = [], "none"
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
        if not candidates:
            out.append({"heard": name, "resolved": None, "how": "no-candidates", "scope": scope})
            continue
        resolved, how = match_heard_road(name, candidates)
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
        "xstreets_unresolved": sum(1 for n in near if n and not n.get("resolved")),
        "xstreets_substituted": sum(1 for n in near if n and n.get("how") == "nearby-fuzzy"),
    }
