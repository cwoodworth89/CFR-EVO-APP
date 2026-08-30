"""Intersection lookup and multi-junction candidate resolution.

WHY THERE IS NO FUZZY AUTO-SUBSTITUTION HERE
--------------------------------------------
This module used to resolve an unmatched intersection by fuzzy-matching the whole
normalized key against every other key and returning the best hit above a score of 80.
Two things were measured on 2026-08-22 and both are fatal to that approach.

1. `token_set_ratio` returns 100 when one token set is a SUBSET of the other. So
   `token_set_ratio('LOUGHEED HWY', 'ALDERSON AVE & LOUGHEED HWY')` = 100. A dispatch
   that parsed to "Lougheed Hwy & Lougheed Hwy" resolved to ALDERSON AVE & LOUGHEED HWY
   at **confidence 100**, reported as an exact, unambiguous answer.

2. More fundamentally, THERE IS NO SAFE SCORE THRESHOLD for street names in this city.
   Measured across all 1,079 distinct road names, real and distinct streets score:

       HAMBER CRT            / AMBER CRT             96
       WESTWOOD ST           / EASTWOOD ST           93
       BURKE MOUNTAIN ST     / BLUE MOUNTAIN ST      93
       HARRISON AVE          / HARRIS AVE            93
       WALLS AVE             / WALES AVE             92

   while the transcription errors worth recovering score:

       TASIS AVE   -> TAHSIS AVE                     95
       JOHNSON ST  -> JOHNSTON ST                    98

   TASIS->TAHSIS (95, correct) scores LOWER than HAMBER->AMBER (96, catastrophic). The
   two populations overlap, so no cutoff separates them. Westwood and Eastwood are both
   real Coquitlam streets on opposite sides of the city.

   Left unaddressed, `Lougheed Hwy & Mariner Way` -- a grade-separated interchange with
   no junction at all -- resolved to `Lougheed Hwy & Pinetree Way`, 4,301 m away, at
   confidence 86 with is_ambiguous=False.

WHAT REPLACES IT
----------------
Fuzzy matching is retained as a CANDIDATE GENERATOR only, and never as a resolution. A
near-miss produces suggestions that are handed to the operator through the CLAUDE.md
section 5 candidate-selector banner (is_ambiguous=True), carrying `requested_address`
and `resolution_note` so the substitution is visible. It is never silently applied, no
matter how high it scores.

The real fix for transcription noise is upstream: Whisper is already given
COQUITLAM_STREETS from public.road_names, and biasing transcription toward the real
street vocabulary prevents "Lowheed" reaching the geocoder at all. Guessing after the
fact cannot be made safe (CLAUDE.md 6.1).
"""
import re
import logging
from typing import List, Tuple, Optional
from .normalization import (
    normalize_intersection_key,
    normalize_street_name,
    split_intersection_parts,
)

try:
    from thefuzz import fuzz
except ImportError:
    import difflib

    class _Fuzz:
        @staticmethod
        def ratio(s1, s2):
            return int(difflib.SequenceMatcher(None, str(s1).lower(), str(s2).lower()).ratio() * 100)

        @staticmethod
        def token_set_ratio(s1, s2):
            return int(difflib.SequenceMatcher(None, str(s1).lower(), str(s2).lower()).ratio() * 100)

    fuzz = _Fuzz()


# Below this, a near-miss is not even worth showing the operator as a suggestion. It is
# NOT a substitution threshold -- nothing is ever auto-applied on the strength of a
# score. Set at the bottom of the band where real transcription errors were observed
# (TASIS->TAHSIS 95, JOHNSON->JOHNSTON 98) with headroom, and deliberately well above
# the 70 scored by genuinely different streets (MARINER WAY vs PINETREE WAY).
SUGGESTION_FLOOR = 85


class IntersectionResolver:
    def __init__(self, intersection_keys_cache: dict, confidence_threshold=80, engine=None):
        self._cache = intersection_keys_cache
        self.confidence_threshold = confidence_threshold
        # Needed only for cross-street narrowing, which measures distance to a bounding
        # road's centreline in public.roads. Without it that stage is skipped.
        self._engine = engine

    # ---------------------------------------------------------------- lookup

    def lookup(self, address: str) -> Tuple[List[dict] | None, int]:
        """Look up an intersection.

        Returns (candidates, score). An EXACT key match scores 100. Anything else
        returns suggestions marked `match_type='suggested'`, which resolve_candidates
        will always present as ambiguous rather than resolving.
        """
        if not self._cache:
            return None, 0
        parts = split_intersection_parts(address)
        if not parts:
            return None, 0
        s1, s2 = parts
        norm_key = normalize_intersection_key(s1, s2)

        # 1. Exact match -- the only path that yields a resolved answer.
        if norm_key in self._cache:
            # Carry the street the dispatcher said FIRST, so _payload can render the
            # junction in announced order rather than the alphabetical order it is
            # stored in. Only recorded on this path: an exact key match proves both
            # legs are the same pair, so ordering them involves no guessing.
            cands = [dict(c, match_type='exact', spoken_first=normalize_street_name(s1))
                     for c in self._cache[norm_key]]
            return cands, 100

        # A street crossed with itself is a parser artifact, not a location. It used to
        # score 100 against any key containing that street via the token_set_ratio
        # subset trap. It is not resolvable and produces no suggestions.
        a, b = sorted([normalize_intersection_key(s1, s1).split(' & ')[0],
                       normalize_intersection_key(s2, s2).split(' & ')[0]])
        if a == b:
            logging.info("Intersection %r names the same street twice; not resolvable.", address)
            return None, 0

        # 2. Suggestions only. Score each street INDEPENDENTLY against the streets that
        #    actually appear in intersection keys. Scoring the whole key lets the shared
        #    half inflate the result -- that is how MARINER WAY -> PINETREE WAY reached
        #    86 on a 4.3 km error.
        suggestions = self._suggest(a, b)
        if suggestions:
            return suggestions, max(s['match_score'] for s in suggestions)
        return None, 0

    def _street_universe(self) -> set:
        if not hasattr(self, '_streets_cache'):
            streets = set()
            for key in self._cache:
                for part in key.split(' & '):
                    part = part.strip()
                    if part:
                        streets.add(part)
            self._streets_cache = streets
        return self._streets_cache

    def _best_streets(self, street: str) -> List[Tuple[str, int]]:
        """Streets scoring at or above SUGGESTION_FLOOR, best first."""
        scored = []
        for known in self._street_universe():
            if known == street:
                return [(known, 100)]
            score = fuzz.ratio(street, known)
            if score >= SUGGESTION_FLOOR:
                scored.append((known, score))
        scored.sort(key=lambda t: -t[1])
        return scored[:4]

    def _suggest(self, street_a: str, street_b: str) -> List[dict]:
        """Build suggestion candidates from per-street near matches.

        Only combinations that correspond to an intersection that REALLY EXISTS are
        offered -- a suggestion pointing at a junction the road network does not contain
        would be a fabrication with extra steps.
        """
        out = []
        seen = set()
        for cand_a, score_a in self._best_streets(street_a):
            for cand_b, score_b in self._best_streets(street_b):
                if cand_a == cand_b:
                    continue
                key = normalize_intersection_key(cand_a, cand_b)
                if key in seen or key not in self._cache:
                    continue
                seen.add(key)
                combined = min(score_a, score_b)
                for c in self._cache[key]:
                    out.append(dict(
                        c,
                        match_type='suggested',
                        match_score=combined,
                        matched_key=key,
                    ))
        out.sort(key=lambda c: -c['match_score'])
        return out[:6]

    # ------------------------------------------------------- candidate resolution

    def _payload(self, c: dict, candidates: List[dict], *, ambiguous: bool,
                 confidence: float, requested: str = None, note: str = None) -> dict:
        return {
            "address": self._name_in_spoken_order(c),
            "lat": c["lat"],
            "lng": c["lng"],
            "rings": [],
            "grid": c.get("grid"),
            "is_ambiguous": ambiguous,
            "candidates": candidates,
            "confidence": confidence,
            "requested_address": requested,
            "resolution_note": note,
        }

    @staticmethod
    def _name_in_spoken_order(c: dict) -> str:
        """Render the junction leading with the street the dispatcher said first.

        `public.intersections` stores the pair alphabetically -- measured 2026-08-29,
        `street_a < street_b` on all 1,995 rows -- so `c['name']` is in alphabetical
        order regardless of what was announced. On 10 of the 12 intersection dispatches
        that resolved through this path, that read back reversed from the announcement:
        "Westwood St and Loheed Highway" was spoken and `Lougheed Highway & Westwood St`
        was stored.

        The street SPELLINGS stay municipal -- only the order comes from the
        announcement, so a transcription error like "Loheed" is still corrected to
        "Lougheed Highway" here.

        Safe because `spoken_first` is set only on an exact key match, where both legs
        are already known to be the same pair (`lookup`). No fuzzy matching is involved;
        the only question is which of the two the dispatcher led with. If that cannot be
        answered unambiguously, the stored order is kept.
        """
        name = c.get("name") or ""
        spoken_first = c.get("spoken_first")
        if not spoken_first or " & " not in name:
            return name
        left, right = (p.strip() for p in name.split(" & ", 1))
        leads_with_right = normalize_street_name(right) == spoken_first
        leads_with_left = normalize_street_name(left) == spoken_first
        if leads_with_right and not leads_with_left:
            return f"{right} & {left}"
        return name

    @staticmethod
    def _metres(a: Tuple[float, float], b: Tuple[float, float]) -> float:
        import math
        R = 6371000.0
        p1, p2 = math.radians(a[0]), math.radians(b[0])
        dp = p2 - p1
        dl = math.radians(b[1] - a[1])
        h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return 2 * R * math.asin(math.sqrt(h))

    def _narrow_by_cross_streets(self, candidates: List[dict],
                                 cross_streets: List[str]) -> Tuple[List[dict], str | None]:
        """Narrow several junctions of one street pair using nearby bounding roads.

        Cross streets in a Locution announcement are NOT junctions -- they are nearby
        roads that bound roughly where the call is ("between Westwood and Johnson").
        So the measure is distance from each candidate to the cross street's CENTRELINE
        in public.roads, not to any junction with it: the bounding road need not touch
        either named street at all.

        Requires a database engine. Without one this is skipped rather than approximated,
        because the alternative -- anchoring on a junction the cross street happens to
        form elsewhere -- would silently answer a different question.

        Never empties the set. If the roads cannot be found, or every candidate is about
        as close to them, the candidates are returned unchanged with a note. An
        uninformative signal is not grounds for discarding a real junction.
        """
        if not cross_streets or self._engine is None:
            return candidates, None

        names = [normalize_intersection_key(c, c).split(' & ')[0]
                 for c in cross_streets if c]
        if not names:
            return candidates, None

        try:
            from sqlalchemy import text
            with self._engine.connect() as conn:
                rows = conn.execute(text("""
                    WITH sfx AS (
                        SELECT upper(btrim(term)) f, upper(btrim(term_normalized)) a
                        FROM public.vocabulary
                        WHERE category = 'street_suffix' AND is_active
                    ),
                    street AS (
                        SELECT btrim(regexp_replace(upper(btrim(r.roadname)), '[,.]', '', 'g')
                                     || ' ' || COALESCE(s.a, upper(btrim(COALESCE(r.roadtype,'')))))
                                 AS canon,
                               ST_Union(r.geom) AS geom
                        FROM public.roads r
                        LEFT JOIN sfx s ON s.f = upper(btrim(r.roadtype))
                        WHERE r.roadname IS NOT NULL AND btrim(r.roadname) <> ''
                        GROUP BY 1
                    )
                    SELECT canon, ST_AsText(geom) FROM street WHERE canon = ANY(:names)
                """), {"names": names}).fetchall()
        except Exception as e:
            logging.warning("Cross-street narrowing skipped (road geometry unavailable): %s", e)
            return candidates, None

        found = {r[0] for r in rows}
        if not found:
            return candidates, (f"cross street(s) {', '.join(names)} not found in "
                                f"public.roads, so they could not narrow these")

        try:
            from sqlalchemy import text
            with self._engine.connect() as conn:
                dists = {}
                for c in candidates:
                    d = conn.execute(text("""
                        WITH sfx AS (
                            SELECT upper(btrim(term)) f, upper(btrim(term_normalized)) a
                            FROM public.vocabulary
                            WHERE category = 'street_suffix' AND is_active
                        ),
                        street AS (
                            SELECT btrim(regexp_replace(upper(btrim(r.roadname)), '[,.]', '', 'g')
                                         || ' ' || COALESCE(s.a, upper(btrim(COALESCE(r.roadtype,'')))))
                                     AS canon,
                                   ST_Union(r.geom) AS geom
                            FROM public.roads r
                            LEFT JOIN sfx s ON s.f = upper(btrim(r.roadtype))
                            WHERE r.roadname IS NOT NULL AND btrim(r.roadname) <> ''
                            GROUP BY 1
                        )
                        SELECT min(ST_Distance(
                                 street.geom::geography,
                                 ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography))
                        FROM street WHERE canon = ANY(:names)
                    """), {"lat": float(c['lat']), "lng": float(c['lng']),
                           "names": list(found)}).scalar()
                    dists[id(c)] = float(d) if d is not None else float('inf')
        except Exception as e:
            logging.warning("Cross-street narrowing skipped (distance query failed): %s", e)
            return candidates, None

        ranked = sorted(candidates, key=lambda c: dists[id(c)])
        best = dists[id(ranked[0])]
        # A bounding road only distinguishes candidates that it is meaningfully closer
        # to. 150 m is roughly a city block here, so candidates within that of each
        # other are not separated by the bounding road and both stay for the operator.
        kept = [c for c in ranked if dists[id(c)] - best <= 150.0]
        if len(kept) == len(candidates):
            return candidates, (f"cross street(s) {', '.join(found)} do not distinguish "
                                f"these junctions")
        return kept, None

    def _narrow_by_grid(self, candidates: List[dict],
                        target_map_grid: str | int) -> Tuple[List[dict], str | None]:
        """Keep only candidates in the map grid the dispatch actually spoke.

        The grid is real data from the Locution announcement, not something inferred, so
        filtering on it is not a guess. It is present on 390 of 410 recorded dispatches
        and on all 24 intersection dispatches, which makes it the workhorse of this
        cascade.

        If nothing matches the grid, the candidates are returned UNCHANGED rather than
        emptied: a grid that matches no candidate means the grid and the street pair
        disagree, which the operator needs to see, not something to silently resolve.
        """
        if target_map_grid is None:
            return candidates, None
        target = re.sub(r'^(?:GRID|ZONE)\s*', '', str(target_map_grid).strip(),
                        flags=re.IGNORECASE)
        matched = [c for c in candidates
                   if str(c.get("grid", "")).strip()
                   and str(c.get("grid", "")).strip().lower() == target.lower()]
        if not matched:
            return candidates, f"none of these junctions lie in map grid {target}"
        return matched, None

    def resolve_candidates(self, candidates: List[dict], target_map_grid: str | int = None,
                           requested_address: str = None,
                           cross_streets: List[str] = None) -> dict | None:
        """Turn candidates into a coordinate payload.

        The narrowing cascade runs over whatever candidates exist -- exact or suggested
        -- so a near-miss is narrowed before it is shown. But narrowing never GRANTS
        resolution authority: only an exact key match can resolve automatically. Cutting
        a wrong-street suggestion down to one candidate does not make it right, it just
        makes the operator's choice shorter.

        Cascade order is cross streets, then map grid. Cross streets are the more
        specific anchor -- a named nearby street pins a junction far more tightly than a
        zone does -- so they run first; the grid then narrows whatever remains. Neither
        ever empties the candidate set: a filter that matches nothing returns the set
        unchanged with a note, because a signal that contradicts every candidate is
        something the operator must see, not grounds for a silent pick.

        As of 2026-08-22 cross streets are newly captured and appear on 1 of 410 recorded
        dispatches; the map grid appears on 390 of 410 and on all 24 intersection
        dispatches, so grid does the work today and cross streets take over as the
        stronger signal once the corpus fills in.
        """
        if not candidates:
            return None

        exact = all(c.get('match_type') != 'suggested' for c in candidates)
        narrowed, cross_note = self._narrow_by_cross_streets(candidates, cross_streets or [])
        narrowed, grid_conflict = self._narrow_by_grid(narrowed, target_map_grid)

        # Only a CONTRADICTION blocks automatic resolution. A grid that matches no
        # candidate means the spoken grid and the street pair disagree -- the operator
        # has to see that. A cross street that was merely uninformative (no junction with
        # either street, or it failed to separate them) is a no-op: it is reported but it
        # does not veto an otherwise unambiguous answer.
        asides = [n for n in (cross_note,) if n]

        if not exact:
            primary = narrowed[0]
            names = ', '.join(dict.fromkeys(
                c.get('matched_key') or c['name'] for c in narrowed))
            note = (
                f"'{requested_address}' does not match any intersection in the road "
                f"network. Nearest existing: {names}. Confirm before dispatching."
                if requested_address else
                f"No exact intersection match. Nearest existing: {names}. "
                f"Confirm before dispatching."
            )
            for extra in ([grid_conflict] if grid_conflict else []) + asides:
                note += f" Note: {extra}."
            return self._payload(
                primary, narrowed, ambiguous=True,
                confidence=float(primary.get('match_score', 0)),
                requested=requested_address, note=note)

        if len(narrowed) == 1 and not grid_conflict:
            note = '. '.join(a.capitalize() for a in asides) or None
            return self._payload(narrowed[0], narrowed, ambiguous=False,
                                 confidence=100.0, note=note)

        note = f"{len(narrowed)} junctions exist for this street pair"
        for extra in ([grid_conflict] if grid_conflict else []) + asides:
            note += f"; {extra}"
        note += ". Select the correct one."
        return self._payload(narrowed[0], narrowed, ambiguous=True,
                             confidence=100.0, note=note)
