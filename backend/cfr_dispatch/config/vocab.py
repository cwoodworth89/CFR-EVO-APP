import os
import re
import logging
from cfr_dispatch.config.paths import VOCAB_DIR

def load_vocabulary_file(filename: str) -> list[str]:
    """Fallback: load from .txt file on disk."""
    filepath = VOCAB_DIR / filename
    items = []
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    items.append(line)
    return items

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
        logging.warning(f"Failed to load vocabulary '{category}' from DB, falling back to file: {e}")
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
        logging.warning(f"Failed to load streets from DB, falling back to file: {e}")
        return []

# Load with DB-first, file fallback
UNITS_VOCAB_RAW = load_vocabulary_from_db('unit') or load_vocabulary_file('units_vocabulary.txt')
RESPONSE_TYPES = load_vocabulary_from_db('response_type') or load_vocabulary_file('response_types.txt')
RADIO_CHANNELS = load_vocabulary_from_db('radio_channel') or load_vocabulary_file('radio_channels.txt')
MAP_GRIDS = load_vocabulary_from_db('map_grid') or load_vocabulary_file('map_grid_numbers.txt')
CALL_TYPES = sorted(load_vocabulary_from_db('call_type') or load_vocabulary_file('call_types.txt'), key=len, reverse=True)
COQUITLAM_STREETS = (
    load_streets_from_db()
    or load_vocabulary_file('top_streets.txt')
    or load_vocabulary_file('coquitlam_streets.txt')
)


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
