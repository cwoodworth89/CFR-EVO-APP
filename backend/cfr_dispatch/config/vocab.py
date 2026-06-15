# NOTE: For vocabulary lists, anchor keywords, and speech adaptation boosts, see:
#   - docs/call_structure.md
#   - docs/hardware_specification.md
import os
import re
from cfr_dispatch.config.paths import VOCAB_DIR

def load_vocabulary_file(filename: str) -> list[str]:
    filepath = VOCAB_DIR / filename
    items = []
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    items.append(line)
    return items

# Dynamic Vocabulary Loading
UNITS_VOCAB_RAW = load_vocabulary_file("units_vocabulary.txt")
RESPONSE_TYPES = load_vocabulary_file("response_types.txt")
RADIO_CHANNELS = load_vocabulary_file("radio_channels.txt")
MAP_GRIDS = load_vocabulary_file("map_grid_numbers.txt")
CALL_TYPES = sorted(load_vocabulary_file("call_types.txt"), key=len, reverse=True)

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
