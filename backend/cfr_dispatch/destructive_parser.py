# backend/cfr_dispatch/destructive_parser.py
# Sequential Destructive Parser for structured CAD dispatches

import regex as re
import logging
from typing import List, Tuple, Optional
from cfr_dispatch.config import (
    DispatchData,
    CALL_TYPES,
    RESPONSE_TYPES,
    UNITS_VOCABULARY
)
from cfr_dispatch.parser import sanitize_transcript

# Neighborhood and local agencies sorted by length descending
AGENCY_VOCABULARY = [
    "port coquitlam",
    "port moody",
    "new westminster",
    "burnaby",
    "coquitlam"
]

def parse_destructive(raw_text: str, units_vocab: List[str] = None) -> DispatchData:
    """
    Parses a dispatch transcript by sequentially matching and stripping tokens (destructive parsing).
    Matches sequence: Agency -> Units -> Response Type -> Incident -> Location -> Talk Group -> Map Grid.
    """
    if units_vocab is None:
        units_vocab = UNITS_VOCABULARY

    # 1. Sanitize and normalize input text
    text = sanitize_transcript(raw_text)
    text = " ".join(text.split()).strip()
    original_normalized = text

    agency = None
    units = []
    response_type = "routine"
    incident_type = "Unknown Incident"
    map_grid = None
    radio_channel = None
    address = None
    intersection = None
    subaddress = None

    # Step 1: Match & Strip Agency (from left)
    for ag in AGENCY_VOCABULARY:
        if text.startswith(ag):
            agency = ag
            text = text[len(ag):].strip()
            break

    # Step 2: Match & Strip Responding Units (from left)
    # Match unit type followed by an optional number (e.g. "engine 4", "medic 1")
    unit_pattern = r'^(' + '|'.join(re.escape(u.lower()) for u in units_vocab) + r')(?:\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten))?\b'
    while True:
        # Clean up leading commas, spaces, or "and" words
        text = re.sub(r'^(?:and\s+|,|\s)+', '', text, flags=re.IGNORECASE).strip()
        match = re.match(unit_pattern, text, re.IGNORECASE)
        if match:
            matched_text = match.group(0)
            units.append(matched_text)
            text = text[len(matched_text):].strip()
        else:
            break

    # Step 3: Match & Strip Response Priority (from left)
    # Look for "respond emergency" or "respond routine" or just "respond"
    respond_match = re.match(r'^respond\s+(emergency|routine)\b', text, re.IGNORECASE)
    if respond_match:
        response_type = respond_match.group(1).lower()
        text = text[len(respond_match.group(0)):].strip()
    else:
        # Check for simple "respond" prefix
        respond_simple = re.match(r'^respond\b', text, re.IGNORECASE)
        if respond_simple:
            text = text[len(respond_simple.group(0)):].strip()

    # Step 4: Match & Strip Incident Type (from left or middle before location)
    sorted_incidents = sorted(CALL_TYPES, key=len, reverse=True)
    for ct in sorted_incidents:
        ct_clean = sanitize_transcript(ct)
        # Check if the text starts with the call type (or has it very close to the start)
        if text.startswith(ct_clean):
            incident_type = ct
            text = text[len(ct_clean):].strip()
            break
        # Sometimes there's minor connector words: "for alarm activated" -> strip "for"
        elif re.match(r'^for\s+' + re.escape(ct_clean) + r'\b', text, re.IGNORECASE):
            incident_type = ct
            text = text[len(ct_clean) + 4:].strip()
            break
        # Handle cases where there's trailing comma/space
        elif re.match(r'^' + re.escape(ct_clean) + r'\b', text, re.IGNORECASE):
            incident_type = ct
            text = text[len(ct_clean):].strip()
            break

    # Step 5: Scan & Strip Map Grid (using non-greedy finditer to get last occurrence)
    grid_pattern = r'\bmap\s+grid\s*([a-zA-Z\d-]{1,8})\b'
    grid_matches = list(re.finditer(grid_pattern, text, re.IGNORECASE))
    if grid_matches:
        last_match = grid_matches[-1]
        map_grid = "".join(filter(str.isalnum, last_match.group(1)))
        # Strip from string
        text = text[:last_match.start()].strip() + " " + text[last_match.end():].strip()
        text = " ".join(text.split())
    else:
        # Fallback to general grid matches
        simple_grid_matches = list(re.finditer(r'\bgrid\s*([a-zA-Z\d-]{1,8})\b', text, re.IGNORECASE))
        if simple_grid_matches:
            last_match = simple_grid_matches[-1]
            map_grid = "".join(filter(str.isalnum, last_match.group(1)))
            text = text[:last_match.start()].strip() + " " + text[last_match.end():].strip()
            text = " ".join(text.split())

    # Step 6: Scan & Strip Talk Group (using non-greedy finditer)
    chan_pattern = r'\b(?:use\s+)?talk\s+group\s*(\d+|combined\s+response(?:\s+coquitlam)?)(?:\s+coquitlam)?\b'
    chan_matches = list(re.finditer(chan_pattern, text, re.IGNORECASE))
    if chan_matches:
        last_match = chan_matches[-1]
        raw_chan = last_match.group(1).strip()
        if "combined" in raw_chan.lower():
            radio_channel = "10 Combined Response"
        else:
            radio_channel = raw_chan
        text = text[:last_match.start()].strip() + " " + text[last_match.end():].strip()
        text = " ".join(text.split())
    else:
        simple_chan_matches = list(re.finditer(r'\btalk\s+group\s*(\d+)\b', text, re.IGNORECASE))
        if simple_chan_matches:
            last_match = simple_chan_matches[-1]
            radio_channel = last_match.group(1)
            text = text[:last_match.start()].strip() + " " + text[last_match.end():].strip()
            text = " ".join(text.split())

    # Clean up trailing/leading commas or connectors left after stripping Map Grid and Talk Group
    text = re.sub(r'(?:,\s*|and\s*|use\s*)+$', '', text, flags=re.IGNORECASE).strip()
    text = re.sub(r'^(?:,\s*|and\s*)+', '', text, flags=re.IGNORECASE).strip()

    # Step 7: Parse Location (Address, Intersection, Subaddress) from the remaining text
    if text:
        # Extract subaddress from leftover text first
        sub_indicators = [
            r'\bnumber\s+(\w+)\b',
            r'\bunit\s+(\w+)\b',
            r'\bsuite\s+(\w+)\b',
            r'\bapartment\s+(\w+)\b',
            r'\bapt\s+(\w+)\b',
            r'\b(?:just\s+for|rain\s+city)\s+([\w\s]+?)(?=\s+near|\s+and|\s*$)'
        ]
        
        for pat in sub_indicators:
            sub_match = re.search(pat, text, re.IGNORECASE)
            if sub_match:
                subaddress = sub_match.group(1).strip()
                text = text.replace(sub_match.group(0), "").strip()
                break

        # Check for intersection / crossroads indicators ("and", "near", "&")
        near_match = re.search(r'\bnear\s+([\w\s&]+)$', text, re.IGNORECASE)
        if near_match:
            intersection_candidate = near_match.group(1).strip()
            intersection = " and ".join(re.split(r'\s+and\s+|\s*&\s*', intersection_candidate, flags=re.IGNORECASE))
            text = text[:near_match.start()].strip()
        
        if not intersection and re.search(r'\b(and|&)\b', text, re.IGNORECASE):
            intersection = " and ".join(re.split(r'\s+and\s+|\s*&\s*', text, flags=re.IGNORECASE))
            address = None
        else:
            address = text.strip()
            # Strip any leading call descriptors (e.g. "smoldering 2911 Lougheed" -> "2911 Lougheed")
            digit_match = re.search(r'\b\d+\b', address)
            if digit_match:
                address = address[digit_match.start():].strip()

    units_str = ", ".join(units) if units else None

    def title_case_location(loc_str: Optional[str]) -> Optional[str]:
        if not loc_str:
            return None
        words = loc_str.split()
        capitalized = [w.capitalize() if w.lower() not in ["and", "near", "of", "or"] else w for w in words]
        return " ".join(capitalized)

    return DispatchData(
        raw_text=original_normalized,
        units=units_str,
        response_type=response_type,
        call_type=incident_type,
        address=title_case_location(address),
        intersection=title_case_location(intersection),
        radio_channel=radio_channel,
        map_grid=map_grid,
        subaddress=title_case_location(subaddress)
    )