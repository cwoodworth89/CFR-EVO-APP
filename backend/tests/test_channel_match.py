"""The operator's cascade: the number, then "venue", then the words that remain.

The roster is a number plus "Coquitlam", or a venue. So the number decides it when there is
one -- across 148 calls on channels 5, 6 and 7 the digit survived the STT every time -- and
"venue" decides which half of the roster is in play when there is not. Only then do the
remaining words choose within that half. Nothing is ever decided by list order.

Note what the corpus actually says: the dispatcher announces "combined response venue port
mann" (DISP-2026-07CC85, and the operator's verified transcript of DISP-2026-B772D2). The
vocabulary had "Combined Venue Port Mann", missing "Response" -- the list was wrong and the
STT was right. Whisper's real failure is the opposite one: it drops the "10" from channel 10
on 8.5 % of those calls, and loses "coquitlam" with it on 3.9 %.

Pure: the real channel list, no database.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from cfr_dispatch.parser.channels import match_radio_channel  # noqa: E402

# The vocabulary terms verbatim, in an order that is not the vocabulary's -- nothing here
# may depend on where a channel sits in the list.
CHANNELS = ["Combined Response Venue Port Mann", "Combined Response Venue Transit System",
            "10 Combined Response Coquitlam", "5 Coquitlam", "6 Coquitlam",
            "7 Coquitlam", "8 Coquitlam", "9 Coquitlam"]

VOCAB_ORDER = ["5 Coquitlam", "6 Coquitlam", "7 Coquitlam", "8 Coquitlam", "9 Coquitlam",
               "10 Combined Response Coquitlam", "Combined Response Venue Port Mann",
               "Combined Response Venue Transit System"]


def test_the_digit_names_the_channel():
    assert match_radio_channel("10 combined response", CHANNELS) == "10 Combined Response Coquitlam"
    assert match_radio_channel("5", CHANNELS) == "5 Coquitlam"
    assert match_radio_channel("6 coquitlam", CHANNELS) == "6 Coquitlam"


def test_the_digit_is_dropped_but_coquitlam_still_names_channel_10():
    """Whisper loses the "10" on ~9 % of channel-10 calls; "coquitlam" carries it.

    Three words to Port Mann's two. This is why the unique-word gate had to go: with the
    corrected venue names, channel 10 owns no word but its digit.
    """
    assert match_radio_channel("combined response coquitlam", CHANNELS) == "10 Combined Response Coquitlam"


def test_bare_combined_response_is_channel_10():
    """Operator ruling 2026-09-11 (#79), on the measurement: 17 of 436 channel-10 calls
    (3.9 %) degrade this far and all 17 verify to channel 10.

    It falls out of the cascade rather than being special-cased: no "venue" rules the venue
    channels out, and no numbered channel carries these words. The risk the operator accepted
    is that a Port Mann call losing all three of "venue port mann" would land here -- "venue"
    survived in both Port Mann calls on record, which is two calls.
    """
    assert match_radio_channel("combined response", CHANNELS) == "10 Combined Response Coquitlam"


def test_coquitlam_alone_still_names_nothing():
    # Six channels carry it and the digit that separates them is gone.
    assert match_radio_channel("coquitlam", CHANNELS) is None


def test_a_venue_is_named_by_its_own_words():
    assert match_radio_channel("combined response venue port mann", CHANNELS) == "Combined Response Venue Port Mann"
    assert match_radio_channel("combined response venue transit system", CHANNELS) == "Combined Response Venue Transit System"
    # And still when the STT drops "response" rather than the digit.
    assert match_radio_channel("combined venue port mann", CHANNELS) == "Combined Response Venue Port Mann"
    assert match_radio_channel("combined venue transit system", CHANNELS) == "Combined Response Venue Transit System"


def test_a_venue_word_with_no_venue_named_is_unknown():
    # "venue" narrows to the two venue channels and then nothing chooses between them.
    assert match_radio_channel("combined venue", CHANNELS) is None
    assert match_radio_channel("combined response venue", CHANNELS) is None


def test_a_misheard_digit_is_unknown_not_a_guess():
    # "five" heard as "fine": the old fuzzy stage scored the shared words and returned a channel.
    assert match_radio_channel("fine", CHANNELS) is None
    assert match_radio_channel("talk group fine", CHANNELS) is None


def test_a_digit_no_channel_carries_falls_through_to_the_words():
    """"12" is a misread, not an answer -- but it is not a reason to abandon the fragment.

    The extractor can also over-run into the map grid, putting a stray number in front of a
    perfectly readable channel name (backlog, 2026-09-11).
    """
    assert match_radio_channel("12", CHANNELS) is None
    assert match_radio_channel("", CHANNELS) is None
    assert match_radio_channel("12 combined response venue port mann", CHANNELS) == "Combined Response Venue Port Mann"
    assert match_radio_channel("combined response coquitlam map grid 68", CHANNELS) == "10 Combined Response Coquitlam"


def test_two_channel_digits_in_one_fragment_is_unknown():
    # Not a reason to take whichever is listed earlier.
    assert match_radio_channel("5 10 combined", CHANNELS) is None


def test_the_venue_channel_outranks_channel_10_on_the_words_they_share():
    """DISP-2026-07CC85 / DISP-2026-B772D2, exactly as broadcast.

    "combined response" belongs to both, so the venue words decide it: five words to two.
    Correct in either spelling of "mann" -- Whisper wrote "man" on 07CC85 -- and in any list
    order, which is what the old rule got wrong.
    """
    for channels in (CHANNELS, VOCAB_ORDER, list(reversed(VOCAB_ORDER))):
        assert match_radio_channel("combined response venue port man", channels) == "Combined Response Venue Port Mann"
        assert match_radio_channel("combined response venue port mann", channels) == "Combined Response Venue Port Mann"


def test_list_order_decides_nothing():
    import itertools
    fragments = ["10 combined response", "combined response", "combined response coquitlam",
                 "combined venue port mann", "combined response venue transit system",
                 "combined response venue port man", "5", "coquitlam", "fine",
                 "combined venue", "12 combined response venue port mann"]
    for frag in fragments:
        answers = {match_radio_channel(frag, list(perm))
                   for perm in itertools.islice(itertools.permutations(VOCAB_ORDER), 200)}
        assert len(answers) == 1, f"{frag!r} depends on list order: {answers}"


def test_a_new_venue_channel_needs_no_code():
    """Adding a channel to public.vocabulary is enough -- step 2 finds it by "venue" and
    step 3 by its own words. The operator flagged Skytrain as a name still to verify."""
    extended = CHANNELS + ["Combined Response Venue Skytrain"]
    assert match_radio_channel("combined response venue skytrain", extended) == "Combined Response Venue Skytrain"
    assert match_radio_channel("combined response venue port mann", extended) == "Combined Response Venue Port Mann"
    assert match_radio_channel("combined response", extended) == "10 Combined Response Coquitlam"
