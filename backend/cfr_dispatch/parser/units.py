# cfr_dispatch/parser/units.py
# Apparatus unit abbreviation, expansion, and Phase 1/Phase 2 merge.

import logging
import regex as re
from typing import List

from cfr_dispatch.config import UNITS_VOCAB_RAW, UNITS_VOCABULARY

def get_unit_abbreviation(unit_type: str) -> str:
    """Returns the abbreviation code for a given unit type (e.g., engine -> E)."""
    mapping = {
        "engine": "E",
        "ladder": "L",
        "rescue": "R",
        "car": "C",
        "squad": "S",
        "medic": "M",
        "quint": "Q",
        "tender": "T",
        "hazmat": "H",
        "hazmat tender": "HT",
        "light attack vehicle": "LAV"
    }
    ut_lower = unit_type.lower().strip()
    if ut_lower in mapping:
        return mapping[ut_lower]
        
    # Fallback/dynamic abbreviation:
    # If it is multi-word (e.g., "Hazmat Tender"), take first letter of each word
    words = ut_lower.split()
    if len(words) > 1:
        return "".join(w[0].upper() for w in words)
    else:
        return ut_lower[:3].upper()

def abbreviate_units(units_str: str) -> List[str]:
    """
    Formats raw unit names into apparatus abbreviation codes (e.g. Engine 1 -> E1).
    Validates unit types and numbers against ground-truth UNITS_VOCAB_RAW.
    """
    if not units_str:
        return []
        
    # Sort units vocabulary descending by length to match multi-word unit types first
    sorted_vocab = sorted(UNITS_VOCABULARY, key=len, reverse=True)
    vocab_pattern = '|'.join(re.escape(ut.lower()) for ut in sorted_vocab)
    
    found_units = []
    # Search for unit types followed by a number
    matches = re.findall(
        r'\b(' + vocab_pattern + r')\s+([\w\d-]+)\b',
        units_str.lower()
    )
    
    valid_units_set = {u.strip().lower() for u in UNITS_VOCAB_RAW}
    
    for unit_type, unit_num in matches:
        raw_unit_name = f"{unit_type.strip()} {unit_num.strip()}".lower()
        if raw_unit_name in valid_units_set:
            abbr = get_unit_abbreviation(unit_type)
            u_code = f"{abbr}{unit_num.upper()}"
            if u_code not in found_units:
                found_units.append(u_code)
        else:
            logging.warning(f"Parsed unit '{raw_unit_name}' is not in ground-truth UNITS_VOCAB_RAW. Rejecting.")
            
    return found_units

def merge_units(p1_str: str, p2_str: str) -> str:
    """
    Merges units lists from Phase 1 and Phase 2.
    Parses them, takes the union, and formats back into a verbal list.
    """
    if not p1_str:
        return p2_str or ""
    if not p2_str:
        return p1_str or ""
        
    sorted_vocab = sorted(UNITS_VOCABULARY, key=len, reverse=True)
    vocab_pattern = '|'.join(re.escape(ut.lower()) for ut in sorted_vocab)
    pattern = r'\b(' + vocab_pattern + r')\s+([\w\d-]+)\b'
    
    def extract_units(s):
        matches = re.findall(pattern, s.lower())
        units_list = []
        seen = set()
        for ut, num in matches:
            u_name = f"{ut.strip().title()} {num.strip().upper()}"
            if u_name.lower() not in seen:
                seen.add(u_name.lower())
                units_list.append(u_name)
        return units_list

    u1 = extract_units(p1_str)
    u2 = extract_units(p2_str)
    
    merged = list(u1)
    for u in u2:
        if u.lower() not in [m.lower() for m in merged]:
            merged.append(u)
            
    return ", ".join(merged)
