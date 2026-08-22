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


# Module-level call-type vocabulary, resolved from public.vocabulary on import.
CALL_TYPES = load_call_types()


def match_incident_type(transcript: str, call_types: List[str]) -> str:
    """Matches transcript text to incident/call types using exact substring or fuzzy matching."""
    # Normalize transcript by removing hyphens and double spaces for clean matching
    norm_transcript = re.sub(r'\s*-\s*', ' ', transcript.lower())
    
    # 1. Look for exact substring matches (normalizing the call type too)
    for ct in call_types:
        norm_ct = re.sub(r'\s*-\s*', ' ', ct.lower())
        if norm_ct in norm_transcript:
            return ct
            
    # 2. Look for best fuzzy match
    best_match = None
    best_score = 0
    for ct in call_types:
        score = fuzz.token_set_ratio(ct.lower(), transcript)
        if score > best_score:
            best_score = score
            best_match = ct
            
    # PROVENANCE REQUIRED (CLAUDE.md §6.3): 80 is an inherited fuzzy-match cutoff with
    # no cited source. Failing it is safe -- the result is the explicit "Unknown
    # Incident", never a guessed call type -- but the value should be validated against
    # the HITL correction history rather than left as a magic number.
    if best_score >= 80:
        return best_match
    return "Unknown Incident"
