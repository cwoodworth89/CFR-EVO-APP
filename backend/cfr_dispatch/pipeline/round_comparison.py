# cfr_dispatch/pipeline/round_comparison.py
"""Cross-check the same dispatch as observed by Phase 1 and by each Phase 2 round.

WHY THIS EXISTS
---------------
Locution announces every call twice, and Phase 2 re-transcribes the whole recording, so
each field is observed more than once. Until now the pipeline compared exactly one thing --
string equality on the address between Phase 1 and the first Phase 2 candidate -- and a
match wrote a hardcoded confidence of 100.

**That is the least informative pairing available.** Phase 1 transcribes a partial buffer
and Phase 2 re-transcribes the full recording *containing that same audio*, through the
same Whisper model with the same parameters. They agree largely by construction, which is
why 389 of 510 records carried confidence 100 -- and a street misheard the same way twice
agrees with itself perfectly.

Round 1 against round 2 is a different question, because those are two separate utterances
by the dispatcher. Measured over the corpus on 2026-08-30, on 403 calls where both rounds
yielded an address:

    rounds agree     305 calls   5.3% rated FAILED   14.8% address corrected by operator
    rounds disagree   98 calls  14.1% rated FAILED   30.6% address corrected by operator

Disagreement triples the failure rate and doubles the correction rate while flagging only
24% of calls. That is the signal worth surfacing.

WHAT THIS MODULE DOES AND DOES NOT DO
-------------------------------------
It **reports** agreement per field. It does not choose a winner, and it must not: picking
between "29883 Robson Dr" and "2983 Robson Dr" programmatically means inventing a rule, and
an invented rule produces a plausible wrong answer that nobody can see (CLAUDE.md §6.1).
Disagreement is surfaced to the operator; the operator decides.

Filling a *blank* from another round is a different operation and is not arbitration --
that is `phase2._coalesce_across_rounds`, and it is deliberately kept separate.

NORMALISATION, AND WHY THERE ARE TWO LEVELS
-------------------------------------------
`docs/arrival_point_handoff.md` records that unnormalised diffs overstate error badly --
address error looked like 30.2% and was 16.8%. Two transcriptions of one utterance
rendering "Ave" and "Avenue" are not in disagreement about anything operational.

So location text is compared through `same_location_text`, which folds street-suffix
variants; everything else goes through `same_value`, which deliberately mirrors
`getVisibleChanges`/`sameValue` in `frontend/src/utils/dispatchModel.js` so the backend and
the kiosk cannot disagree about what counts as a change. Keep the two in step.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

# Source labels. P1 is the partial-buffer pass; P2R<n> are the rounds of the full-recording
# pass. Order matters only for reporting -- no source outranks another here.
SOURCE_PHASE_1 = "p1"


def source_for_round(index: int) -> str:
    """Label for the nth Phase 2 round, 0-based, as `split_rounds` returns them."""
    return f"p2r{index + 1}"


# Suffix folding for location text only. Taken from the forms that actually occur in
# `public.roads.roadtype` and in the announcements, not from a postal standard -- the
# street-suffix vocabulary in `public.vocabulary` is the authority for canonical forms
# (docs/standards/README.md, "Street suffix canonical forms"). This is a comparison aid,
# never a rewrite: nothing here is stored.
_SUFFIX_FOLD = {
    "avenue": "av", "ave": "av",
    "street": "st", "st": "st",
    "road": "rd", "rd": "rd",
    "drive": "dr", "dr": "dr",
    "crescent": "cr", "cres": "cr",
    "court": "ct", "crt": "ct", "ct": "ct",
    "place": "pl", "pl": "pl",
    "boulevard": "bl", "blvd": "bl",
    "highway": "hw", "hwy": "hw",
    "lane": "ln", "ln": "ln",
    "way": "wy", "wy": "wy",
    "close": "cl", "cl": "cl",
    "terrace": "tc", "terr": "tc",
}


def normalize_location_text(value: Any) -> str:
    """Fold a location string to a comparison key.

    Lower-cases, drops punctuation, collapses whitespace, and folds street-suffix
    variants so "Anson Ave" and "Anson Avenue" compare equal. Intersection separators
    (`and`, `&`) are dropped entirely and the remaining tokens sorted, so
    "Gordon and Christmas" and "Christmas & Gordon" are the same junction -- they are,
    and treating the announced order as a disagreement would bury the real ones.
    """
    if value is None:
        return ""
    text = re.sub(r"[^a-z0-9 ]", " ", str(value).lower())
    tokens = [_SUFFIX_FOLD.get(t, t) for t in text.split() if t and t not in ("and", "&")]
    return " ".join(sorted(tokens))


def same_value(a: Any, b: Any) -> bool:
    """Mirror of `sameValue` in frontend/src/utils/dispatchModel.js. Keep in step.

    `None`, `''` and a missing key all mean "not present" and must not read as a change.
    Numeric strings compare numerically, so '82' and 82 are the same map grid. Sequence
    order IS significant -- for `responding_units` it is the dispatch order, which the
    kiosk preserves deliberately.
    """
    if isinstance(a, (list, tuple)) or isinstance(b, (list, tuple)):
        ax = list(a) if isinstance(a, (list, tuple)) else []
        bx = list(b) if isinstance(b, (list, tuple)) else []
        if len(ax) != len(bx):
            return False
        return all(str(x or "").strip() == str(y or "").strip() for x, y in zip(ax, bx))

    an = "" if a is None else a
    bn = "" if b is None else b
    if an == "" and bn == "":
        return True
    if isinstance(an, (int, float)) or isinstance(bn, (int, float)):
        try:
            return float(an) == float(bn)
        except (TypeError, ValueError):
            pass
    return str(an).strip() == str(bn).strip()


def same_location_text(a: Any, b: Any) -> bool:
    """Equality for addresses, intersections and street names."""
    return normalize_location_text(a) == normalize_location_text(b)


def _x_street_key(candidate: Any) -> tuple:
    """XStreets as an ORDERED pair.

    Corrected 2026-08-30 on the operator's ruling. This previously sorted the pair and
    called order "not operationally meaningful" -- that was an inference, and it was
    wrong. Locution announces

        [address] NEAR [x_street_1] AND [x_street_2]

    so position is part of what was said, and either may be omitted. Sorting them hid
    a real disagreement: two rounds naming the same pair in different positions read as
    agreement when the parser had in fact assigned them differently.

    Position is preserved on both sides, so an absent first XStreet stays absent rather
    than being back-filled by the second.
    """
    return (normalize_location_text(getattr(candidate, "x_street_1", None)),
            normalize_location_text(getattr(candidate, "x_street_2", None)))


# (field name, how to read it from a candidate, how to compare two read values)
_FIELDS: tuple = (
    ("address",        lambda c: getattr(c, "address", None) or getattr(c, "intersection", None), same_location_text),
    ("x_streets",      _x_street_key,                                                            lambda a, b: a == b),
    ("subaddress",     lambda c: getattr(c, "subaddress", None),                                  same_value),
    ("units",          lambda c: getattr(c, "units", None),                                       same_value),
    ("map_grid",       lambda c: getattr(c, "map_grid", None),                                    same_value),
    ("radio_channel",  lambda c: getattr(c, "radio_channel", None),                               same_value),
    ("call_type",      lambda c: getattr(c, "call_type", None),                                   same_value),
    ("response_type",  lambda c: getattr(c, "response_type", None),                               same_value),
)

# Verdicts. These are deliberately four states rather than a boolean, because "the sources
# disagree" and "only one source ever saw this" are different situations and must not
# render to the operator the same way.
AGREE = "agree"        # two or more sources hold a value and they match
DISAGREE = "disagree"  # two or more sources hold a value and they differ
SINGLE = "single"      # exactly one source holds a value -- no corroboration available
ABSENT = "absent"      # no source holds a value


@dataclass(frozen=True)
class FieldComparison:
    name: str
    verdict: str
    values: dict          # {source: raw value}, only sources that held one
    corroborated_by: int  # how many sources held a value

    @property
    def is_flagged(self) -> bool:
        """Whether this field warrants an operator-facing warning."""
        return self.verdict == DISAGREE


@dataclass(frozen=True)
class RoundComparison:
    fields: dict = field(default_factory=dict)   # {field name: FieldComparison}
    sources: tuple = ()

    @property
    def disagreements(self) -> list:
        return [c for c in self.fields.values() if c.verdict == DISAGREE]

    @property
    def uncorroborated(self) -> list:
        return [c for c in self.fields.values() if c.verdict == SINGLE]

    @property
    def has_second_observation(self) -> bool:
        """False when only one source produced anything at all.

        A single-round call cannot be cross-checked, which is itself worth surfacing:
        the absence of a disagreement is not evidence of agreement.
        """
        return len(self.sources) > 1


def compare_observations(observations: Sequence[tuple]) -> RoundComparison:
    """Compare one dispatch as seen by each source.

    `observations` is a sequence of `(source_label, candidate)`, where candidate is a
    `DispatchData` (or anything exposing the same attributes). Sources holding no value
    for a field are simply absent from that field's `values`.

    Returns a report. It makes no decision and mutates nothing.
    """
    obs = [(s, c) for s, c in (observations or []) if c is not None]
    result = {}

    for name, read, equal in _FIELDS:
        values = {}
        for source, cand in obs:
            try:
                raw = read(cand)
            except Exception:  # a malformed candidate must not break the whole comparison
                raw = None
            if raw is None or raw == "" or raw == ():
                continue
            values[source] = raw

        if not values:
            verdict = ABSENT
        elif len(values) == 1:
            verdict = SINGLE
        else:
            items = list(values.values())
            verdict = AGREE if all(equal(items[0], v) for v in items[1:]) else DISAGREE

        result[name] = FieldComparison(
            name=name, verdict=verdict, values=values, corroborated_by=len(values)
        )

    return RoundComparison(fields=result, sources=tuple(s for s, _ in obs))


def observations_from_rounds(p1_candidate: Any, round_candidates: Iterable) -> list:
    """Build the observation list from Phase 1 and the per-round Phase 2 candidates.

    `round_candidates` is an iterable of per-round candidate lists, in the order
    `split_rounds` produced them. The first candidate in each round carrying a location is
    that round's observation, matching how Phase 2 already picks a candidate.
    """
    observations = []
    if p1_candidate is not None:
        observations.append((SOURCE_PHASE_1, p1_candidate))
    for index, candidates in enumerate(round_candidates or []):
        pick = next((c for c in (candidates or [])
                     if getattr(c, "address", None) or getattr(c, "intersection", None)), None)
        if pick is not None:
            observations.append((source_for_round(index), pick))
    return observations
