"""Whisper STT vocabulary biasing.

THE TOKEN BUDGET IS REAL AND IT IS SMALL
----------------------------------------
faster-whisper caps the `hotwords` string and keeps the HEAD of it
(`faster_whisper/transcribe.py`, get_prompt):

    if len(hotwords_tokens) >= self.max_length // 2:
        hotwords_tokens = hotwords_tokens[: self.max_length // 2 - 1]

For the model loaded on the kiosk, `max_length` is 448, so the cap is **223 tokens**.

An earlier version of this file assembled every road name, unit, core term and call type
into one string -- 1,173 entries, 5,172 tokens -- under the comment "NO artificial
truncation", having removed an earlier top-80-by-frequency limit (commit 79808cc, which
had correctly identified the decoder context problem). Measured 2026-08-22: **61 of 1,173
entries survived**, the list was alphabetical, so it ended at "Archworth Avenue" and
dropped everything from "Argyle Street" onward. Westwood, Lougheed, Pinetree, Barnet and
Mariner -- every arterial in the city -- received no biasing whatsoever, and call types,
being last, never survived at all.

That is the upstream source of the transcription errors the geocoder was then trying to
repair by guessing ("Lowheed" for Lougheed, "Tasis" for Tahsis). Guessing downstream
cannot be made safe -- distinct Coquitlam streets score up to 96 against each other -- so
the fix has to be here (punch-list #15, #18).

SO THE BUDGET IS SPENT DELIBERATELY, IN PRIORITY ORDER
1. Core dispatch template terms and unit names -- small, and every announcement uses them.
2. Streets the operator has actually corrected in HITL review -- empirically demonstrated
   to be misheard, so the highest value per token available.
3. Streets ranked by how often they appear in real dispatches (public.dispatches).
4. Streets ranked by parcel count (public.parcels) -- a proxy for prominence that covers
   streets not yet dispatched to. This is the ranking commit 79808cc used.
5. Call types.

Terms are then trimmed to the MEASURED token budget rather than to a guessed term count:
the earlier fix capped at 120 terms, which at ~4.4 tokens per street name is still roughly
double the real cap. Whatever is dropped is dropped from the least valuable end, and the
trim is logged so it is visible rather than silent.
"""
import os
import re
import time
import logging
import requests

_cached_hitl_streets = []
_last_hitl_fetch_time = 0.0

# faster-whisper keeps hotwords_tokens[: max_length // 2 - 1]. Used only when the caller
# cannot supply the loaded model's real max_length; 448 is Whisper's decoder context for
# every published model size, so 223 is the correct cap unless that changes upstream.
DEFAULT_MAX_LENGTH = 448


def hotword_token_budget(max_length: int = DEFAULT_MAX_LENGTH) -> int:
    """Tokens faster-whisper will actually keep from the hotwords string."""
    return max_length // 2 - 1


def get_hitl_verified_streets() -> list[str]:
    """
    Fetches the most frequently misheard street names that required HITL correction.
    Cached in memory for 10 minutes to prevent blocking network requests during transcription.
    """
    global _cached_hitl_streets, _last_hitl_fetch_time
    now = time.time()
    if _cached_hitl_streets and (now - _last_hitl_fetch_time < 600.0):
        return _cached_hitl_streets

    try:
        local_api_url = os.environ.get("LOCAL_API_URL", "http://localhost:8000").rstrip("/")
        endpoint = f"{local_api_url}/api/dispatches?limit=200"
        response = requests.get(endpoint, timeout=3)
        response.raise_for_status()
        records = response.json()

        from collections import defaultdict
        tally = defaultdict(int)

        for r in records:
            if not r.get("feedback_submitted"):
                continue
            verified_addr = r.get("verified_address")
            system_addr = r.get("address") or (r.get("target", {}).get("address") if r.get("target") else None)

            if not verified_addr:
                continue

            def clean_street(addr_str):
                if not addr_str:
                    return ""
                match = re.search(r'^\d+\s+(?P<street>.*)', addr_str.split(',')[0].strip())
                if match:
                    return match.group('street').strip().title()
                return addr_str.strip().title()

            v_street = clean_street(verified_addr)
            sys_street = clean_street(system_addr)

            if v_street and sys_street and v_street != sys_street:
                tally[v_street] += 1

        sorted_streets = sorted(tally.keys(), key=lambda s: tally[s], reverse=True)
        _cached_hitl_streets = sorted_streets
        _last_hitl_fetch_time = now
        return sorted_streets
    except Exception as e:
        logging.warning(f"Failed to fetch HITL verified streets for STT hotwords: {e}")
        return _cached_hitl_streets


def _streets_by_frequency(engine) -> list[str]:
    """Street names ordered by dispatch count, then by parcel count.

    Dispatch history is the better signal -- it is what the microphone actually hears --
    but it only covers 159 of 1,079 streets, so parcel count carries the rest. Parcel
    count is the ranking commit 79808cc used, from the address layer.
    """
    if engine is None:
        return []
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            rows = conn.execute(text("""
                WITH dispatched AS (
                    SELECT upper(btrim(regexp_replace(
                               split_part(COALESCE(verified_address, target->>'address'), ',', 1),
                               '^[0-9]+\\s+', ''))) AS street,
                           count(*) AS n
                    FROM public.dispatches
                    WHERE COALESCE(verified_address, target->>'address') IS NOT NULL
                    GROUP BY 1
                ),
                parcelled AS (
                    SELECT upper(btrim(street || ' ' || COALESCE(streettype, ''))) AS street,
                           count(*) AS n
                    FROM public.parcels
                    WHERE street IS NOT NULL AND btrim(street) <> ''
                    GROUP BY 1
                )
                SELECT COALESCE(d.street, p.street) AS street,
                       COALESCE(d.n, 0) AS dispatch_n,
                       COALESCE(p.n, 0) AS parcel_n
                FROM dispatched d
                FULL OUTER JOIN parcelled p ON p.street = d.street
                WHERE COALESCE(d.street, p.street) <> ''
                ORDER BY dispatch_n DESC, parcel_n DESC
            """)).fetchall()
        return [str(r[0]).title() for r in rows if r[0]]
    except Exception as e:
        logging.warning(f"Failed to rank streets by frequency for STT hotwords: {e}")
        return []


def _trim_to_budget(terms: list[str], budget_tokens: int, encoder=None) -> tuple[list[str], int]:
    """Keep as many leading terms as fit inside the token budget.

    `encoder` should be the loaded model's tokenizer encode function so the budget is
    MEASURED. Without one, a deliberately conservative estimate is used -- overshooting
    silently is the failure this whole module exists to prevent, so the estimate errs
    toward dropping a term rather than toward losing an arterial.
    """
    def n_tokens(s: str) -> int:
        if encoder is not None:
            return len(encoder(" " + s.strip()))
        # ~1 token per 3 characters is pessimistic for title-case street names, which is
        # the direction we want to be wrong in.
        return max(1, len(s) // 3 + 1)

    kept, used = [], 0
    sep = n_tokens(", ")
    for t in terms:
        cost = n_tokens(t) + (sep if kept else 0)
        if used + cost > budget_tokens:
            continue
        kept.append(t)
        used += cost
    return kept, used


def build_stt_bias_words(validator=None, units_vocabulary: list[str] = None,
                         max_length: int = DEFAULT_MAX_LENGTH,
                         encoder=None) -> tuple[str, str]:
    """Build (initial_prompt, hotwords) for faster-whisper, inside the real token budget."""
    core_dispatch_terms = [
        'Coquitlam', 'respond', 'routine', 'emergency', 'Combined Response Coquitlam',
        'use talk group', 'map grid', 'medical aid', 'overdose', 'lift assist',
        'structure fire', 'alarm activated', 'rescue', 'hazard'
    ]

    unit_terms = []
    if units_vocabulary and isinstance(units_vocabulary, (list, set)):
        unit_terms = [str(u).title() for u in units_vocabulary if len(str(u).strip()) > 1]

    hitl_streets = get_hitl_verified_streets()

    ranked_streets = _streets_by_frequency(getattr(validator, 'engine', None))
    if not ranked_streets and validator and hasattr(validator, 'get_all_road_names'):
        # Fall back to the unranked list rather than no streets at all, but say so: an
        # unranked list means the budget is being spent alphabetically, which is the
        # defect this module was rewritten to fix.
        logging.warning("STT hotwords: street frequency ranking unavailable; "
                        "falling back to unranked road names.")
        try:
            ranked_streets = [str(s).title() for s in validator.get_all_road_names()]
        except Exception as e:
            logging.warning(f'Failed to load road names for STT hotwords: {e}')

    all_call_types = []
    try:
        from cfr_dispatch.config.vocab import CALL_TYPES
        all_call_types = [str(ct).title() for ct in CALL_TYPES if len(str(ct).strip()) > 1]
    except Exception:
        pass

    # Priority order. Everything after the budget runs out is dropped, so this ordering is
    # the actual policy decision -- see the module docstring.
    ordered = list(dict.fromkeys(
        core_dispatch_terms + unit_terms + hitl_streets + ranked_streets + all_call_types
    ))

    # STT_HOTWORDS_EXCLUDE: comma-separated terms removed before the budget is spent, so one
    # term's effect can be measured with tools/harness_chain.py (CLAUDE.md 6.4). First use
    # 2026-09-05, "map grid": the template prompt echoed that phrase into pauses (#63) and the
    # hotwords sit in the same previous-text slot of the decoder.
    excluded = {t.strip().lower() for t in os.environ.get("STT_HOTWORDS_EXCLUDE", "").split(",")
                if t.strip()}
    if excluded:
        before = len(ordered)
        ordered = [t for t in ordered if t.lower() not in excluded]
        logging.info("STT hotwords: %d term(s) removed by STT_HOTWORDS_EXCLUDE (%s).",
                     before - len(ordered), ", ".join(sorted(excluded)))

    budget = hotword_token_budget(max_length)
    kept, used = _trim_to_budget(ordered, budget, encoder)

    dropped = len(ordered) - len(kept)
    logging.info(
        "STT hotwords: %d/%d terms kept, ~%d/%d tokens used "
        "(%d dropped; ranking: %d HITL, %d frequency-ranked streets).",
        len(kept), len(ordered), used, budget, dropped, len(hitl_streets), len(ranked_streets)
    )
    if kept and hitl_streets and not set(hitl_streets) & set(kept):
        logging.warning("STT hotwords: no HITL-corrected street survived the budget. "
                        "The most valuable terms are being crowded out.")

    hotwords_str = ', '.join(kept)

    # STT_INITIAL_PROMPT, when set, replaces the template prompt below; set it to an empty
    # string to send no prompt at all. A named tuning surface (CLAUDE.md 6.4) so the prompt's
    # effect is measured with tools/harness_chain.py rather than argued: on 2026-09-05 the
    # model in service was inserting this prompt's own "map grid" phrase into pauses
    # (punch-list #63).
    env_prompt = os.environ.get("STT_INITIAL_PROMPT")
    if env_prompt is not None:
        return (env_prompt.strip() or None), hotwords_str
    initial_prompt_str = (
        'Coquitlam Fire Dispatch. Engine 1, Ladder 1, Quint 5, Rescue 1. '
        'Structure Fire, Medical Aid, Alarm Activated, Commercial Alarm. '
        'Respond on talk group Tac 1, map grid.'
    )
    return initial_prompt_str, hotwords_str
