"""Street name normalization, intersection key formation, and address parsing utilities."""
import re
from typing import Tuple, Optional
from dataclasses import dataclass

SUFFIX_MAPPINGS = {
    "AVENUE": "AVE", "AVE": "AVE",
    "STREET": "ST", "ST": "ST",
    "ROAD": "RD", "RD": "RD",
    "DRIVE": "DR", "DR": "DR",
    "BOULEVARD": "BLVD", "BLVD": "BLVD",
    "HIGHWAY": "HWY", "HWY": "HWY",
    "WAY": "WAY",
    "CRESCENT": "CRES", "CRES": "CRES",
    "COURT": "CRT", "CRT": "CRT",
    "PLACE": "PL", "PL": "PL",
    "LANE": "LN", "LN": "LN",
    "PROMENADE": "PROM", "PROM": "PROM",
    "RAMP": "RAMP",
    "ALLEY": "ALLEY",
}

INTERSECTION_SPLIT_REGEX = re.compile(
    r'\s+(?:and|&|/|near|at|@)\s+|\s*[/&@]\s*',
    re.IGNORECASE
)

@dataclass
class ParsedAddress:
    """Structured result of parsing a raw address string."""
    house: str | None
    street: str
    street_type: str
    raw: str
    has_block_indicator: bool = False  # True if original had 'block'/'blk'

def normalize_street_name(name: str) -> str:
    """Normalizes street name suffix to municipal abbreviation."""
    if not name:
        return ""
    clean = re.sub(r'[,.]', '', name.strip()).upper()
    clean = re.sub(r'\b(?:BLOCK|BLK|OF)\b', '', clean).strip()
    words = clean.split()
    if not words:
        return ""
    if len(words) > 1 and words[-1] in SUFFIX_MAPPINGS:
        words[-1] = SUFFIX_MAPPINGS[words[-1]]
    return " ".join(words)

def normalize_intersection_key(street1: str, street2: str) -> str:
    """Forms a canonical, alphabetically sorted intersection key."""
    s1 = normalize_street_name(street1)
    s2 = normalize_street_name(street2)
    streets = sorted([s1, s2])
    return f"{streets[0]} & {streets[1]}"

def split_intersection_parts(address_str: str) -> Tuple[str, str] | None:
    """Detects and extracts the two street components from an intersection query."""
    if not address_str:
        return None
    clean_addr = address_str.split(',')[0].strip()
    if not re.search(r'\b(?:and|&|/|near|at|@)\b', clean_addr, re.IGNORECASE) and not any(c in clean_addr for c in ['&', '/', '@']):
        return None
    parts = INTERSECTION_SPLIT_REGEX.split(clean_addr)
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) >= 2:
        return parts[0], parts[1]
    return None

def parse_house_and_street(clean_address: str) -> ParsedAddress | None:
    """Parses '3030 Gordon Ave' into structured components.
    Also handles '1000 block Ponderosa St' by flagging has_block_indicator."""
    if not clean_address:
        return None
    # Detect block indicator before stripping it
    has_block = bool(re.search(r'\b(block|blk)\b', clean_address, re.IGNORECASE))
    
    clean = re.sub(r'\b(number|num|unit|suite|apt|apartment|#)\s+\w+\b.*', '', clean_address, flags=re.IGNORECASE).strip()
    clean = re.sub(r'\b(block|blk|of)\b', '', clean, flags=re.IGNORECASE).strip()
    clean = ' '.join(clean.split())
    
    match = re.search(r'^(?P<number>\d+)\s+(?P<street>.*)', clean)
    if not match:
        return None
    
    house = match.group('number')
    street_raw = match.group('street').strip()
    
    words = street_raw.split()
    if len(words) > 1:
        street_type_raw = words[-1]
        street_name = ' '.join(words[:-1])
        norm_type = SUFFIX_MAPPINGS.get(street_type_raw.upper(), street_type_raw.upper())
    elif len(words) == 1:
        if words[0].upper() in SUFFIX_MAPPINGS:
            street_name = ''
            norm_type = SUFFIX_MAPPINGS[words[0].upper()]
        else:
            street_name = street_raw
            norm_type = ''
    else:
        street_name = street_raw
        norm_type = ''
    
    return ParsedAddress(
        house=house,
        street=street_name,
        street_type=norm_type,
        raw=street_raw,
        has_block_indicator=has_block
    )

def extract_near_street(address_str: str) -> str | None:
    """Extracts 'near X Street' clause from address, returns the cross street name."""
    if not address_str:
        return None
    near_match = re.search(r'\bnear\s+(.+?)(?:\s+use\b|\s+map\b|\s*$)', address_str, re.IGNORECASE)
    if near_match:
        return near_match.group(1).strip()
    return None
