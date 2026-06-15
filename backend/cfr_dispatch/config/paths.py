import os
from pathlib import Path

# Resolve base agent/ directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Decoupled authoritative data paths
VOCAB_DIR = BASE_DIR / "data" / "vocabulary"
SHAPES_DIR = BASE_DIR / "data"
