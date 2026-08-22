# cfr_dispatch/parser/call_types.py
# Incident/call type vocabulary loading and fuzzy matching.

import os
import logging
import regex as re
from typing import List
from thefuzz import fuzz

def load_call_types(filepath="call_types.txt") -> List[str]:
    """Loads and returns sorted call types list from a text file, longest first."""
    if filepath == "call_types.txt":
        try:
            from cfr_dispatch.config import CALL_TYPES as cfg_call_types
            if cfg_call_types:
                return cfg_call_types
        except ImportError:
            pass

    call_types = []
    
    # Resolve default filepath relative to the parent directory of this module (agent/)
    if filepath == "call_types.txt":
        package_dir = os.path.dirname(os.path.abspath(__file__))
        agent_dir = os.path.dirname(package_dir)
        resolved_path = os.path.join(agent_dir, "data", "vocabulary", "call_types.txt")
        if os.path.exists(resolved_path):
            filepath = resolved_path
        else:
            resolved_path = os.path.join(agent_dir, "call_types.txt")
            if os.path.exists(resolved_path):
                filepath = resolved_path

    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        call_types.append(line)
            logging.info(f"Loaded {len(call_types)} call types from '{filepath}'")
        except Exception as e:
            logging.error(f"Error loading call types from '{filepath}': {e}")
    else:
        logging.warning(f"'{filepath}' not found. Fuzzy incident type matching will be limited.")
    return sorted(call_types, key=len, reverse=True)

# Global call types list initialized on module import
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
