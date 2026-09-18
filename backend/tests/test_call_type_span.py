"""The words the call type took are not left at the head of the address (DISP-2026-A018E9).

The record for DISP-2026-A018E9 (2026-09-18 21:09Z, E4) carried the right call type,
"Wildland Fire - Smouldering", and the wrong address, "Smoldering David Avenue And Genest
Way". The kiosk showed LOCATION UNRESOLVED for an intersection that public.intersections
holds. Two matchers had decided where the call type ends: match_incident_type, which knows
the recognition alias and names a misheard qualifier, and a substring loop of its own in
parser/announcement.py over the canonical spellings only. The loop stopped at "wildland
fire" and left "smoldering" in the address. A house number would have hidden it, because
announcement.py strips everything before the first digits; only an intersection address
is exposed, and DISP-2026-FC1B29 had already lost one the same way.

split_incident_type is now the one decision, and announcement.py takes its remainder.

The first test is the call as the STT wrote it, against the live vocabulary. The rest are
pure: a stand-in vocabulary, the alias present and absent (the 2026-09-11c migration says
no alias replaces the US spelling; the live table carries one -- both must work).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from cfr_dispatch.config import UNITS_VOCABULARY  # noqa: E402
from cfr_dispatch.parser import (  # noqa: E402
    parse_dispatch_announcement,
    reconstruct_template_transcript,
    sanitize_transcript,
    split_rounds,
)
from cfr_dispatch.parser.call_types import split_incident_type  # noqa: E402

# DISP-2026-A018E9, raw_transcript: one round, read twice.
ROUND = ("coquitlam engine 4 respond routine wildland fire smoldering david avenue and genest way "
         "near david avenue and genest way use talk group 5 coquitlam map grid 88")


def test_disp_2026_a018e9_keeps_the_qualifier_out_of_the_address():
    cands = []
    for seg in split_rounds(sanitize_transcript(ROUND + " " + ROUND), UNITS_VOCABULARY):
        cands.extend(parse_dispatch_announcement(seg, UNITS_VOCABULARY))
    assert len(cands) == 2, cands
    for d in cands:
        assert d.call_type == "Wildland Fire - Smouldering"
        assert d.address is None
        assert d.intersection == "David Avenue And Genest Way"
        assert (d.x_street_1, d.x_street_2) == ("David Avenue", "Genest Way")
    rebuilt = reconstruct_template_transcript(cands[0])
    assert "smoldering" not in rebuilt
    assert ", wildland fire - smouldering, david avenue and genest way, near david avenue and genest way," in rebuilt


TYPES = [
    "Wildland Fire",
    "Wildland Fire - Smouldering",
    "Wildland Fire - Small Area",
    "Medical Aid",
    "Medical Aid - Chest Pain",
    "Medical Aid - Overdose",
    "Medical Aid - Overdose Arrest",
    "Structure Fire",
    "Structure Fire - Detached Structure",
    "Assist",
]
ALIASES = {"wildland fire - smoldering": "Wildland Fire - Smouldering"}


def split(text, aliases=ALIASES):
    return split_incident_type(text, TYPES, aliases)


def test_the_alias_spelling_is_consumed_with_the_call_type():
    assert split("wildland fire smoldering david avenue and genest way") == \
        ("Wildland Fire - Smouldering", "david avenue and genest way")


def test_without_the_alias_the_named_qualifier_is_consumed():
    # The migration's stated state: no alias. The qualifier is named on the one-letter
    # difference, and the word it was named from goes with it.
    assert split("wildland fire smoldering david avenue and genest way", aliases={}) == \
        ("Wildland Fire - Smouldering", "david avenue and genest way")


def test_the_verbatim_qualified_term_is_consumed_whole():
    assert split("wildland fire smouldering david avenue and genest way") == \
        ("Wildland Fire - Smouldering", "david avenue and genest way")


def test_a_bare_category_takes_only_its_own_words():
    assert split("wildland fire david avenue and genest way") == \
        ("Wildland Fire", "david avenue and genest way")


def test_a_misheard_qualifier_before_a_house_number():
    """DISP-2026-A7BE29's phrasing: the pre-digit strip used to hide this one."""
    assert split("medical aid chest payne 1538 big leaf court") == \
        ("Medical Aid - Chest Pain", "1538 big leaf court")


def test_the_longer_qualifier_is_consumed_whole():
    assert split("medical aid overdose arrest 3030 gordon avenue") == \
        ("Medical Aid - Overdose Arrest", "3030 gordon avenue")


def test_a_street_word_is_not_taken_for_a_qualifier():
    assert split("structure fire main st and elm st") == ("Structure Fire", "main st and elm st")


def test_no_call_type_means_nothing_is_taken():
    assert split("1234 pinetree way") == (None, "1234 pinetree way")


def test_matching_is_on_whole_words():
    # "assist" is not found inside "assistance", which the old substring loop would have cut.
    assert split("assistance 12 main st") == (None, "assistance 12 main st")
