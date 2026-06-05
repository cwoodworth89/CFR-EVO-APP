# cfr_dispatch/parser.py
# Regex parsing, sanitization, and incident matching logic

import os
import regex as re
import logging
from typing import List
from word2number import w2n
from thefuzz import fuzz

from cfr_dispatch.config import (
    DispatchData,
    UNIT_PARSING_IGNORE_LIST,
    INVALID_NEXT_WORDS
)

def sanitize_transcript(text: str) -> str:
    """
    Cleans a transcript by converting to lowercase, mapping verbal numbers
    to digits, removing non-alphanumeric punctuation, and normalizing whitespace.
    """
    text = text.lower()

    number_words = {
        'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
        'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9',
        'ten': '10', 'eleven': '11', 'twelve': '12', 'thirteen': '13',
        'fourteen': '14', 'fifteen': '15', 'sixteen': '16', 'seventeen': '17',
        'eighteen': '18', 'nineteen': '19', 'twenty': '20'
    }

    # Replace whole word numbers with digits
    pattern = r'\b(' + '|'.join(number_words.keys()) + r')\b'
    text = re.sub(pattern, lambda m: number_words[m.group(0)], text)

    # Strip punctuation
    text = re.sub(r'[^a-z0-9\s]', '', text)
    
    # Trim and normalize spaces
    return ' '.join(text.split())

def load_call_types(filepath="call_types.txt") -> List[str]:
    """Loads and returns sorted call types list from a text file, longest first."""
    call_types = []
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
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
    # 1. Look for exact substring matches
    for ct in call_types:
        if ct.lower() in transcript:
            return ct
            
    # 2. Look for best fuzzy match
    best_match = None
    best_score = 0
    for ct in call_types:
        score = fuzz.token_set_ratio(ct.lower(), transcript)
        if score > best_score:
            best_score = score
            best_match = ct
            
    if best_score >= 80:
        return best_match
    return "Unknown Incident"

def parse_alarm_level(transcript: str) -> int:
    """Parses and returns alarm level (1, 2, or 3) from the transcript text."""
    match = re.search(r'\balarm\s*(?:level)?\s*(\d)\b', transcript, re.IGNORECASE)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    return 1

def abbreviate_units(units_str: str) -> List[str]:
    """Formats raw unit names into apparatus abbreviation codes (e.g. Engine 1 -> E1)."""
    if not units_str:
        return []
        
    mapping = {
        "engine": "E", "ladder": "L", "rescue": "R", "car": "C",
        "squad": "S", "medic": "M", "quint": "Q", "tender": "T",
        "hazmat": "H", "light attack vehicle": "LAV"
    }
    
    found_units = []
    # Search for unit types followed by a number
    matches = re.findall(
        r'\b(engine|ladder|rescue|car|squad|medic|quint|tender|hazmat|light attack vehicle)\s+([\w\d-]+)\b',
        units_str.lower()
    )
    for unit_type, unit_num in matches:
        abbr = mapping.get(unit_type, unit_type.capitalize())
        found_units.append(f"{abbr}{unit_num.upper()}")
        
    return found_units

def normalize_street_suffix(text: str) -> str:
    """Normalizes and capitalizes street type suffixes to standardized casings (e.g., Crescent -> Cres)."""
    type_mapping = {
        "crescent": "Cres", "cres": "Cres",
        "highway": "Hwy", "hwy": "Hwy",
        "street": "St", "st": "St",
        "avenue": "Ave", "ave": "Ave",
        "court": "Crt", "crt": "Crt",
        "place": "Pl", "pl": "Pl",
        "drive": "Dr", "dr": "Dr",
        "boulevard": "Blvd", "blvd": "Blvd",
        "lane": "Ln", "ln": "Ln",
        "road": "Rd", "rd": "Rd"
    }
    words = text.split()
    if not words:
        return text
        
    last_word = words[-1].lower()
    if last_word in type_mapping:
        words[-1] = type_mapping[last_word]
    else:
        words[-1] = words[-1].capitalize()
        
    for i in range(len(words) - 1):
        words[i] = words[i].capitalize()
        
    return " ".join(words)

def clean_location_text(text: str, call_types: List[str], units_vocab: List[str]) -> str:
    """
    Cleans a location candidate string by recursively stripping leading prepositions,
    action/dispatch keywords, unit vocabulary terms, and incident call types.
    """
    text = ' '.join(text.split()).strip()
    if not text:
        return ""
        
    prepositions = {"at", "near", "on", "for", "in", "to", "and"}
    action_words = {"respond", "routine", "emergency", "alarm", "activated", "level", "map", "grid"}
    
    call_type_phrases = []
    if call_types:
        for ct in call_types:
            ct_clean = re.sub(r'[^a-z0-9\s]', '', ct.lower()).strip()
            if ct_clean:
                call_type_phrases.append(ct_clean)
                
    incident_words = {"fire", "medical", "rescue", "accident", "crash", "leak", "assist", "arrest", "mvi"}
    
    unit_words = set(u.lower() for u in units_vocab) if units_vocab else set()
    unit_words.update({"engine", "ladder", "squad", "medic", "rescue", "tender", "hazmat", "quint", "car", "command"})

    changed = True
    while changed:
        changed = False
        lower_text = text.lower()
        words = lower_text.split()
        if not words:
            break
            
        first_word = words[0]
        if first_word in prepositions or first_word in action_words or first_word in unit_words:
            text = text[len(first_word):].strip()
            changed = True
            continue
            
        if first_word.isdigit():
            if len(words) > 1 and (words[1] in action_words or words[1] in prepositions or words[1] in unit_words):
                text = text[len(first_word):].strip()
                changed = True
                continue
                
        for phrase in sorted(call_type_phrases, key=len, reverse=True):
            if lower_text.startswith(phrase):
                phrase_len = len(phrase)
                if phrase_len == len(text) or text[phrase_len].isspace():
                    text = text[phrase_len:].strip()
                    changed = True
                    break
        if changed:
            continue
            
        if first_word in incident_words:
            text = text[len(first_word):].strip()
            changed = True
            continue

    return text

def parse_dispatch_announcement(announcement_text: str, units_vocab: List[str]) -> List[DispatchData]:
    """
    Parses sanitized text for dispatch fields, including addresses, intersections, units,
    response priority types, and map response grids.
    """
    text = announcement_text.strip()
    street_types = r"street|avenue|drive|way|road|crescent|boulevard|place|court|highway|lane"
    
    unit_lookbehind = '|'.join(UNIT_PARSING_IGNORE_LIST)
    
    address_pattern = re.compile(
        fr"(?<!\b(?:{unit_lookbehind})s?\s\d+\s)" 
        fr"(?P<number_phrase>(?:\d+[\s-]*)+)\s+" 
        fr"(?P<street_name>(?:[a-zA-Z'-]+\s+){{0,4}}?)"
        fr"(?P<street_type>{street_types})"
        fr"(?! \s* (?:{INVALID_NEXT_WORDS}))",
        re.IGNORECASE | re.VERBOSE
    )
    
    address_matches = list(address_pattern.finditer(text))
    intersection_pattern = re.compile(
        fr"((?:[\w'-]+\s+){{0,4}}?(?:{street_types}))\s+and\s+((?:[\w'-]+\s+){{0,4}}?(?:{street_types}))",
        re.IGNORECASE
    )
    intersection_match = intersection_pattern.search(text)
    
    found_dispatches = []
    if address_matches:
        for match in address_matches:
            number_phrase = match.group('number_phrase').strip()
            cleaned_number = None
            
            try:
                cleaned_number = str(w2n.word_to_num(number_phrase))
                logging.debug(f"Successfully parsed number phrase '{number_phrase}' with word2number -> {cleaned_number}")
            except ValueError:
                digits_only = "".join(filter(str.isdigit, number_phrase))
                if digits_only:
                    cleaned_number = digits_only
                    logging.debug(f"word2number failed for '{number_phrase}', fell back to digit joining -> {cleaned_number}")

            if not cleaned_number:
                logging.warning(f"Could not parse a valid number from phrase: '{number_phrase}'. Skipping candidate.")
                continue

            raw_street = f"{match.group('street_name').strip()} {match.group('street_type')}"
            cleaned_street = clean_location_text(raw_street, CALL_TYPES, units_vocab)
            normalized_street = normalize_street_suffix(cleaned_street)
            
            if normalized_street:
                address_str = f"{cleaned_number} {normalized_street}"
                found_dispatches.append(DispatchData(raw_text=text, address=address_str))
                
    if not found_dispatches and intersection_match:
        leg1 = clean_location_text(intersection_match.group(1), CALL_TYPES, units_vocab)
        leg2 = clean_location_text(intersection_match.group(2), CALL_TYPES, units_vocab)
        normalized_leg1 = normalize_street_suffix(leg1)
        normalized_leg2 = normalize_street_suffix(leg2)
        if normalized_leg1 and normalized_leg2:
            intersection_str = f"{normalized_leg1} and {normalized_leg2}"
            found_dispatches.append(DispatchData(raw_text=text, intersection=intersection_str))
            
    if not found_dispatches:
        return []

    units_pattern = re.compile(r'^(?P<units>(?:(?:' + '|'.join(units_vocab) + r')\s+[\w\d-]+[,\s]*)+)', re.IGNORECASE)
    response_pattern = re.compile(r'\brespond\s*(?P<type>routine|emergency)\b', re.IGNORECASE)
    map_grid_pattern = re.compile(r'\b(?:map grid|math grade|math grid)\s*(\d{1,3})\b', re.IGNORECASE)
    final_grid_pattern = re.compile(r'coquitlam\s*(\d{1,3})\b', re.IGNORECASE)
    
    units_str = (units_pattern.search(text).group('units').strip() if units_pattern.search(text) else None)
    response_str = (response_pattern.search(text).group('type').strip() if response_pattern.search(text) else None)
    
    parsed_grids = map_grid_pattern.findall(text)
    final_grid_matches = final_grid_pattern.findall(text)
    if final_grid_matches:
        parsed_grids.extend(final_grid_matches)
    grid_str = parsed_grids[0] if parsed_grids else None
    
    for dispatch in found_dispatches:
        dispatch.units, dispatch.response_type, dispatch.map_grid = units_str, response_str, grid_str
        
    return found_dispatches
