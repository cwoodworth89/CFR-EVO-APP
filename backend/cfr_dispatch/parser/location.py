# cfr_dispatch/parser/location.py
# Street suffix normalisation, location text cleaning, subaddress extraction,
# and fuzzy street correction against the known-streets vocabulary.

import regex as re
from typing import List, Tuple, Optional
from thefuzz import fuzz

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
    # `&` is in the lookahead for the same reason `and` is: it separates two cross
    # streets, and without it the second one is stripped as trailing junk.
    #
    # Defence in depth only -- it does NOT fix the measured defect. In the live pipeline
    # `sanitize_transcript` runs first and now rewrites `&` to " and ", so no ampersand
    # reaches this function from the announcement path. That rewrite is the actual fix
    # for DISP-2026-AAFDB8 (2026-08-30). This guard exists so the bug does not come back
    # silently if some other caller passes unsanitised text.
    match = re.search(r'\b(' + street_types + r')\b(?!\s*&|\s+(?:and|near|cross\s+roads|cross\s+street|cross\s+of))\s+(.*)', text, re.IGNORECASE)
    if match:
        text = text[:match.end(1)].strip()

    return text

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
        
        # If the extracted subaddress contains "and" or "&" (indicating an intersection), bypass extraction
        if re.search(r'\b(and|&)\b|\s*&\s*', sub_val, re.IGNORECASE):
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
            
            # If the extracted subaddress contains "and" or "&" (indicating an intersection), bypass extraction
            if re.search(r'\b(and|&)\b|\s*&\s*', sub_val, re.IGNORECASE):
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

# Suffix equivalences, for deciding whether an announced suffix agrees with a municipal
# one. Canonical forms come from `public.roads.roadtype` via the street_suffix vocabulary
# (docs/standards/README.md, "Street suffix canonical forms") -- this map only decides
# equality, it never renames anything.
_SUFFIX_EQUIV = {
    "street": "st", "st": "st",
    "avenue": "ave", "ave": "ave",
    "drive": "dr", "dr": "dr",
    "road": "rd", "rd": "rd",
    "crescent": "cres", "cres": "cres",
    "boulevard": "blvd", "blvd": "blvd",
    "place": "pl", "pl": "pl",
    "court": "crt", "crt": "crt", "ct": "crt",
    "highway": "hwy", "hwy": "hwy",
    "lane": "ln", "ln": "ln",
    "way": "way", "wy": "way",
    "close": "cl", "cl": "cl",
    "gate": "gt", "gt": "gt",
}


def _same_suffix(a: str, b: str) -> bool:
    a, b = (a or "").strip().lower(), (b or "").strip().lower()
    if not a or not b:
        return False
    return _SUFFIX_EQUIV.get(a, a) == _SUFFIX_EQUIV.get(b, b)


def fuzzy_correct_street(street_name: str, known_streets: List[str]) -> str:
    """Fuzzy corrects a single street name against the known Coquitlam street names.

    `known_streets` holds FULL municipal names ("Christmas Way", "King Edward Street"),
    not bare bases -- the docstring used to say "base street names" and the code trusted
    that (CLAUDE.md §7.3a: the name is not the contract). It split the announced name into
    base + suffix, scored the **base** against those **full** names, and then re-appended
    the caller's suffix to the winner. So "Christmas Way" resolved to "Christmas Way Way"
    and "King Edward Street" to "King Edward Street Street" -- 10 of the 23 unmatched
    cross streets in the corpus were this, all of them real streets (punch-list #56).

    Now scores base against base and returns the **municipal** name, so the suffix comes
    from the authoritative record rather than from the transcript.
    """
    if not street_name or not known_streets:
        return street_name
    base, suffix = split_street_base_suffix(street_name)
    clean_base = base.strip().lower()
    clean_base = re.sub(r'^(?:near|at)\s+', '', clean_base, flags=re.IGNORECASE).strip()
    if not clean_base:
        return street_name

    # Short street names collide easily under fuzzy matching (e.g. "Oak" vs "Oaks"),
    # so they demand a stricter score.
    # PROVENANCE REQUIRED (CLAUDE.md §6.3): 90/75 and the 4-character boundary are
    # inherited and uncited. Failing the threshold returns the street name unchanged,
    # so a miss degrades to raw text rather than a wrong street.
    #
    # NOTE: 938 of the 1,079 real street names have a DIFFERENT real Coquitlam street
    # scoring >= 75, so this threshold separates almost nothing. Replacing this whole
    # function with the resolution path the main address already uses is punch-list #56;
    # this fix is the suffix bug only, and does not make the threshold safe.
    threshold = 90 if len(clean_base) <= 4 else 75

    best_match = None
    best_key = (-1, -1)
    for ks in known_streets:
        ks_base, ks_suffix = split_street_base_suffix(ks)
        score = fuzz.ratio(clean_base, ks_base.strip().lower())
        # Suffix agreement breaks ties, so "Pinetree Way" cannot be answered with
        # "Pinetree Close" -- both bases score 100 and the order of the vocabulary
        # would otherwise decide.
        key = (score, 1 if _same_suffix(suffix, ks_suffix) else 0)
        if key > best_key:
            best_key = key
            best_match = ks
    if best_key[0] >= threshold:
        # Municipal names are stored expanded ("Austin Avenue"); the parser's house form
        # is abbreviated ("Austin Ave"), and callers normalise before this runs rather
        # than after. Normalising the winner keeps the output shape exactly as it was, so
        # this change fixes the doubling and alters nothing else downstream.
        return normalize_street_suffix(best_match)
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
