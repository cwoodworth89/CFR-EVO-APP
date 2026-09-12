"""The talk group is the digit, or the channel accounting for most of what was heard.

The eight channels share "coquitlam", and three share "combined response", so no channel but
a numbered one has a word of its own. A fragment is matched by overlap and an equal split is
unknown -- nothing is named by list order, and nothing by a margin it does not have.

Note what the corpus actually says: the dispatcher announces "combined response venue port
mann" (DISP-2026-07CC85, and the operator's verified transcript of DISP-2026-B772D2). The
vocabulary had "Combined Venue Port Mann", missing "Response" -- the list was wrong and the
STT was right. Whisper's real failure here is the opposite one: it drops the "10" from
channel 10 on about 9 % of those calls, which is why a rule needing a word no other channel
carries cannot work.

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


def test_bare_combined_response_is_unknown():
    """Operator ruling 2026-09-11 (#79), 10 calls of 584.

    Degraded to just these two words, the fragment names channel 10 and Port Mann equally.
    Channel 10 being 460 calls to Port Mann's 2 is not evidence about the call in hand, so
    the answer is unresolved rather than a frequency guess. Unresolved is not the same fact
    as "the dispatcher announced no talk group", which is a valid dispatch -- the pipeline
    conflates them today, punch list #80.
    """
    assert match_radio_channel("combined response", CHANNELS) is None


def test_a_venue_is_named_by_its_own_words():
    assert match_radio_channel("combined response venue port mann", CHANNELS) == "Combined Response Venue Port Mann"
    assert match_radio_channel("combined response venue transit system", CHANNELS) == "Combined Response Venue Transit System"
    # And still when the STT drops "response" rather than the digit.
    assert match_radio_channel("combined venue port mann", CHANNELS) == "Combined Response Venue Port Mann"
    assert match_radio_channel("combined venue transit system", CHANNELS) == "Combined Response Venue Transit System"


def test_shared_words_alone_name_nothing():
    # "coquitlam" is in six channels; "combined" in three; "combined venue" in two.
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
                 "combined response venue port man", "5", "coquitlam", "fine"]
    for frag in fragments:
        answers = {match_radio_channel(frag, list(perm))
                   for perm in itertools.islice(itertools.permutations(VOCAB_ORDER), 200)}
        assert len(answers) == 1, f"{frag!r} depends on list order: {answers}"
