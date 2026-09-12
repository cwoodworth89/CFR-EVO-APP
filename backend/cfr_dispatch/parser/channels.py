# cfr_dispatch/parser/channels.py
# Radio talkgroup / channel matching.

import regex as re
from typing import List, Optional

def _tokens(text: str) -> List[str]:
    return re.findall(r'[a-z0-9]+', (text or "").lower())


def match_radio_channel(talk_group_raw: str, radio_channels: List[str]) -> Optional[str]:
    """The channel named by what was heard after "talk group", or None.

    A channel is named by its digit ("5", "10"), or by words only it carries ("response"
    for 10 Combined Response Coquitlam, "port"/"mann" for the Port Mann venue). Words the
    channels share -- "coquitlam", "combined", "venue" -- name nothing on their own, but
    they do break ties once a channel is in contention.

    Two order-dependencies have been removed here. Until 2026-09-06 (#19a) a fragment with
    no digit fell through to token_set_ratio over the shared words, which scores a subset at
    100 (docs/standards/dependency-behaviour.md) and returned whichever channel came first
    in the list. That stage was replaced by a uniquely-owned-word test which still returned
    the first channel in list order when more than one qualified -- so "combined response
    venue port man" (DISP-2026-07CC85: Whisper inserted "response" into "combined venue port
    mann") matched Combined Venue Port Mann on three words and 10 Combined Response Coquitlam
    on one, and channel 10 won for being sixth in the list rather than seventh.

    So a qualifying channel is now scored by how much of what was heard it accounts for, and
    a tie is None. Measured 2026-09-11 by replaying all 624 stored raw transcripts through
    the parser and diffing both rules over the 1029 fragments that reached this function:
    1026 identical, 3 changed, all 3 the Port Mann defect above. No fragment the first-in-list
    rule got right is decided differently.

    None is not a fallback -- the pipeline shows it as NO_TALK_GROUP, an unknown rather than
    a guess (CLAUDE.md 6.1). The return value is the vocabulary term verbatim, which is also
    the spoken form, so nothing downstream has to rewrite it.
    """
    raw_tokens = _tokens(talk_group_raw)
    if not raw_tokens:
        return None
    raw_set = set(raw_tokens)

    channel_tokens = {ch: _tokens(ch) for ch in radio_channels}

    # 1. A digit names the channel that carries it as a whole word. A digit no channel
    #    carries ("12") is a misread, not an invitation to match on the other words; two
    #    channels' digits in one fragment is ambiguity, not a reason to take the earlier one.
    raw_digits = {t for t in raw_tokens if t.isdigit()}
    if raw_digits:
        named = [ch for ch, toks in channel_tokens.items() if raw_digits & set(toks)]
        return named[0] if len(named) == 1 else None

    # 2. No digit: a channel is in contention only if the fragment carries a word that no
    #    other channel has. Among those, the one accounting for the most of what was heard
    #    wins -- shared words ("combined", "venue") are the tiebreak they are good for. An
    #    outright tie is unknown.
    owner_count = {}
    for toks in channel_tokens.values():
        for t in set(toks):
            owner_count[t] = owner_count.get(t, 0) + 1

    contenders = []
    for channel, toks in channel_tokens.items():
        unique = {t for t in toks if owner_count.get(t) == 1 and not t.isdigit()}
        if unique & raw_set:
            contenders.append((len(set(toks) & raw_set), channel))
    if not contenders:
        return None

    contenders.sort(key=lambda pair: (-pair[0], pair[1]))
    if len(contenders) > 1 and contenders[0][0] == contenders[1][0]:
        return None
    return contenders[0][1]
