"""The talk group is the digit, or a venue's name; nothing else names a channel (#19a).

Six of the eight channels share the words "talk group" and "coquitlam". A heard fragment with
no digit and no venue word used to reach a fuzzy stage that scored those shared words and
returned whichever channel came first in the list. Pure: the real channel list, no database.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from cfr_dispatch.parser.channels import match_radio_channel  # noqa: E402

CHANNELS = ["Combined Venue Port Mann", "Combined Venue Transit System",
            "Talk Group 10 Combined Response Coquitlam", "Talk Group 5 Coquitlam",
            "Talk Group 6 Coquitlam", "Talk Group 7 Coquitlam", "Talk Group 8 Coquitlam",
            "Talk Group 9 Coquitlam"]


def test_the_digit_names_the_channel():
    assert match_radio_channel("10 combined response", CHANNELS) == "Talk Group 10 Combined Response Coquitlam"
    assert match_radio_channel("5", CHANNELS) == "Talk Group 5 Coquitlam"
    assert match_radio_channel("6 coquitlam", CHANNELS) == "Talk Group 6 Coquitlam"


def test_combined_response_alone_is_still_channel_10():
    # The digit was lost but the phrase belongs to one channel only.
    assert match_radio_channel("combined response", CHANNELS) == "Talk Group 10 Combined Response Coquitlam"


def test_a_venue_is_named_by_its_own_words():
    assert match_radio_channel("combined venue port mann", CHANNELS) == "Combined Venue Port Mann"
    assert match_radio_channel("combined venue transit system", CHANNELS) == "Combined Venue Transit System"


def test_shared_words_alone_name_nothing():
    # "talk group" is in six channels; "combined venue" in two. Neither picks one.
    assert match_radio_channel("talk group", CHANNELS) is None
    assert match_radio_channel("coquitlam", CHANNELS) is None
    assert match_radio_channel("combined venue", CHANNELS) is None


def test_a_misheard_digit_is_unknown_not_a_guess():
    # "five" heard as "fine": the old fuzzy stage scored "talk group" and returned a channel.
    assert match_radio_channel("fine", CHANNELS) is None
    assert match_radio_channel("talk group fine", CHANNELS) is None


def test_a_digit_that_is_not_a_channel_is_unknown():
    assert match_radio_channel("12", CHANNELS) is None
    assert match_radio_channel("", CHANNELS) is None
