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
            return canonical

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
    if best_score >= 80:
        return best_match
    return "Unknown Incident"
