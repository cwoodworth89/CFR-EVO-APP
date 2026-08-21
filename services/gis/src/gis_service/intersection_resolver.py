"""Intersection lookup, fuzzy key matching, and multi-junction candidate resolution."""
import re
import logging
from typing import List, Tuple, Optional
from .normalization import normalize_intersection_key, split_intersection_parts

try:
    from thefuzz import fuzz
except ImportError:
    import difflib
    class _Fuzz:
        @staticmethod
        def token_set_ratio(s1, s2):
            return int(difflib.SequenceMatcher(None, str(s1).lower(), str(s2).lower()).ratio() * 100)
    fuzz = _Fuzz()


class IntersectionResolver:
    def __init__(self, intersection_keys_cache: dict, confidence_threshold=80):
        self._cache = intersection_keys_cache
        self.confidence_threshold = confidence_threshold

    def lookup(self, address: str) -> Tuple[List[dict] | None, int]:
        """
        Parses intersection address and looks up candidates in normalized index.
        Returns (candidates, score).
        """
        if not self._cache:
            return None, 0
        parts = split_intersection_parts(address)
        if not parts:
            return None, 0
        s1, s2 = parts
        norm_key = normalize_intersection_key(s1, s2)

        # 1. Exact match
        if norm_key in self._cache:
            return self._cache[norm_key], 100

        # 2. Road type alias match (e.g. RD <-> AVE)
        alias_replacements = [
            (" RD", " AVE"), (" AVE", " RD"),
            (" ST", " WAY"), (" WAY", " ST"),
            (" BLVD", " DR"), (" DR", " BLVD")
        ]
        for src, target in alias_replacements:
            if src in norm_key:
                alt_key = norm_key.replace(src, target)
                if alt_key in self._cache:
                    return self._cache[alt_key], 95

        # 3. Fuzzy matching across keys
        best_score = 0
        best_cands = None
        for key, cands in self._cache.items():
            score = fuzz.token_set_ratio(norm_key, key)
            if score > best_score:
                best_score = score
                best_cands = cands

        if best_score >= self.confidence_threshold and best_cands is not None:
            return best_cands, best_score

        return None, 0

    def resolve_candidates(self, candidates: List[dict], target_map_grid: str | int = None) -> dict | None:
        """
        Disambiguates candidate list using target_map_grid if provided.
        Returns formatted coordinate payload.
        """
        if not candidates:
            return None

        if len(candidates) == 1:
            c = candidates[0]
            return {
                "address": c["name"],
                "lat": c["lat"],
                "lng": c["lng"],
                "rings": [],
                "grid": c.get("grid"),
                "is_ambiguous": False,
                "candidates": candidates,
                "confidence": 100.0
            }

        # Multiple candidates (e.g., dual-junction corridor)
        if target_map_grid is not None:
            target_grid_clean = re.sub(r'^(?:GRID|ZONE)\s*', '', str(target_map_grid).strip(), flags=re.IGNORECASE)
            for c in candidates:
                cand_grid = str(c.get("grid", "")).strip()
                if cand_grid and cand_grid.lower() == target_grid_clean.lower():
                    return {
                        "address": c["name"],
                        "lat": c["lat"],
                        "lng": c["lng"],
                        "rings": [],
                        "grid": c.get("grid"),
                        "is_ambiguous": False,
                        "candidates": candidates,
                        "confidence": 100.0
                    }

        # No grid or grid unmatched: return primary candidate with is_ambiguous=True
        primary = candidates[0]
        return {
            "address": primary["name"],
            "lat": primary["lat"],
            "lng": primary["lng"],
            "rings": [],
            "grid": primary.get("grid"),
            "is_ambiguous": True,
            "candidates": candidates,
            "confidence": 100.0
        }
