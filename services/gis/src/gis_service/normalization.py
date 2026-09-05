"""Street name normalization, intersection key formation, and address parsing utilities."""
import re
from typing import Tuple, Optional
from dataclasses import dataclass

# Street suffix mappings live in public.vocabulary (category 'street_suffix'), not here.
#
# They were hardcoded in this module AND in extract_all_intersections_from_gis.py, and
# the two disagreed: the extractor wrote 'SUNSET SQ' into public.intersections while
# this module normalized an incoming dispatch to 'SUNSET SQUARE', so those intersections
# could never be found. This module was also missing 10 suffix types that occur in
# public.roads.roadtype, covering 26 real streets.
#
# The database is the single source of truth, matching the pattern already used for
# units, call types and radio channels (backend/cfr_dispatch/config/vocab.py). There is
# deliberately NO file fallback: a stale or partial suffix table silently mis-normalizes
# street names, which surfaces as an address that will not resolve rather than as an
# error, and nothing would report it (CLAUDE.md 6.1).
#
# Loaded lazily on first use rather than at import: this is a leaf utility imported by
# the parser, and an import-time database round trip makes import order load-bearing.

_SUFFIX_CACHE: dict | None = None


def _load_suffix_mappings() -> dict:
    """Load variant -> canonical street suffix mappings from public.vocabulary."""
    import os
    from sqlalchemy import create_engine, text
    db_url = os.environ.get('DATABASE_URL',
                            'postgresql://cfr_user:cfr_password_2026@localhost:5432/cfr_dispatch')
    engine = create_engine(db_url)
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT term, term_normalized FROM public.vocabulary
            WHERE category = 'street_suffix' AND is_active = TRUE
        """)).fetchall()
    return {r[0].strip().upper(): r[1].strip().upper() for r in rows if r[0] and r[1]}


def get_suffix_mappings() -> dict:
    """Cached accessor. Raises if the vocabulary is unreachable or empty."""
    global _SUFFIX_CACHE
    if _SUFFIX_CACHE is None:
        try:
            mappings = _load_suffix_mappings()
        except Exception as e:
            raise RuntimeError(
                "Could not load street suffix vocabulary from public.vocabulary "
                f"(category 'street_suffix'): {e}. Refusing to normalize street names "
                "against an unknown suffix set -- addresses would silently fail to "
                "resolve. Check DATABASE_URL and that cfr_postgres is healthy, then "
                "apply backend/migrations/2026-08-22_street_suffix_vocabulary.sql."
            ) from e
        if not mappings:
            raise RuntimeError(
                "public.vocabulary has no active 'street_suffix' rows. Apply "
                "backend/migrations/2026-08-22_street_suffix_vocabulary.sql."
            )
        _SUFFIX_CACHE = mappings
    return _SUFFIX_CACHE


def reset_suffix_cache() -> None:
    """Drop the cache so the next call re-reads the table (for tests and after edits)."""
    global _SUFFIX_CACHE
    _SUFFIX_CACHE = None


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
    has_block_indicator: bool = False  # set by parse_house_and_street; nothing reads it yet

def normalize_street_name(name: str) -> str:
    """Normalizes street name suffix to municipal abbreviation.

    Apostrophes are stripped because the municipal layers disagree with each other:
    public.parcels stores "Deer's Leap" while public.roads and public.road_names store
    "Deers Leap Place". Matching is exact on the street name, so 15 addressed parcels
    appeared to sit on a street with no centreline -- indistinguishable, on inspection,
    from a genuinely missing road (see docs/city_gis_data_register.md, closed item).

    Verified 2026-08-26: this is the ONLY apostrophe in any street name across parcels,
    roads, road_names and intersections, so stripping cannot collide two real streets.
    Both the ASCII apostrophe and the typographic one are removed, since a transcript or
    an operator correction may carry either.
    """
    if not name:
        return ""
    clean = re.sub(r"[,.'’]", '', name.strip()).upper()
    clean = re.sub(r'\b(?:BLOCK|BLK|OF)\b', '', clean).strip()
    words = clean.split()
    if not words:
        return ""
    mappings = get_suffix_mappings()
    if len(words) > 1 and words[-1] in mappings:
        words[-1] = mappings[words[-1]]
    return " ".join(words)

def title_address(text: str) -> str:
    """Title-case an address for display, without breaking apostrophes.

    str.title() capitalizes after every non-letter, so "Deer's Leap" becomes
    "Deer'S Leap" -- which is what the kiosk showed once apostrophe-bearing streets
    started resolving. The letter after an apostrophe that sits between two letters is
    part of the same word, so it stays lower case.

    Deliberately narrow: only the apostrophe case is repaired. Municipal street names
    also contain hyphens ("Mary Hill By-Pass"), where title-casing each part IS
    correct, so hyphens are left to str.title().
    """
    if not text:
        return ""
    return re.sub(r"(?<=[A-Za-z])(['’])([A-Za-z])",
                  lambda m: m.group(1) + m.group(2).lower(),
                  str(text).title())


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
        norm_type = get_suffix_mappings().get(street_type_raw.upper(), street_type_raw.upper())
    elif len(words) == 1:
        if words[0].upper() in get_suffix_mappings():
            street_name = ''
            norm_type = get_suffix_mappings()[words[0].upper()]
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
