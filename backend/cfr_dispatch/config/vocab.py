import os
import re
import logging

def load_vocabulary_from_db(category: str) -> list[str]:
    """Load vocabulary terms from PostgreSQL by category."""
    try:
        from sqlalchemy import create_engine, text
        db_url = os.environ.get('DATABASE_URL', 'postgresql://cfr_user:cfr_password_2026@localhost:5432/cfr_dispatch')
        engine = create_engine(db_url)
        with engine.connect() as conn:
            rows = conn.execute(
                text('SELECT term FROM public.vocabulary WHERE category = :cat AND is_active = TRUE ORDER BY sort_order, term'),
                {'cat': category}
            ).fetchall()
            return [r[0] for r in rows]
    except Exception as e:
        logging.error(f"Failed to load vocabulary '{category}' from public.vocabulary: {e}")
        return []

def load_streets_from_db() -> list[str]:
    """Load road names from PostgreSQL public.road_names."""
    try:
        from sqlalchemy import create_engine, text
        db_url = os.environ.get('DATABASE_URL', 'postgresql://cfr_user:cfr_password_2026@localhost:5432/cfr_dispatch')
        engine = create_engine(db_url)
        with engine.connect() as conn:
            rows = conn.execute(
                text('SELECT road_name FROM public.road_names ORDER BY road_name')
            ).fetchall()
            return [r[0] for r in rows if r[0]]
    except Exception as e:
        logging.error(f"Failed to load street names from public.road_names: {e}")
        return []

# public.vocabulary and public.road_names are the single source of truth.
#
# There is deliberately NO runtime file fallback. The .txt files under
# data/vocabulary/ are one-time SEED data for import_gis_data.py step7 on a fresh
# install; they are not kept in sync afterwards. Falling back to them at runtime meant
# a database that was merely slow to start would silently arm the parser with stale
# vocabulary, and nothing would report it.
#
# If the vocabulary cannot be loaded, that is a hard failure. A parser running with an
# empty call-type list labels every dispatch "Unknown Incident" -- a silent, plausible
# wrong answer, which CLAUDE.md §6.1 exists to prevent.

def _require(category: str, terms: list[str]) -> list[str]:
    if not terms:
        raise RuntimeError(
            f"Vocabulary category '{category}' is empty or unreachable in public.vocabulary. "
            f"Refusing to start with degraded vocabulary -- the parser would silently "
            f"mislabel every dispatch. Check DATABASE_URL and that the cfr_postgres "
            f"container is healthy, then re-run "
            f"'python backend/scripts/import_gis_data.py' if the table needs seeding."
        )
    return terms

UNITS_VOCAB_RAW = _require('unit', load_vocabulary_from_db('unit'))
RESPONSE_TYPES = _require('response_type', load_vocabulary_from_db('response_type'))
RADIO_CHANNELS = _require('radio_channel', load_vocabulary_from_db('radio_channel'))
MAP_GRIDS = _require('map_grid', load_vocabulary_from_db('map_grid'))
CALL_TYPES = sorted(_require('call_type', load_vocabulary_from_db('call_type')), key=len, reverse=True)
COQUITLAM_STREETS = _require('road_names', load_streets_from_db())


# Extract base unit types dynamically from units_vocabulary.txt (e.g. "Engine 1" -> "Engine")
_types_set = set()
for _unit in UNITS_VOCAB_RAW:
    _match = re.match(r'^([a-zA-Z\s]+?)\s*\d*$', _unit)
    if _match:
        _types_set.add(_match.group(1).strip())
UNITS_VOCABULARY = sorted(list(_types_set)) if _types_set else [
    "Car", "Engine", "Hazmat", "Hazmat Tender", "Ladder", "Light Attack Vehicle", "Medic", "Quint", "Rescue", "Squad", "Tender"
]

UNIT_PARSING_IGNORE_LIST = UNITS_VOCABULARY + [
    "Queens" # Phonetic misspelling help for address parser
]

INVALID_NEXT_WORDS = r'respond|alarm|activated|crew|group'
