# cfr_dispatch/parser.py
# Regex parsing, sanitization, and incident matching logic
# NOTE: For dispatch template definitions and regex segmentation fields, see docs/call_structure.md

import os
import regex as re
import logging
from typing import List
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

    # Apply phonetic corrections for common mishearings in dispatch templates and names
    phonetic_corrections = {
        # Unit number homophones
        r'\b(engine|ladder|rescue|car|squad|medic|quint|tender|hazmat)\s+to\b': r'\1 2',
        r'\b(engine|ladder|rescue|car|squad|medic|quint|tender|hazmat)\s+for\b': r'\1 4',

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
        r'\bqueens\s+(\d+)\b': r'quint \1',
        
        # Respond & Priority
        r'\brespawns?\b': 'respond',
        r'\bresponses?\b': 'respond',
        r'\bresign\b': 'respond',
        r'\breson\b': 'respond',
        r'\bwe\s+found\b': 'respond',
        r'\brespondents\b': 'respond',
        r'\bresponder\b': 'respond',
        r'\bregency\b': 'emergency',
        r'\bmedley\b': 'medical aid',
        r'\bvan\s+ruitens?\b': 'routine',
        
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
        
        # Street suffixes
        r'\bpresidents?\b': 'crescent',
        r'\bpresents?\b': 'crescent',
        r'\bpresence?\b': 'crescent',
        r'\btreat\b': 'street',
        
        # Specific major streets / locations
        r'\bsharp\s+treat\b': 'sharpe street',
        r'\bwig\s+on\s+throught\b': 'wigham drive',
        r'\bburden\s+cart\b': 'burton court',
        r'\bbroke\s+mirror\b': 'brookmere',
        r'\bdo\s+we\s+need\s+from\s+growing\b': 'dewdney trunk road',
        r'\bdo\s+we\s+need\s+from\s+bro\b': 'dewdney trunk road',
        r'\bdo\s+we\s+need\s+from\b': 'dewdney trunk road',
    }
    for pattern, replacement in phonetic_corrections.items():
        text = re.sub(pattern, replacement, text)

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
            
            # Clean and normalize isolated address
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
                    
            dispatch = DispatchData(
                raw_text=text,
                units=units_segment if units_segment else None,
                response_type=respond_match.group(1).strip(),
                call_type=matched_call_type,
                address=normalized_address if normalized_address and "and" not in normalized_address.lower() else None,
                intersection=normalized_address if normalized_address and "and" in normalized_address.lower() else cross_roads_str,
                map_grid=map_grid_str,
                radio_channel=talk_group_str
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

    # Sort units_vocab descending by length to support multi-word units correctly in the regex
    sorted_vocab = sorted(units_vocab, key=len, reverse=True)
    units_pattern = re.compile(r'^(?P<units>(?:(?:' + '|'.join(re.escape(u) for u in sorted_vocab) + r')\s+[\w\d-]+[,\s]*)+)', re.IGNORECASE)
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
    
    # 1. Split right after the first "map grid [digits]" (standard end of Round 1)
    # E.g. "map grid 12 Engine 1 respond..." -> splits after "map grid 12"
    grid_split = re.split(r'(?<=\bmap\s+grid\s+\d{1,3}\b)', text, maxsplit=1, flags=re.IGNORECASE)
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
