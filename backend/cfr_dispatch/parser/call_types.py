# cfr_dispatch/parser/call_types.py
# Incident/call type vocabulary loading and fuzzy matching.

import logging
import regex as re
from typing import List
from thefuzz import fuzz

def load_call_types(filepath: str = None) -> List[str]:
    """Returns the call-type vocabulary from public.vocabulary via the config layer.

    `filepath` is accepted for backwards compatibility with existing callers and is
    ignored; vocabulary has no runtime file fallback (see config/vocab.py).
    """
    from cfr_dispatch.config import CALL_TYPES as cfg_call_types
    return cfg_call_types


def load_call_type_aliases() -> dict:
    """Recognition-only spellings, keyed lowercased -> canonical term (see config/vocab.py)."""
    from cfr_dispatch.config import CALL_TYPE_ALIASES as cfg_aliases
    return cfg_aliases


# Module-level call-type vocabulary, resolved from public.vocabulary on import.
CALL_TYPES = load_call_types()
CALL_TYPE_ALIASES = load_call_type_aliases()


_RESPOND = re.compile(r'\brespond(?:\s+(?:emergency|routine))?\b', re.IGNORECASE)


def incident_search_text(transcript: str, units_vocabulary=None) -> str:
    """The part of an announcement the call type can legitimately be in (punch-list #34a).

    The template (docs/call_structure.md) is "coquitlam <units> respond <priority> <incident>
    <address> ...": the apparatus come before "respond", the call type after it. Four call
    types are also apparatus names, Rescue and Hazmat 1/2/3, so a search over the whole
    transcript reads "rescue 2" in the unit list as the incident whenever the STT has mangled
    the real one, and does so at full score: DISP-2026-A19179, an alarm call shown as Rescue.
    Two of 530 verified incidents on the corpus, 2026-09-05.

    After "respond [priority]" when it is there. When it is not, the unit tokens are blanked
    out and the rest is searched, so a garbled announcement can still yield its call type
    but never one made of its unit list.
    """
    if units_vocabulary is None:
        from cfr_dispatch.config import UNITS_VOCABULARY as units_vocabulary
    names = sorted((str(u) for u in units_vocabulary if str(u).strip()), key=len, reverse=True)
    unit_alt = '|'.join(re.escape(n) for n in names) if names else None
    # One slot per round: the text after each "respond [priority]" up to that round's end
    # (its "map grid N", or the next "coquitlam <unit> N" when the grid was lost). Every round
    # is searched, because the announcement is read twice and STT damages the two readings
    # differently: DISP-2026-E792B0 heard "epidominal pain" in round 1 and "abdominal pain" in
    # round 2, and DISP-2026-76A4BF lost the whole incident phrase from round 1. A slot never
    # runs on into the next round's unit list: DISP-2026-A19179's did, and found "rescue 2".
    slots = []
    for m in _RESPOND.finditer(transcript or ""):
        tail = transcript[m.end():]
        end = re.search(r'\bmap\s+grid\s+\d+', tail, re.IGNORECASE)
        if end:
            tail = tail[:end.end()]
        elif unit_alt:
            nxt = re.search(r'\bcoquitlam\s+(?:' + unit_alt + r')\s*\d', tail, re.IGNORECASE)
            if nxt:
                tail = tail[:nxt.start()]
        slots.append(tail.strip())
    if slots:
        return " ; ".join(s for s in slots if s)
    if not unit_alt:
        return transcript or ""
    unit_token = re.compile(r'\b(?:' + unit_alt + r')\s*\d+\b', re.IGNORECASE)
    return unit_token.sub(' ', transcript or "")


# Minimum fuzz.ratio for a heard qualifier to name one. Swept 70/75/80/85/90 against all 601
# verified calls on 2026-09-11: 70 through 85 behave identically (one call corrected, none
# broken) and 90 fires on nothing, because the case that motivated it -- "chest payne" for
# "Chest Pain" on DISP-2026-A7BE29 -- scores 86. 80 is the midpoint of the band that behaves
# identically, so the value is not on an edge in either direction.
#
# A minimum margin over the runner-up was swept alongside it (0/5/10/15) and changed nothing
# on any call, so there is no measurement to justify one and none is imposed. An outright tie
# is handled instead, below.
_QUALIFIER_MIN_RATIO = 80


def _name_the_qualifier(matched: str, norm_transcript: str, call_types: List[str]) -> str:
    """Having matched a call type by substring, name a qualifier heard after it -- or don't.

    The exact-substring stage returns the longest candidate that appears verbatim, so a
    misheard qualifier drops the whole clause: "medical aid chest payne" contains
    "medical aid" and not "medical aid chest pain", and the answer came back as the bare
    category with the fuzzy stage never reached (DISP-2026-A7BE29).

    So once a category is matched, the qualifier is chosen among that category's own
    variants -- the same partition-then-decide shape the talk group uses (parser/channels.py).
    Scoring within the partition is what makes it safe: every sibling shares the category
    words, so only the qualifier can separate them, and fuzz.ratio over the equivalent window
    of what was heard is doing the one job it is reliable at. token_set_ratio must not be used
    here -- it returns 100 whenever one token set is a subset of the other, so the bare
    category would score a perfect match against every variant at once
    (docs/standards/dependency-behaviour.md).

    A longer qualifier scoring the same as a shorter one wins, because it accounts for more of
    what was heard: "overdose arrest" over "overdose". An outright tie on both score and length
    returns the bare category rather than whichever sorted first.

    Returning the bare category is a real answer, not a failure: 161 of 601 verified calls
    (26.8 %) are announced with no qualifier at all.

    Measured 2026-09-11 over all 601 verified calls: 584 -> 585 correct, nothing broken.
    """
    cat_norm = re.sub(r'\s*-\s*', ' ', matched.lower())
    prefix = matched.lower() + " - "
    siblings = [t for t in call_types if t.lower().startswith(prefix)]
    if not siblings:
        return matched

    at = norm_transcript.find(cat_norm)
    if at < 0:
        return matched
    heard = norm_transcript[at + len(cat_norm):].split()
    if not heard:
        return matched

    scored = []
    for term in siblings:
        qualifier = re.sub(r'\s*-\s*', ' ', term[len(matched) + 3:].lower())
        window = " ".join(heard[:len(qualifier.split())])
        scored.append((fuzz.ratio(qualifier, window), len(qualifier.split()), term))
    scored.sort(key=lambda row: (-row[0], -row[1]))

    best = scored[0]
    if best[0] < _QUALIFIER_MIN_RATIO:
        return matched
    if len(scored) > 1 and (scored[1][0], scored[1][1]) == (best[0], best[1]):
        return matched
    return best[2]


def match_incident_type(transcript: str, call_types: List[str], aliases: dict = None,
                        units_vocabulary=None) -> str:
    """Matches transcript text to incident/call types using exact substring or fuzzy matching.

    Returns a CANONICAL term always. `aliases` maps a recognition-only spelling to the
    canonical term it stands for: faster-whisper writes American English while the
    department writes Canadian, so the string matched is not always the string shown
    (punch-list #43). Defaults to the vocabulary-backed map when not supplied.
    """
    if aliases is None:
        aliases = CALL_TYPE_ALIASES

    # Only the incident slot is searched (#34a): the unit list is never a source of a call type.
    transcript = incident_search_text(transcript, units_vocabulary)

    # Normalize transcript by removing hyphens and double spaces for clean matching
    norm_transcript = re.sub(r'\s*-\s*', ' ', transcript.lower())

    # Candidates are canonical terms plus recognition aliases, each carrying the canonical
    # term it resolves to. Longest-first so a qualified type ("Report of Smoke - High
    # Risk") is tested before the base type it contains, which would otherwise match first
    # and silently drop the qualifier.
    candidates = [(ct, ct) for ct in call_types]
    candidates += [(alias, canon) for alias, canon in aliases.items()]
    candidates.sort(key=lambda pair: len(pair[0]), reverse=True)

    # 1. Look for exact substring matches (normalizing the candidate too)
    for match_text, canonical in candidates:
        norm_ct = re.sub(r'\s*-\s*', ' ', match_text.lower())
        if norm_ct in norm_transcript:
            return _name_the_qualifier(canonical, norm_transcript, call_types)

    # 2. Look for best fuzzy match
    best_match = None
    best_score = 0
    for match_text, canonical in candidates:
        score = fuzz.token_set_ratio(match_text.lower(), transcript)
        if score > best_score:
            best_score = score
            best_match = canonical
            
    # PROVENANCE REQUIRED (CLAUDE.md §6.3): 80 is an inherited fuzzy-match cutoff with
    # no cited source. Failing it is safe -- the result is the explicit "Unknown
    # Incident", never a guessed call type -- but the value should be validated against
    # the HITL correction history rather than left as a magic number.
    #
    # Kept on measurement (punch-list #19a, 2026-09-06). This stage was removed and the
    # whole corpus re-run through the chain harness: three calls lost their call type --
    # DISP-2026-4C9D76 and 7270E4, "order, unknown source" for Odor - Unknown Source, and
    # 969223, "Medic, Aid, overdose, arrest" for Medical Aid - Overdose Arrest -- STT
    # misspellings the substring stage cannot see. token_set_ratio's subset property
    # (docs/standards/dependency-behaviour.md) means a misspelled qualifier can come back
    # as the generic type; on 508 verified calls it produced no wrong answer.
    if best_score >= 80:
        return best_match
    return "Unknown Incident"
