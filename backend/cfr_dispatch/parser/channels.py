# cfr_dispatch/parser/channels.py
# Radio talkgroup / channel matching and display formatting.

import regex as re
from typing import List, Optional
from thefuzz import fuzz

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
            
    # PROVENANCE REQUIRED (CLAUDE.md §6.3): 75 is an inherited cutoff with no cited
    # source. Failing it returns None (channel unknown) rather than a guessed channel.
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
