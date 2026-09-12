"""A matched category then names its qualifier, or stays a bare category.

The exact-substring stage returns the longest call type that appears verbatim, so one
misheard word in the qualifier dropped the whole clause: "medical aid chest payne" contains
"medical aid" and not "medical aid chest pain", and the answer came back as bare
"Medical Aid" with the fuzzy stage never reached (DISP-2026-A7BE29, 2026-09-11).

The qualifier is now chosen among that category's own variants -- partition, then decide,
the same shape as the talk group in parser/channels.py. Scoring inside the partition is what
makes it safe: every sibling shares the category words, so only the qualifier separates them.

Pure: a stand-in vocabulary, no database.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from cfr_dispatch.parser.call_types import _name_the_qualifier  # noqa: E402

# Shaped like the real vocabulary: bare categories, qualified variants, a nested qualifier,
# and two variants where one qualifier is a prefix of the other.
TYPES = [
    "Medical Aid",
    "Medical Aid - Chest Pain",
    "Medical Aid - Back Pain",
    "Medical Aid - Cardiac Arrest",
    "Medical Aid - Overdose",
    "Medical Aid - Overdose Arrest",
    "Structure Fire",
    "Structure Fire - High Risk",
    "Compressed Gas Smell - Inside",
    "Compressed Gas Smell - Inside - High Risk",
    "Gas Leak",
]


def name(category, heard):
    return _name_the_qualifier(category, heard, TYPES)


def test_a_misheard_qualifier_is_still_named():
    """DISP-2026-A7BE29 -- the call this was built for. "payne" for "pain"."""
    assert name("Medical Aid", "medical aid chest payne 1538 big leaf court") == "Medical Aid - Chest Pain"


def test_a_clean_qualifier_is_named():
    assert name("Medical Aid", "medical aid cardiac arrest 12 main street") == "Medical Aid - Cardiac Arrest"


def test_no_qualifier_stays_a_bare_category():
    """161 of 601 verified calls (26.8 %) are announced with no qualifier. That is an answer."""
    assert name("Medical Aid", "medical aid 1538 big leaf court") == "Medical Aid"
    assert name("Medical Aid", "medical aid") == "Medical Aid"


def test_an_unrecognisable_qualifier_stays_a_bare_category():
    # Never reach for the nearest variant just because a word is there.
    assert name("Medical Aid", "medical aid zzzz qqqq 1538 big leaf court") == "Medical Aid"


def test_the_longer_qualifier_wins_when_both_fit():
    """"overdose arrest" accounts for more of what was heard than "overdose"."""
    assert name("Medical Aid", "medical aid overdose arrest 3030 gordon avenue") == "Medical Aid - Overdose Arrest"
    assert name("Medical Aid", "medical aid overdose 3030 gordon avenue") == "Medical Aid - Overdose"


def test_a_nested_qualifier_is_reached():
    assert name("Compressed Gas Smell - Inside",
                "compressed gas smell inside high risk 100 main street") == "Compressed Gas Smell - Inside - High Risk"


def test_a_category_with_no_variants_is_returned_unchanged():
    assert name("Gas Leak", "gas leak 100 main street") == "Gas Leak"


def test_similar_qualifiers_do_not_swap():
    """"back pain" and "chest pain" differ by one word and must not stand in for each other."""
    assert name("Medical Aid", "medical aid back pain 12 main street") == "Medical Aid - Back Pain"
    assert name("Medical Aid", "medical aid chest pain 12 main street") == "Medical Aid - Chest Pain"


def test_vocabulary_order_decides_nothing():
    import itertools
    heard = [("Medical Aid", "medical aid chest payne 1538 big leaf court"),
             ("Medical Aid", "medical aid overdose arrest 3030 gordon avenue"),
             ("Medical Aid", "medical aid 1538 big leaf court"),
             ("Medical Aid", "medical aid zzzz 1538 big leaf court")]
    for category, text in heard:
        answers = {_name_the_qualifier(category, text, list(perm))
                   for perm in itertools.islice(itertools.permutations(TYPES), 120)}
        assert len(answers) == 1, f"{text!r} depends on vocabulary order: {answers}"
