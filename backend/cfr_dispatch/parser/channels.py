# cfr_dispatch/parser/channels.py
# Radio talkgroup / channel matching.

import regex as re
from typing import List, Optional, Set

# The word that separates the venue channels from the rest of the roster.
#
# PROVENANCE (CLAUDE.md 6.3, tier 4 -- department operational policy): operator, 2026-09-11.
# The roster is a number followed by "Coquitlam" ("5 Coquitlam" ... "10 Combined Response
# Coquitlam") or a venue ("Combined Response Venue Port Mann"). "Venue" is what tells them
# apart, so it is the first thing to look for once the number is gone.
#
# Verified against the rest of the domain before relying on it (7.3a) -- as a whole word it
# appears in 0 of public.road_names, 0 of public.parcels.street, 0 of every non-radio_channel
# vocabulary category, and in 2 of 624 raw transcripts, both of them the Port Mann calls.
# "Avenue" does not collide: it is a single token, so the word boundary excludes it.
VENUE_WORD = "venue"


def _tokens(text: str) -> Set[str]:
    return set(re.findall(r'[a-z0-9]+', (text or "").lower()))


def _best(heard: Set[str], candidates: dict) -> Optional[str]:
    """Of these channels, the one whose name accounts for most of what was heard.

    Only ever called on a partition the cascade has already narrowed, so this decides between
    channels of the same kind -- which venue, or which Coquitlam channel -- never across the
    roster. A tie is None: no channel is picked for being earlier in the list.
    """
    scored = sorted(((len(toks & heard), ch) for ch, toks in candidates.items()),
                    key=lambda pair: (-pair[0], pair[1]))
    if not scored or scored[0][0] == 0:
        return None
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None
    return scored[0][1]


def match_radio_channel(talk_group_raw: str, radio_channels: List[str]) -> Optional[str]:
    """The channel named by what was heard after "talk group", or None.

    The operator's cascade, 2026-09-11 -- the number first, then the venue word, and only
    then the words that remain:

      1. **A number.** Every Coquitlam channel is announced with one, and across 148 calls on
         channels 5, 6 and 7 the digit survived the STT every single time. If exactly one
         channel carries a heard digit, that is the channel and nothing else is consulted.
         Anything else -- no digit, a digit no channel carries ("12"), or two channels' digits
         at once because the fragment over-ran into the map grid -- is "unsure", and unsure
         falls through rather than giving up.
      2. **"Venue".** It appears in the venue channels and nowhere else in the domain (see
         VENUE_WORD). Heard, it restricts the answer to the venue channels; absent, it rules
         them out. This is the step that was missing: a venue channel used to have to outscore
         channel 10 across the whole roster, and it lost.
      3. **What is left**, within whichever group step 2 chose -- "port mann" against "transit
         system", or "combined response coquitlam" against the bare numbered channels.

    Because step 2 partitions before step 3 scores, a fragment Whisper has degraded to bare
    "combined response" resolves to channel 10: the venue channels are already excluded, and
    no numbered channel carries those words. That is the operator's ruling of 2026-09-11,
    taken on the measurement that it happens on 17 of 436 channel-10 calls (3.9 %), that all
    17 verify to channel 10, and that "venue" survived in both Port Mann calls on record. The
    residual risk is stated rather than hidden: if a Port Mann call ever loses all three of
    "venue port mann", a crew is sent to a bridge incident on the wrong net and cannot tell.
    Two calls is thin evidence and the ruling was made knowing it.

    Adding a channel needs no code here. A new venue is matched by step 3 on its own words as
    soon as it is in public.vocabulary; a new numbered channel by step 1.

    This replaces two rules that each failed the same way, by list order:

      * until 2026-09-06 (#19a), token_set_ratio over the words the channels share, which
        scores a subset at 100 (docs/standards/dependency-behaviour.md);
      * until 2026-09-11 (#79), "a word no other channel carries", which returned the first
        qualifying channel -- so "combined response venue port man" went to channel 10 for
        being listed sixth rather than seventh (DISP-2026-07CC85, DISP-2026-B772D2).

    A brief third rule, plain overlap across the whole roster, gave the same answers on the
    corpus but decided them by arithmetic rather than by anything nameable. The cascade is
    what the operator can read and check.

    None means *unresolved*, not *no channel*: a dispatch with no talk group is a valid
    dispatch and the pipeline does not yet tell the two apart (punch list #80). The return
    value is the vocabulary term verbatim, which is also the spoken form.
    """
    heard = _tokens(talk_group_raw)
    if not heard:
        return None

    channels = {ch: _tokens(ch) for ch in radio_channels}

    # 1. The number, when exactly one channel answers to it. A digit no channel carries
    #    ("12", or a map grid the extractor over-ran into) is not an answer, so the cascade
    #    goes on to the words. Two channels' digits at once is a contradiction rather than a
    #    near miss, and picking one of them would be the list-order guess this rule exists to
    #    stop -- the fragment is bad, and that is the finding.
    digits = {t for t in heard if t.isdigit()}
    if digits:
        named = [ch for ch, toks in channels.items() if digits & toks]
        if len(named) == 1:
            return named[0]
        if len(named) > 1:
            return None

    # 2. Venue or not. One of these groups is the answer; the other cannot be.
    venues = {ch: toks for ch, toks in channels.items() if VENUE_WORD in toks}
    if VENUE_WORD in heard:
        return _best(heard, venues)

    # 3. No venue word: the numbered channels. Their digit is gone (step 1 would have caught
    #    it), so only a channel with words beyond its number can still be named -- which is
    #    what "combined response" names, and why bare "coquitlam" stays unresolved.
    return _best(heard, {ch: toks for ch, toks in channels.items() if ch not in venues})
