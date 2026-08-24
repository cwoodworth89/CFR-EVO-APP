# cfr_dispatch/parser/call_types.py
# Incident/call type vocabulary loading and fuzzy matching.

import logging
import regex as re
from typing import List
from thefuzz import fuzz

def load_call_types(filepath: str = None) -> List[str]:
    """Returns the call-type vocabulary from public.vocabulary via the config layer.

    `filepath` is accepted for backwards compatibility with existing callers and is
    ignored; vocabulary has no runtime file fallback (see config/vocab.py).
    """
    from cfr_dispatch.config import CALL_TYPES as cfg_call_types
    return cfg_call_types


def load_call_type_aliases() -> dict:
    """Recognition-only spellings, keyed lowercased -> canonical term (see config/vocab.py)."""
    from cfr_dispatch.config import CALL_TYPE_ALIASES as cfg_aliases
    return cfg_aliases


# Module-level call-type vocabulary, resolved from public.vocabulary on import.
CALL_TYPES = load_call_types()
CALL_TYPE_ALIASES = load_call_type_aliases()


def match_incident_type(transcript: str, call_types: List[str], aliases: dict = None) -> str:
    """Matches transcript text to incident/call types using exact substring or fuzzy matching.

    Returns a CANONICAL term always. `aliases` maps a recognition-only spelling to the
    canonical term it stands for: faster-whisper writes American English while the
    department writes Canadian, so the string matched is not always the string shown
    (punch-list #43). Defaults to the vocabulary-backed map when not supplied.
    """
    if aliases is None:
        aliases = CALL_TYPE_ALIASES

    # Normalize transcript by removing hyphens and double spaces for clean matching
    norm_transcript = re.sub(r'\s*-\s*', ' ', transcript.lower())

    # Candidates are canonical terms plus recognition aliases, each carrying the canonical
    # term it resolves to. Longest-first so a qualified type ("Report of Smoke - High
    # Risk") is tested before the base type it contains, which would otherwise match first
    # and silently drop the qualifier.
    candidates = [(ct, ct) for ct in call_types]
    candidates += [(alias, canon) for alias, canon in aliases.items()]
    candidates.sort(key=lambda pair: len(pair[0]), reverse=True)

    # 1. Look for exact substring matches (normalizing the candidate too)
    for match_text, canonical in candidates:
        norm_ct = re.sub(r'\s*-\s*', ' ', match_text.lower())
        if norm_ct in norm_transcript:
            return canonical

    # 2. Look for best fuzzy match
    best_match = None
    best_score = 0
    for match_text, canonical in candidates:
        score = fuzz.token_set_ratio(match_text.lower(), transcript)
        if score > best_score:
            best_score = score
            best_match = canonical
            
    # PROVENANCE REQUIRED (CLAUDE.md §6.3): 80 is an inherited fuzzy-match cutoff with
    # no cited source. Failing it is safe -- the result is the explicit "Unknown
    # Incident", never a guessed call type -- but the value should be validated against
    # the HITL correction history rather than left as a magic number.
    if best_score >= 80:
        return best_match
    return "Unknown Incident"
