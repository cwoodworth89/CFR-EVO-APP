# cfr_dispatch/parser/__init__.py
"""Dispatch transcript parsing.

Split from a single 1053-line parser.py. This package re-exports the same public
names, so `from cfr_dispatch.parser import ...` continues to work unchanged for all
nine existing consumers.
"""

from .sanitize import sanitize_transcript
from .call_types import load_call_types, CALL_TYPES, match_incident_type
from .units import get_unit_abbreviation, abbreviate_units, merge_units
from .channels import match_radio_channel, clean_channel_name_for_output
from .location import (
    normalize_street_suffix,
    clean_location_text,
    extract_subaddress_info,
    split_street_base_suffix,
    fuzzy_correct_street,
    fuzzy_correct_cross_roads,
)
from .announcement import (
    parse_dispatch_announcement,
    split_rounds,
    reconstruct_template_transcript,
)

__all__ = [
    "sanitize_transcript",
    "load_call_types", "CALL_TYPES", "match_incident_type",
    "get_unit_abbreviation", "abbreviate_units", "merge_units",
    "match_radio_channel", "clean_channel_name_for_output",
    "normalize_street_suffix", "clean_location_text", "extract_subaddress_info",
    "split_street_base_suffix", "fuzzy_correct_street", "fuzzy_correct_cross_roads",
    "parse_dispatch_announcement", "split_rounds", "reconstruct_template_transcript",
]
