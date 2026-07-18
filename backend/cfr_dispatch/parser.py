# cfr_dispatch/parser.py
# Regex parsing, sanitization, and incident matching logic
# NOTE: For dispatch template definitions and regex segmentation fields, see docs/call_structure.md

import os
import regex as re
import logging
from typing import List, Tuple, Optional
from word2number import w2n
from thefuzz import fuzz

from cfr_dispatch.config import (
    DispatchData,
    UNIT_PARSING_IGNORE_LIST,
    INVALID_NEXT_WORDS,
    CALL_TYPES,
    RESPONSE_TYPES,
    RADIO_CHANNELS,
    MAP_GRIDS,
    UNITS_VOCAB_RAW,
    UNITS_VOCABULARY
)

def sanitize_transcript(text: str) -> str:
    """
    Cleans a transcript by converting to lowercase, applying phonetic corrections,
    mapping verbal numbers to digits, removing non-alphanumeric punctuation,
    and normalizing whitespace.
    """
    text = text.lower()

    # Compress commas, hyphens, and spaces between consecutive digits (e.g., 296, 8 -> 2968, 3-1-0-5 -> 3105, 110 0 -> 1100)
    while True:
        new_text = re.sub(r'(\d+)\s*,\s*(\d+)', r'\1\2', text)
        if new_text == text:
            break
        text = new_text

    while True:
        new_text = re.sub(r'(\d+)\s*-\s*(\d+)', r'\1\2', text)
        if new_text == text:
            break
        text = new_text

    while True:
        new_text = re.sub(r'\b(\d+)\s+(\d+)\b', r'\1\2', text)
        if new_text == text:
            break
        text = new_text

    # Apply phonetic corrections for common mishearings in dispatch templates and names
    phonetic_corrections = {
        # Unit number homophones & Engine 1 mishearings
        r'\b(engine|ladder|rescue|car|squad|medic|quint|tender|hazmat)\s+won\b': r'\1 1',
        r'\b(engine|ladder|rescue|car|squad|medic|quint|tender|hazmat)\s+juan\b': r'\1 1',
        r'\b(engine|ladder|rescue|car|squad|medic|quint|tender|hazmat)\s+run\b': r'\1 1',
        r'\b(engine|ladder|rescue|car|squad|medic|quint|tender|hazmat)\s+on\b': r'\1 1',
        r'\b(engine|ladder|rescue|car|squad|medic|quint|tender|hazmat)\s+when\b': r'\1 1',
        r'\b(engine|ladder|rescue|car|squad|medic|quint|tender|hazmat)\s+to\b': r'\1 2',
        r'\b(engine|ladder|rescue|car|squad|medic|quint|tender|hazmat)\s+too\b': r'\1 2',
        r'\b(engine|ladder|rescue|car|squad|medic|quint|tender|hazmat)\s+two\b': r'\1 2',
        r'\b(engine|ladder|rescue|car|squad|medic|quint|tender|hazmat)\s+free\b': r'\1 3',
        r'\b(engine|ladder|rescue|car|squad|medic|quint|tender|hazmat)\s+three\b': r'\1 3',
        r'\b(engine|ladder|rescue|car|squad|medic|quint|tender|hazmat)\s+for\b': r'\1 4',
        r'\b(engine|ladder|rescue|car|squad|medic|quint|tender|hazmat)\s+four\b': r'\1 4',

        # Unit type STT mishearings
        r'\b(agent|ancient|angel|asian)\s+(\d+|1|2|3|4|5|one|two|three|four|five)\b': r'engine \2',

        # Responding units & Coquitlam mishearings
        r'\bcolquitt\s+loom\b': 'coquitlam',
        r'\bcorporate\s+loan\b': 'coquitlam',
        r'\bcocoa\b': 'coquitlam',
        r'\bcocoon\b': 'coquitlam',
        r'\bkirk\s+whitman\b': 'coquitlam',
        r'\bquickly\b': 'coquitlam',
        r'\bcopeland\b': 'coquitlam',
        r'\bpoit\s*loma\b': 'coquitlam',
        r'\bpoint\s+loma\b': 'coquitlam',
        r'\bhope\s+that\s+1\b': 'coquitlam',
        r'\bhope\s+that\s+one\b': 'coquitlam',
        r'\bpopoetal\b': 'coquitlam',
        r'\bhoquiam\b': 'coquitlam',
        r'\bcrazy\s+an\b': 'coquitlam',
        r'\bcoquit\s*loom\b': 'coquitlam',
        r'\bcoquina\b': 'coquitlam',
        r'\bpoke\s+with\s+them\b': 'coquitlam',
        r'\bhope\s+with\s+them\b': 'coquitlam',
        r'\bpoke\s+with\s+him\b': 'coquitlam',
        r'\bhope\s+with\s+him\b': 'coquitlam',
        
        # Unit corrections
        r'\bengines\b': 'engine',
        r'\bladders\b': 'ladder',
        r'\bmedics\b': 'medic',
        r'\bquints\b': 'quint',
        r'\brescues\b': 'rescue',
        r'\bsquads\b': 'squad',
        r'\bcars\b': 'car',
        r'\btenders\b': 'tender',
        r'\bqueens\s+(\d+)\b': r'quint \1',
        
        # Respond & Priority
        r'\brespawn(ed)?s?\b': 'respond',
        r'\bresponses?\s+(emergency|routine)\b': r'respond \1',
        r'\bresponse\s+(emergency|routine)\b': r'respond \1',
        r'\bresign\b': 'respond',
        r'\breson\b': 'respond',
        r'\bwe\s+found\b': 'respond',
        r'\brespondents\b': 'respond',
        r'\bresponder\b': 'respond',
        r'\bregency\b': 'emergency',
        r'\bmedley\b': 'medical aid',
        r'\bvan\s+ruitens?\b': 'routine',
        r'\bportman(n)?\b': 'port mann',
        r'\benramp\b': 'on-ramp',
        r'\bonramp\b': 'on-ramp',
        
        # Cross streets and roads
        r'\bcross\s+roads?\b': 'cross roads',
        r'\bcross\s+streets?\b': 'cross roads',
        r'\b(?:cross|across)\s+up\b': 'cross of',
        r'\b(?:cross|across)\s+ark\b': 'cross of',
        r'\b(?:cross|across)\s+of\b': 'cross of',
        
        # Talk Group (channel)
        r'\buse\s+tax\b': 'use talk group',
        r'\buse\s+tack\b': 'use talk group',
        r'\buse\s+tag\b': 'use talk group',
        r'\bnews\s+tack\b': 'use talk group',
        r'\bmens\s+table\b': 'use talk group',
        r'\btalk\s*groups?\b': 'talk group',
        r'\btorque\s+groups?\b': 'talk group',
        
        # Map Grid
        r'\bmath\s+grids?\b': 'map grid',
        r'\bmath\s+grades?\b': 'map grid',
        r'\bmap\s+grades?\b': 'map grid',
        r'\bmath\s+griff\b': 'map grid',
        
        # Street suffixes
        r'\bpresidents?\b': 'crescent',
        r'\bpresents?\b': 'crescent',
        r'\bpresence?\b': 'crescent',
        r'\btreat\b': 'street',
        
        # Specific major streets / locations
        r'\blow\s+heat\s+high\s*ways?\b': 'lougheed highway',
        r'\blow\s+heed\s+high\s*ways?\b': 'lougheed highway',
        r'\blove\s+heat\s+high\s*ways?\b': 'lougheed highway',
        r'\blough\s+head\s+high\s*ways?\b': 'lougheed highway',
        r'\bsharp\s+treat\b': 'sharpe street',
        r'\bwig\s+on\s+throught\b': 'wigham drive',
        r'\bburden\s+cart\b': 'burton court',
        r'\bbroke\s+mirror\b': 'brookmere',
        r'\bdo\s+we\s+need\s+from\s+growing\b': 'dewdney trunk road',
        r'\bdo\s+we\s+need\s+from\s+bro\b': 'dewdney trunk road',
        r'\bdo\s+we\s+need\s+from\b': 'dewdney trunk road',
        
        # Coquitlam / Quitlam mishearings and collapses
        r'\bquitlam\b': 'coquitlam',
        r'\bego\s+mountain\b': 'eagle mountain',
        r'\bcoquitlam\s+coquitlam\b': 'coquitlam',
        
        # Unit mishearings (e.g. water 1 -> ladder 1)
        r'\bwater\s+(\d+)\b': r'ladder \1',
    }
    for pattern, replacement in phonetic_corrections.items():
        text = re.sub(pattern, replacement, text)

    # Secondary sweep to collapse any remaining double occurrences of coquitlam
    text = re.sub(r'\b(coquitlam)\s+\1\b', r'\1', text, flags=re.IGNORECASE)

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

    # Strip punctuation except alphanumeric characters and spaces
    text = re.sub(r'[^a-z0-9\s]', '', text)
    
    # Join consecutive single digits separated by spaces (e.g. "4 2 8" -> "428")
    text = re.sub(r'\b(\d)\s+(?=\d\b)', r'\1', text)
    
    # Trim and normalize spaces
    return ' '.join(text.split())

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
            
    if best_score >= 80:
        return best_match
    return "Unknown Incident"

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
            found_units.append(f"{abbr}{unit_num.upper()}")
        else:
            logging.warning(f"Parsed unit '{raw_unit_name}' is not in ground-truth UNITS_VOCAB_RAW. Rejecting.")
            
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
                
    incident_words = {"fire", "medical", "rescue", "accident", "crash", "leak", "assist", "arrest", "mvi", "incident", "patients", "patient", "multiple"}
    
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

    # Strip trailing numbers, suite numbers, or building details after street type (unless followed by "and" / "near")
    # e.g., "Burlington Drive 105" -> "Burlington Drive", "Lougheed Highway Superstore" -> "Lougheed Highway"
    street_types = r"street|avenue|drive|way|road|crescent|boulevard|place|court|highway|lane|st|ave|rd|dr|ln|ct|blvd|hwy|wy"
    match = re.search(r'\b(' + street_types + r')\b(?!\s+(?:and|near|cross\s+roads|cross\s+street|cross\s+of))\s+(.*)', text, re.IGNORECASE)
    if match:
        text = text[:match.end(1)].strip()

    return text

def match_radio_channel(talk_group_raw: str, radio_channels: List[str]) -> Optional[str]:
    """Matches raw transcript text against ground-truth radio channels using substring or fuzzy logic."""
    if not talk_group_raw:
        return None
    raw_clean = talk_group_raw.strip().lower()
    if not raw_clean:
        return None
        
    # 1. Look for exact substring match first
    for channel in radio_channels:
        chan_clean = channel.strip().lower()
        if raw_clean in chan_clean:
            if raw_clean.isdigit():
                # For digit channels, ensure word boundary to prevent matching e.g. "5" with "15"
                if re.search(r'\b' + re.escape(raw_clean) + r'\b', chan_clean):
                    return channel
            else:
                return channel
                
    # 2. Look for digits inside raw text and see if it matches channel digit
    raw_digits = re.findall(r'\d+', raw_clean)
    if raw_digits:
        for digit in raw_digits:
            for channel in radio_channels:
                chan_clean = channel.strip().lower()
                # If channel has this digit as a word, e.g. "Talk Group 5" contains "\b5\b"
                if re.search(r'\b' + re.escape(digit) + r'\b', chan_clean):
                    return channel

    # 3. Fallback to fuzzy matching
    best_match = None
    best_score = 0
    for channel in radio_channels:
        chan_clean = channel.strip().lower()
        score = fuzz.token_set_ratio(raw_clean, chan_clean)
        if score > best_score:
            best_score = score
            best_match = channel
            
    if best_score >= 75:
        return best_match
        
    return None

def clean_channel_name_for_output(channel_name: str) -> str:
    """Removes redundant words like 'Coquitlam' and 'Talk Group' for clean storage/UI display."""
    # Remove "coquitlam" (case insensitive)
    cleaned = re.sub(r'(?i)\bcoquitlam\b', '', channel_name).strip()
    # Remove "talk group" (case insensitive) from start
    cleaned = re.sub(r'(?i)^\btalk\s*group\b', '', cleaned).strip()
    cleaned = cleaned.strip()
    return cleaned if cleaned else channel_name

def extract_subaddress_info(address_text: str) -> Tuple[str, Optional[str]]:
    """
    Given an address string, extracts trailing subaddress indicators (like unit, apartment, 
    suite, room, or business names) that always follow the main address.
    """
    if not address_text:
        return address_text, None

    suffixes = r"\b(?:street|st|avenue|ave|drive|drv|way|road|rd|crescent|cres|boulevard|blvd|place|pl|court|ct|highway|hwy|lane|ln|close|cl|gate|gt)\b"
    
    # Match suffix followed by any trailing words (business name, unit, station, etc.)
    match = re.search(fr'({suffixes})\s+(.+)$', address_text, re.IGNORECASE)
    if match:
        suffix_word = match.group(1)
        sub_val = match.group(2).strip()
        
        # Clean up any leftover punctuation or noise from subaddress
        sub_val = sub_val.rstrip(',- ').lstrip(',- ')
        
        # If the extracted subaddress contains "and" (indicating an intersection), bypass extraction
        if re.search(r'\band\b', sub_val, re.IGNORECASE):
            return address_text, None
        
        # Clean up main address (everything up to and including the suffix)
        idx = match.start() + len(suffix_word)
        cleaned_addr = address_text[:idx].strip()
        cleaned_addr = " ".join(cleaned_addr.split())
        cleaned_addr = cleaned_addr.rstrip(',- ').lstrip(',- ')
        
        # If the extracted subaddress is just a number (e.g. "105"), format as "Unit 105"
        if re.match(r'^#?\s*\d+$', sub_val):
            sub_val = f"Unit {sub_val.replace('#', '').strip()}"
            
        return cleaned_addr, sub_val.title()
    else:
        # Fallback: check for explicit subaddress prefixes like "number", "unit", "apt", "suite", "basement", "room" without suffix
        sub_pattern = r'\b(number|unit|apt|suite|basement|rm|room|#)\s*(\d+|\w+)?'
        sub_match = re.search(sub_pattern, address_text, re.IGNORECASE)
        if sub_match:
            sub_val = sub_match.group(0).strip()
            
            # If the extracted subaddress contains "and" (indicating an intersection), bypass extraction
            if re.search(r'\band\b', sub_val, re.IGNORECASE):
                return address_text, None
                
            cleaned_addr = address_text[:sub_match.start()].strip()
            cleaned_addr = " ".join(cleaned_addr.split())
            cleaned_addr = cleaned_addr.rstrip(',- ').lstrip(',- ')
            
            # Format bare digits (e.g. "# 105" -> "Unit 105")
            if re.match(r'^#?\s*\d+$', sub_val):
                sub_val = f"Unit {sub_val.replace('#', '').strip()}"
                
            return cleaned_addr, sub_val.title()

    return address_text, None

def split_street_base_suffix(street_text: str) -> Tuple[str, str]:
    """Splits a street name (e.g. 'Austin Ave') into ('Austin', 'Ave')."""
    words = street_text.strip().split()
    if not words:
        return "", ""
    suffixes = {"street", "st", "avenue", "ave", "drive", "dr", "road", "rd", 
                "crescent", "cres", "boulevard", "blvd", "place", "pl", 
                "court", "ct", "highway", "hwy", "lane", "ln", "way", "wy", "close", "cl", "gate", "gt"}
    if len(words) >= 2 and words[-1].lower() in suffixes:
        return " ".join(words[:-1]), words[-1]
    return street_text, ""

def fuzzy_correct_street(street_name: str, known_streets: List[str]) -> str:
    """Fuzzy corrects a single street name against a list of known Coquitlam base street names."""
    if not street_name or not known_streets:
        return street_name
    base, suffix = split_street_base_suffix(street_name)
    clean_base = base.strip().lower()
    clean_base = re.sub(r'^(?:near|at)\s+', '', clean_base, flags=re.IGNORECASE).strip()
    if not clean_base:
        return street_name
    
    # If base name is 4 characters or less, require higher match threshold to prevent collision errors
    threshold = 90 if len(clean_base) <= 4 else 75
    
    best_match = None
    best_score = 0
    for ks in known_streets:
        ks_lower = ks.strip().lower()
        score = fuzz.ratio(clean_base, ks_lower)
        if score > best_score:
            best_score = score
            best_match = ks
    if best_score >= threshold:
        corrected_street = best_match.title()
        if suffix:
            corrected_street = f"{corrected_street} {suffix.title()}"
        return corrected_street
    return street_name

def fuzzy_correct_cross_roads(cross_roads_text: str, known_streets: List[str]) -> str:
    """Corrects misspelled street names inside cross road intersections."""
    if not cross_roads_text or not known_streets:
        return cross_roads_text
    parts = re.split(r'\s+(?:and|at|&)\s+', cross_roads_text, flags=re.IGNORECASE)
    corrected_parts = []
    for part in parts:
        corrected_parts.append(fuzzy_correct_street(part, known_streets))
    return " and ".join(corrected_parts)

def parse_dispatch_announcement(announcement_text: str, units_vocab: List[str]) -> List[DispatchData]:
    """
    Parses sanitized text for dispatch fields, including addresses, intersections, units,
    response priority types, and map response grids. Attempts template-aligned anchor
    segmentation first, and falls back to standard regex parsing if necessary.
    """
    text = announcement_text.strip()
    
    # Normalize spaces
    text = ' '.join(text.split())
    
    street_types = r"street|avenue|drive|way|road|crescent|boulevard|place|court|highway|lane"
    
    # --- 1. Try Template-Aligned Anchor Segmentation ---
    # Template: [Units] respond [priority] [incident_type] [address] near/cross roads [cross_roads] use talk group [channel] map grid [grid]
    response_pattern_str = '|'.join(re.escape(rt.strip().lower()) for rt in RESPONSE_TYPES)
    respond_match = re.search(r'\brespond\s+(' + response_pattern_str + r')\b', text, re.IGNORECASE)
    if respond_match:
        try:
            respond_idx = respond_match.start()
            respond_len = len(respond_match.group(0))
            
            # Units segment: text preceding 'respond'
            units_segment = text[:respond_idx].strip()
            # Clean up trailing and leading "and" from units segment
            units_segment = re.sub(r'^(?:and\s+)+|(?:and\s*)+$', '', units_segment, flags=re.IGNORECASE).strip()
            
            # Remainder of the announcement after 'respond [priority]'
            remainder = text[respond_idx + respond_len:].strip()
            
            # Find boundary anchors
            cross_roads_match = re.search(r'\b(cross\s+roads|near|cross\s+street|cross\s+of)\b', remainder, re.IGNORECASE)
            talk_group_match = re.search(r'\b(use\s+talk\s+group|talk\s+group)\b', remainder, re.IGNORECASE)
            map_grid_match = re.search(r'\bmap\s+grid\b', remainder, re.IGNORECASE)
            
            # Determine end of Call Type + Address segment
            address_end_idx = len(remainder)
            if cross_roads_match:
                address_end_idx = min(address_end_idx, cross_roads_match.start())
            elif talk_group_match:
                address_end_idx = min(address_end_idx, talk_group_match.start())
            elif map_grid_match:
                address_end_idx = min(address_end_idx, map_grid_match.start())
                
            call_type_and_address_segment = remainder[:address_end_idx].strip()
            
            # Match Call Type within the segment to isolate the Address
            matched_call_type = None
            address_part = call_type_and_address_segment
            
            # Sort call types by length descending to match longest phrases first
            for ct in CALL_TYPES:
                ct_clean = sanitize_transcript(ct)
                if ct_clean in call_type_and_address_segment:
                    matched_call_type = ct
                    address_part = call_type_and_address_segment.replace(ct_clean, "").strip()
                    break
            else:
                # If call type didn't match exactly, isolate address by finding the first digits (house number)
                digit_match = re.search(r'\b\d+\b', call_type_and_address_segment)
                if digit_match:
                    address_part = call_type_and_address_segment[digit_match.start():].strip()
                    call_type_part = call_type_and_address_segment[:digit_match.start()].strip()
                    matched_call_type = match_incident_type(call_type_part, CALL_TYPES)
                else:
                    matched_call_type = "Unknown Incident"
            
            # If the isolated address still has text before the first digit (house number), strip it
            if address_part:
                digit_match = re.search(r'\b\d+\b', address_part)
                if digit_match:
                    pre_digit_text = address_part[:digit_match.start()].strip()
                    if pre_digit_text:
                        logging.info(f"Stripping pre-digit noise '{pre_digit_text}' from address '{address_part}'")
                        address_part = address_part[digit_match.start():].strip()
            
            # Clean and normalize isolated address
            address_part, extracted_subaddr = extract_subaddress_info(address_part)
            address_part = clean_location_text(address_part, CALL_TYPES, units_vocab)
            normalized_address = normalize_street_suffix(address_part)
            
            # Extract Cross Roads segment
            cross_roads_str = None
            if cross_roads_match:
                cross_roads_start = cross_roads_match.start() + len(cross_roads_match.group(0))
                cross_roads_end = len(remainder)
                if talk_group_match:
                    cross_roads_end = min(cross_roads_end, talk_group_match.start())
                elif map_grid_match:
                    cross_roads_end = min(cross_roads_end, map_grid_match.start())
                cross_roads_raw = remainder[cross_roads_start:cross_roads_end].strip()
                cross_roads_clean = clean_location_text(cross_roads_raw, CALL_TYPES, units_vocab)
                cross_roads_str = normalize_street_suffix(cross_roads_clean)
                try:
                    from cfr_dispatch.config.vocab import COQUITLAM_STREETS
                    if COQUITLAM_STREETS:
                        cross_roads_str = fuzzy_correct_cross_roads(cross_roads_str, COQUITLAM_STREETS)
                except Exception as ex:
                    logging.warning(f"Failed to fuzzy correct cross roads: {ex}")
                
            # Extract Talk Group (Radio channel)
            talk_group_str = None
            if talk_group_match:
                talk_group_start = talk_group_match.start() + len(talk_group_match.group(0))
                talk_group_end = len(remainder)
                if map_grid_match:
                    talk_group_end = min(talk_group_end, map_grid_match.start())
                talk_group_raw = remainder[talk_group_start:talk_group_end].strip()
                matched_chan = match_radio_channel(talk_group_raw, RADIO_CHANNELS)
                if matched_chan:
                    talk_group_str = clean_channel_name_for_output(matched_chan)
                    
            # Extract Map Grid
            map_grid_str = None
            if map_grid_match:
                map_grid_start = map_grid_match.start() + len(map_grid_match.group(0))
                map_grid_raw = remainder[map_grid_start:].strip()
                grid_digits = re.search(r'\d+', map_grid_raw)
                if grid_digits:
                    grid_val = grid_digits.group(0)
                    if grid_val in MAP_GRIDS:
                        map_grid_str = grid_val
                    else:
                        logging.warning(f"Parsed map grid '{grid_val}' is not in ground-truth MAP_GRIDS. Rejecting.")
                    
            is_intersection = bool(normalized_address and re.search(r'\band\b', normalized_address, re.IGNORECASE))
            dispatch = DispatchData(
                raw_text=text,
                units=units_segment if units_segment else None,
                response_type=respond_match.group(1).strip(),
                call_type=matched_call_type,
                address=normalized_address if normalized_address and not is_intersection else None,
                intersection=normalized_address if normalized_address and is_intersection else cross_roads_str,
                map_grid=map_grid_str,
                radio_channel=talk_group_str,
                subaddress=extracted_subaddr
            )
            
            if dispatch.address or dispatch.intersection:
                return [dispatch]
        except Exception as e:
            logging.warning(f"Template parsing failed: {e}. Falling back to regex parser.")

    # --- 2. Fallback to Standard Regex Parsing ---
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
                # Check for trailing subaddress right after the street type
                post_address_text = text[match.end():].strip()
                # Strip out any subsequent anchors (cross roads, talk group, map grid) to isolate the subaddress
                sub_clean = re.sub(r'\b(?:near|cross\s+roads|cross\s+street|cross\s+of|use\s+talk\s+group|talk\s+group|map\s+grid|math\s+grade|math\s+grid)\b.*', '', post_address_text, flags=re.IGNORECASE).strip()
                sub_clean = sub_clean.rstrip(',- ').lstrip(',- ')
                
                extracted_subaddr = sub_clean if sub_clean else None
                if extracted_subaddr and re.match(r'^#?\s*\d+$', extracted_subaddr):
                    extracted_subaddr = f"Unit {extracted_subaddr.replace('#', '').strip()}"
                
                found_dispatches.append(DispatchData(raw_text=text, address=address_str, subaddress=extracted_subaddr))
                
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

    # Sort units_vocab descending by length to support multi-word units correctly in the regex
    sorted_vocab = sorted(units_vocab, key=len, reverse=True)
    units_pattern = re.compile(r'^(?:coquitlam\s+)?(?P<units>(?:(?:' + '|'.join(re.escape(u) for u in sorted_vocab) + r')\s+[\w\d-]+[,\s]*)+)', re.IGNORECASE)
    response_pattern = re.compile(r'\brespond\s*(?P<type>' + response_pattern_str + r')\b', re.IGNORECASE)
    map_grid_pattern = re.compile(r'\b(?:map grid|math grade|math grid)\s*(\d{1,3})\b', re.IGNORECASE)
    final_grid_pattern = re.compile(r'coquitlam\s*(\d{1,3})\b', re.IGNORECASE)
    
    units_str = (units_pattern.search(text).group('units').strip() if units_pattern.search(text) else None)
    response_str = (response_pattern.search(text).group('type').strip() if response_pattern.search(text) else None)
    
    parsed_grids = map_grid_pattern.findall(text)
    final_grid_matches = final_grid_pattern.findall(text)
    if final_grid_matches:
        parsed_grids.extend(final_grid_matches)
    valid_grids = [g for g in parsed_grids if g in MAP_GRIDS]
    grid_str = valid_grids[0] if valid_grids else None
    
    # Look for talk group match in fallback text
    talk_group_pattern = re.compile(r'\b(?:use talk group|talk group)\s+(.+?)(?:\s+map grid|\s+math grade|\s+math grid|$)', re.IGNORECASE)
    tg_match = talk_group_pattern.search(text)
    fallback_tg_str = None
    if tg_match:
        matched_chan = match_radio_channel(tg_match.group(1), RADIO_CHANNELS)
        if matched_chan:
            fallback_tg_str = clean_channel_name_for_output(matched_chan)
            
    for dispatch in found_dispatches:
        dispatch.units = units_str
        dispatch.response_type = response_str
        dispatch.map_grid = grid_str
        dispatch.radio_channel = fallback_tg_str
        
    return found_dispatches


def split_rounds(text: str, units_vocab: List[str]) -> List[str]:
    """
    Splits a continuous transcript containing multiple announcement rounds into separate segments.
    Aligns with Coquitlam dispatch structures where the wake-word is not repeated.
    Splits by:
      1. Right after the first "map grid [digits]" phrase.
      2. Before the second occurrence of a responding unit followed by "respond".
    """
    # Normalize spaces
    text = ' '.join(text.strip().split())
    
    # 1. Split right after the first "map grid [digits/words]" (standard end of Round 1)
    # E.g. "map grid 12 Engine 1 respond..." -> splits after "map grid 12"
    grid_split = re.split(r'(?<=\bmap\s+grid\s+\w+\b)', text, maxsplit=1, flags=re.IGNORECASE)
    if len(grid_split) >= 2:
        return [grid_split[0].strip(), grid_split[1].strip()]
        
    # 2. Fallback: Split before the second occurrence of a unit followed by "respond"
    # E.g. "engine 1 respond... engine 1 respond..." -> splits before second "engine 1 respond"
    unit_pattern = '|'.join(re.escape(u.lower()) for u in units_vocab)
    matches = list(re.finditer(rf'\b({unit_pattern})\s+\d+\s+respond\b', text, flags=re.IGNORECASE))
    if len(matches) >= 2:
        split_idx = matches[1].start()
        return [text[:split_idx].strip(), text[split_idx:].strip()]
        
    return [text]


def reconstruct_template_transcript(dispatch: DispatchData) -> str:
    """
    Reconstructs a clean, standard, template-compliant transcript from parsed entities,
    expanding abbreviations to align verbally with the dispatcher's voice.
    """
    # 1. Expand Unit Names (e.g. E1 -> Engine 1, R2 -> Rescue 2)
    def expand_unit(u: str) -> str:
        u_clean = str(u).strip().upper()
        match = re.match(r'^([A-Z]+)(\d+)$', u_clean)
        if match:
            abbr, num = match.groups()
            name_map = {
                'E': 'Engine', 'R': 'Rescue', 'L': 'Ladder',
                'Q': 'Quint', 'M': 'Medic', 'S': 'Squad', 'B': 'Battalion'
            }
            full_name = name_map.get(abbr, abbr)
            return f"{full_name} {num}"
        return str(u).title()

    if dispatch.units:
        unit_list = dispatch.units if isinstance(dispatch.units, list) else [dispatch.units]
        units_part = ", ".join(expand_unit(u) for u in unit_list)
        # Strip any leading 'coquitlam' from units_part to avoid doubled-up "Coquitlam Coquitlam"
        units_part = re.sub(r'^(?:coquitlam\s+)+', '', units_part, flags=re.IGNORECASE).strip()
    else:
        units_part = "units"
        
    # 2. Priority
    resp = (dispatch.response_type or "routine").lower()
    priority_part = f"respond {resp}"
    
    # 3. Call Type
    call_type_part = (dispatch.call_type or "incident").lower()
        
    # 4. Address (Expand suffix abbreviations: e.g. pl -> place, cres -> crescent)
    def expand_address_suffix(addr: str) -> str:
        if not addr:
            return "address"
        suffix_map = {
            r'\bpl\b': 'place',
            r'\bcres\b': 'crescent',
            r'\bave\b': 'avenue',
            r'\bst\b': 'street',
            r'\brd\b': 'road',
            r'\bdr\b': 'drive',
            r'\bln\b': 'lane',
            r'\bct\b': 'court',
            r'\bblvd\b': 'boulevard',
            r'\bhwy\b': 'highway',
            r'\bwy\b': 'way'
        }
        addr_lower = addr.lower()
        for pattern, replacement in suffix_map.items():
            addr_lower = re.sub(pattern, replacement, addr_lower)
        return addr_lower

    if dispatch.address:
        address_part = expand_address_suffix(dispatch.address)
        if dispatch.subaddress:
            address_part = f"{address_part} {dispatch.subaddress.lower()}"
        intersection_part = f", near {expand_address_suffix(dispatch.intersection)}" if dispatch.intersection else ""
    elif dispatch.intersection:
        address_part = expand_address_suffix(dispatch.intersection)
        if dispatch.subaddress:
            address_part = f"{address_part} {dispatch.subaddress.lower()}"
        intersection_part = ""
    else:
        address_part = "address"
        intersection_part = ""
        
    # 6. Radio Channel (Map digital channels back to the full verbal name)
    chan = dispatch.radio_channel or "10 combined response coquitlam"
    if chan.strip() == "10" or "combined" in chan.lower():
        channel_part = "use talk group 10 combined response coquitlam"
    else:
        chan_lower = chan.lower()
        if "talk group" in chan_lower:
            channel_part = chan_lower
        else:
            channel_part = f"use talk group {chan_lower}"
            
        if not channel_part.endswith("coquitlam"):
            channel_part = f"{channel_part} coquitlam"
            
    # 7. Map Grid
    grid_part = f"map grid {dispatch.map_grid}" if dispatch.map_grid else "map grid"
        
    # Reconstruct transcript matching template punctuation/commas
    # Format: "Coquitlam [Units], respond [Priority], [Incident], [Address], [near Intersection], [Talk Group], [Map Grid]"
    reconstructed = f"Coquitlam {units_part}, {priority_part}, {call_type_part}, {address_part}{intersection_part}, {channel_part}, {grid_part}"
    
    return reconstructed

