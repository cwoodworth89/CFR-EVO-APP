# cfr_dispatch/parser/channels.py
# Radio talkgroup / channel matching and display formatting.

import regex as re
from typing import List, Optional

def _tokens(text: str) -> List[str]:
    return re.findall(r'[a-z0-9]+', (text or "").lower())


def match_radio_channel(talk_group_raw: str, radio_channels: List[str]) -> Optional[str]:
    """The channel named by what was heard after "talk group", or None.

    A channel is named by the token that sets it apart from the others: its digit ("5",
    "10"), or a word no other channel carries ("response" for 10 Combined Response, "port"
    for the Port Mann venue). Words the channels share -- "talk group", "coquitlam",
    "combined venue" -- name nothing on their own. Until 2026-09-06 (#19a) a fragment with
    no digit fell through to token_set_ratio over those shared words, which scores a subset
    at 100 (docs/standards/dependency-behaviour.md) and returned whichever channel came
    first in the list: "talk group fine" (five, misheard) became a confident channel. Now
    it is None, which the pipeline shows as NO_TALK_GROUP -- an unknown, not a guess
    (CLAUDE.md 6.1). Measured on the corpus before the change: every talk-group fragment
    with a digit or "combined response" resolved at the earlier stages; the fuzzy stage
    decided nothing that was right.
    """
    raw_tokens = _tokens(talk_group_raw)
    if not raw_tokens:
        return None

    channel_tokens = {ch: _tokens(ch) for ch in radio_channels}

    # 1. A digit names the channel that carries it as a whole word. A digit no channel
    #    carries ("12") is a misread, not an invitation to match on the other words.
    raw_digits = [t for t in raw_tokens if t.isdigit()]
    for digit in raw_digits:
        for channel, toks in channel_tokens.items():
            if digit in toks:
                return channel
    if raw_digits:
        return None

    # 2. A word that exactly one channel carries names that channel.
    counts = {}
    for toks in channel_tokens.values():
        for t in set(toks):
            counts[t] = counts.get(t, 0) + 1
    for channel, toks in channel_tokens.items():
        unique = {t for t in toks if counts.get(t) == 1 and not t.isdigit()}
        if unique & set(raw_tokens):
            return channel

    return None

def clean_channel_name_for_output(channel_name: str) -> str:
    """Removes redundant words like 'Coquitlam' and 'Talk Group' for clean storage/UI display."""
    # Remove "coquitlam" (case insensitive)
    cleaned = re.sub(r'(?i)\bcoquitlam\b', '', channel_name).strip()
    # Remove "talk group" (case insensitive) from start
    cleaned = re.sub(r'(?i)^\btalk\s*group\b', '', cleaned).strip()
    cleaned = cleaned.strip()
    return cleaned if cleaned else channel_name
