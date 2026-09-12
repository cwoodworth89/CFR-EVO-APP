"""The talk group is the digit, or the channel accounting for most of what was heard.

The eight channels share "coquitlam", and three of them share "combined". A fragment that
names no channel by a word only that channel carries is unknown (#19a). A fragment that
names two is decided by how much of it each accounts for, not by list order -- the defect
behind DISP-2026-07CC85 and DISP-2026-B772D2, where Whisper inserted "response" into
"combined venue port mann" and the venue channel lost to channel 10 for being listed first.

Pure: the real channel list, no database.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from cfr_dispatch.parser.channels import match_radio_channel  # noqa: E402

# The vocabulary terms verbatim, in an order that is not the vocabulary's -- nothing here
# may depend on where a channel sits in the list.
CHANNELS = ["Combined Venue Port Mann", "Combined Venue Transit System",
            "10 Combined Response Coquitlam", "5 Coquitlam", "6 Coquitlam",
            "7 Coquitlam", "8 Coquitlam", "9 Coquitlam"]

VOCAB_ORDER = ["5 Coquitlam", "6 Coquitlam", "7 Coquitlam", "8 Coquitlam", "9 Coquitlam",
               "10 Combined Response Coquitlam", "Combined Venue Port Mann",
               "Combined Venue Transit System"]


def test_the_digit_names_the_channel():
    assert match_radio_channel("10 combined response", CHANNELS) == "10 Combined Response Coquitlam"
    assert match_radio_channel("5", CHANNELS) == "5 Coquitlam"
    assert match_radio_channel("6 coquitlam", CHANNELS) == "6 Coquitlam"


def test_combined_response_alone_is_still_channel_10():
    # The digit was lost but the phrase belongs to one channel only.
    assert match_radio_channel("combined response", CHANNELS) == "10 Combined Response Coquitlam"


def test_a_venue_is_named_by_its_own_words():
    assert match_radio_channel("combined venue port mann", CHANNELS) == "Combined Venue Port Mann"
    assert match_radio_channel("combined venue transit system", CHANNELS) == "Combined Venue Transit System"


def test_shared_words_alone_name_nothing():
    # "coquitlam" is in six channels; "combined venue" in two. Neither picks one.
    assert match_radio_channel("coquitlam", CHANNELS) is None
    assert match_radio_channel("combined venue", CHANNELS) is None
    assert match_radio_channel("combined", CHANNELS) is None


def test_a_misheard_digit_is_unknown_not_a_guess():
    # "five" heard as "fine": the old fuzzy stage scored the shared words and returned a channel.
    assert match_radio_channel("fine", CHANNELS) is None
    assert match_radio_channel("talk group fine", CHANNELS) is None


def test_a_digit_that_is_not_a_channel_is_unknown():
    assert match_radio_channel("12", CHANNELS) is None
    assert match_radio_channel("", CHANNELS) is None


def test_two_channel_digits_in_one_fragment_is_unknown():
    # Not a reason to take whichever is listed earlier.
    assert match_radio_channel("5 10 combined", CHANNELS) is None


def test_an_inserted_word_does_not_outrank_the_channel_actually_named():
    """DISP-2026-07CC85 / DISP-2026-B772D2.

    Whisper put "response" into "combined venue port mann". That word belongs to channel 10
    and to nothing else, so both channels are in contention -- but the fragment carries three
    of Port Mann's words and one of channel 10's. Port Mann is the answer in either spelling
    of "mann", and in either list order.
    """
    for channels in (CHANNELS, VOCAB_ORDER, list(reversed(VOCAB_ORDER))):
        assert match_radio_channel("combined response venue port man", channels) == "Combined Venue Port Mann"
        assert match_radio_channel("combined response venue port mann", channels) == "Combined Venue Port Mann"


def test_list_order_decides_nothing():
    import itertools
    fragments = ["10 combined response", "combined response", "combined venue port mann",
                 "combined venue transit system", "combined response venue port man",
                 "5", "coquitlam", "fine"]
    for frag in fragments:
        answers = {match_radio_channel(frag, list(perm))
                   for perm in itertools.islice(itertools.permutations(VOCAB_ORDER), 200)}
        assert len(answers) == 1, f"{frag!r} depends on list order: {answers}"
