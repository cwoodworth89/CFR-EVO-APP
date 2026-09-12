# cfr_dispatch/parser/channels.py
# Radio talkgroup / channel matching.

import regex as re
from typing import List, Optional

def _tokens(text: str) -> List[str]:
    return re.findall(r'[a-z0-9]+', (text or "").lower())


def match_radio_channel(talk_group_raw: str, radio_channels: List[str]) -> Optional[str]:
    """The channel named by what was heard after "talk group", or None.

    A digit settles it outright. Otherwise the channel accounting for the most of what was
    heard wins, and a tie is None -- no channel is named by being earlier in the list, and
    none is named by a margin it does not have.

    Two earlier rules failed the same way, each replaced after the next call exposed it:

      * until 2026-09-06 (#19a) a fragment with no digit fell to token_set_ratio over the
        words the channels share, which scores a subset at 100
        (docs/standards/dependency-behaviour.md) and returned the first channel in the list;
      * until 2026-09-11 (#79) a channel had to be named by a word no other channel carried,
        and among those that qualified the first in the list won. "combined response venue
        port man" named two and channel 10 took it for being listed sixth rather than
        seventh (DISP-2026-07CC85, DISP-2026-B772D2).

    The unique-word gate is gone with it, because the corrected channel names break it:
    "Combined Response Venue Port Mann" and "10 Combined Response Coquitlam" share
    "combined" and "response", so channel 10 has no distinguishing word left that is not its
    digit -- and Whisper drops that digit on about 9 % of channel-10 calls (39 of 434,
    confirmed against the operator's own verified transcripts). Under a gate those calls
    resolve to nothing. Under plain overlap "combined response coquitlam" still names
    channel 10, on three words to Port Mann's two.

    What overlap cannot separate, it does not pretend to: a fragment degraded to bare
    "combined response" matches both channels equally and returns None. That is the
    operator's ruling of 2026-09-11 -- 10 calls of 584 -- taken over a frequency tiebreak,
    because channel 10 being 460 calls to Port Mann's 2 is not evidence about the call in
    hand (CLAUDE.md 6.1).

    None here means *unresolved*, not *no channel*. A dispatch with no talk group is a valid
    form of dispatch (operator, 2026-09-11) and 39 calls in the corpus carry no talk-group
    clause at all, against 12 that carry one this function could not read. The pipeline does
    not yet tell those apart -- both raise NO_TALK_GROUP and the kiosk hides the field either
    way, so a crew cannot see that a channel was announced and lost. Punch list #80.

    Measured 2026-09-11 by replaying all 624 stored raw transcripts through the parser and
    diffing per call: 572 of 584 unchanged, 2 corrected to Port Mann, 10 to NO_TALK_GROUP.
    tools/oneshot/2026-09-11_replay_channel_match.py.

    The return value is the vocabulary term verbatim, which is also the spoken form.
    """
    raw_tokens = _tokens(talk_group_raw)
    if not raw_tokens:
        return None
    raw_set = set(raw_tokens)

    channel_tokens = {ch: set(_tokens(ch)) for ch in radio_channels}

    # 1. A digit names the channel that carries it as a whole word. A digit no channel
    #    carries ("12") is a misread, not an invitation to match on the other words; two
    #    channels' digits in one fragment is ambiguity, not a reason to take the earlier one.
    raw_digits = {t for t in raw_tokens if t.isdigit()}
    if raw_digits:
        named = [ch for ch, toks in channel_tokens.items() if raw_digits & toks]
        return named[0] if len(named) == 1 else None

    # 2. No digit: the channel whose name accounts for most of what was heard, and only if
    #    it does so outright. Nothing in common is unknown; an equal split is unknown too.
    scored = sorted(((len(toks & raw_set), ch) for ch, toks in channel_tokens.items()),
                    key=lambda pair: (-pair[0], pair[1]))
    if scored[0][0] == 0:
        return None
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None
    return scored[0][1]
