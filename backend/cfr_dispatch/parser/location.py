# cfr_dispatch/parser/location.py
# Street suffix normalisation, location text cleaning, and subaddress extraction.
#
# Street names are NOT corrected here. fuzzy_correct_street, fuzzy_correct_x_streets,
# split_street_base_suffix and _same_suffix were removed on 2026-09-11: punch-list #56
# moved cross streets onto the address's own resolution path on 2026-09-05 (89e25d4) --
# resolved against the roads near the placed address, and reported rather than rewritten
# -- and left these behind with no caller.
#
# They are not worth reviving. The threshold they ran on could not work: measured over
# the 1,079 municipal street names, 938 of them (86.9 %) have a DIFFERENT real Coquitlam
# street scoring >= 75 on fuzz.ratio, so accepting the best match above 75 separates
# almost nothing. Resolution belongs against PostGIS, which is the authority for what
# streets exist and where (CLAUDE.md 6.2).

import regex as re
from typing import List, Tuple, Optional

# Suffix equivalences: the one list the parser folds street types against, so "glen pine crt",
# "Glen Pine Crt" and "Glen Pine Court" all compare equal. Read by clean_location_text,
# _street_key and extract_subaddress_info -- it used to sit at the bottom of the file, below
# its own callers, next to the fuzzy matcher deleted on 2026-09-11.
#
# PROVENANCE (CLAUDE.md 6.3): canonical forms come from `public.roads.roadtype` via the
# street_suffix vocabulary (docs/standards/README.md, "Street suffix canonical forms"). This
# map only decides equality -- it never renames anything, and it is not the source of the
# canonical spelling.
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
    "drv": "dr",          # accepted by the old extractor regex; kept so nothing regresses
}


def normalize_street_suffix(text: str) -> str:
    """Normalizes and capitalizes street type suffixes to standardized casings (e.g., Crescent -> Cres)."""
    type_mapping = {
        "crescent": "Cres", "cres": "Cres",
        "highway": "Hwy", "hwy": "Hwy",
        "street": "St", "st": "St",
        "avenue": "Ave", "ave": "Ave",
        "court": "Crt", "crt": "Crt", "ct": "Crt",  # "ct" as typed in review, 2026-09-05 (#71)
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

def clean_location_text(text: str, call_types: List[str], units_vocab: List[str],
                        known_streets: Optional[List[str]] = None) -> str:
    """
    Cleans a location candidate string by recursively stripping leading prepositions,
    action/dispatch keywords, unit vocabulary terms, and incident call types.

    With `known_streets`, a house number followed by a municipal street name is returned
    as exactly that, before the trailing-junk strip below can cut it at its first suffix
    word -- which turned "1234 st laurence street" into "1234 st" even after
    extract_subaddress_info had split it correctly (measured on the kiosk, 2026-09-02).
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

    # A house number followed by a municipal street name is the whole answer. Return it
    # before the suffix-word strip below, which cannot tell "St" the street type from
    # "St" the first word of St Laurence Street.
    if known_streets:
        hit = _split_on_known_street(text, known_streets)
        if hit:
            return hit[0]

    # Strip trailing numbers, suite numbers, or building details after street type (unless followed by "and" / "near")
    # e.g., "Burlington Drive 105" -> "Burlington Drive", "Lougheed Highway Superstore" -> "Lougheed Highway"
    # From the one suffix list. The hand-typed copy this replaces lacked "crt" and "cres".
    street_types = "|".join(sorted(_SUFFIX_EQUIV, key=len, reverse=True))
    # `&` is in the lookahead for the same reason `and` is: it separates two cross
    # streets, and without it the second one is stripped as trailing junk.
    #
    # Defence in depth only -- it does NOT fix the measured defect. In the live pipeline
    # `sanitize_transcript` runs first and now rewrites `&` to " and ", so no ampersand
    # reaches this function from the announcement path. That rewrite is the actual fix
    # for DISP-2026-AAFDB8 (2026-08-30). This guard exists so the bug does not come back
    # silently if some other caller passes unsanitised text.
    # Strip at the LAST suffix word, not the first. "Gate" is a suffix (Windsor Gate), so
    # when the STT hears Agate Place as "a gate place and topas crt" the first-match strip
    # cut everything after "gate" and the kiosk showed "Near A Gate (as heard)" with Topaz
    # Court gone entirely: DISP-2026-5317C5, live, 2026-09-06. A suffix word followed by
    # text that itself holds a suffix word is a street name, not trailing junk.
    suffix_word = re.compile(r'\b(?:' + street_types + r')\b', re.IGNORECASE)
    for match in re.finditer(r'\b(' + street_types + r')\b(?!\s*&|\s+(?:and|near|cross\s+roads|cross\s+street|cross\s+of))\s+(.*)', text, re.IGNORECASE):
        if suffix_word.search(match.group(2)):
            continue
        text = text[:match.end(1)].strip()
        break

    return text

def _street_key(name: str) -> str:
    """Comparison form of a street name: lowercase, suffix folded to its canonical form,
    so 'glen pine crt' and 'Glen Pine Court' compare equal."""
    words = (name or "").strip().lower().split()
    if len(words) >= 2 and words[-1] in _SUFFIX_EQUIV:
        words[-1] = _SUFFIX_EQUIV[words[-1]]
    return " ".join(words)


_KNOWN_STREET_CACHE: dict = {}


def _known_street_keys(known_streets: List[str]):
    """(set of comparison keys, longest name in words) for a vocabulary list, cached."""
    hit = _KNOWN_STREET_CACHE.get(id(known_streets))
    if hit is None or hit[0] is not known_streets:
        keys = {_street_key(s) for s in known_streets if s}
        longest = max((len(k.split()) for k in keys), default=0)
        hit = (known_streets, keys, longest)
        _KNOWN_STREET_CACHE[id(known_streets)] = hit
    return hit[1], hit[2]


def _split_on_known_street(address_text: str, known_streets: List[str]):
    """'1200 glen pine crt glen pine pavilion' -> ('1200 glen pine crt', 'glen pine pavilion')
    using the LONGEST municipal street name that follows the house number. None if no
    municipal name matches -- a mis-heard street falls through to the suffix scan."""
    m = re.match(r'^\s*(\d+)\s+(.+)$', address_text.strip())
    if not m:
        return None
    house, rest = m.group(1), m.group(2)
    words = rest.split()
    keys, longest = _known_street_keys(known_streets)
    for n in range(min(len(words), longest), 0, -1):
        if _street_key(" ".join(words[:n])) in keys:
            return "%s %s" % (house, " ".join(words[:n])), " ".join(words[n:])
    return None


def extract_subaddress_info(address_text: str,
                            known_streets: Optional[List[str]] = None) -> Tuple[str, Optional[str]]:
    """
    Given an address string, extracts trailing subaddress indicators (like unit, apartment,
    suite, room, or business names) that always follow the main address.

    Two ways to find where the street ends, in order:

    1. The longest municipal street name after the house number (`known_streets`, i.e.
       COQUITLAM_STREETS). Authoritative (CLAUDE.md s6.2), and the only way to get
       "1234 St Laurence Street Unit 5" right -- a suffix scan sees "St" first and returns
       address "1234 St", subaddress "Laurence Street Unit 5". Measured 2026-09-02.
    2. The first suffix word, as before, when no municipal name matches (a mis-heard
       street). The suffix list is now _SUFFIX_EQUIV rather than a fourth hand-typed
       copy: the old copy lacked "crt", so "1200 glen pine crt Glen Pine Pavilion" was
       returned whole as the street -- and the fine-tuned model was trained on the
       operator's transcripts, which write "crt".
    """
    if not address_text:
        return address_text, None

    if known_streets:
        hit = _split_on_known_street(address_text, known_streets)
        if hit:
            cleaned_addr, sub_val = hit
            sub_val = sub_val.strip().rstrip(',- ').lstrip(',- ')
            if not sub_val:
                return cleaned_addr, None
            # "and" / "&" in the tail means this is an intersection, not a subaddress.
            if re.search(r'\b(and|&)\b|\s*&\s*', sub_val, re.IGNORECASE):
                return address_text, None
            if re.match(r'^#?\s*\d+$', sub_val):
                sub_val = f"Unit {sub_val.replace('#', '').strip()}"
            return cleaned_addr, sub_val.title()

    suffixes = r"\b(?:" + "|".join(sorted(_SUFFIX_EQUIV, key=len, reverse=True)) + r")\b"

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
