# backend/scripts/check_verified_transcripts.py
"""Spell- and street-checks the operator's verified transcripts before they become labels.

Run before every Whisper training pass. prepare_training_clips.py calls it and refuses to
build a dataset while blocking issues exist (override: --skip-label-check).

WHY THIS EXISTS
---------------
On the 2026-09-02 holdout, two of six address failures were the LABEL being wrong, not the
model: the verified transcript said "Norbur Pl" where the authoritative street is Norbury Pl
(the model's "norbery" was closer to the truth than its own reference), and "eagle mountain
driveuse" ran two words together. A verified transcript is simultaneously the training label
and the scoring reference, so a typo in it is trained in and then scored as correct.

WHAT IT CHECKS, AND AGAINST WHAT
--------------------------------
Every source is authoritative or the corpus itself -- no hand-written word list:

  1. Unknown tokens. Each word of a flagged transcript is checked against
       public.roads (road names and types), public.vocabulary (every active term), the
       street-suffix table, and the corpus: any token attested in >= ATTESTED_MIN distinct
       verified transcripts is accepted (typos are rare; real words recur). Anything left is
       reported with the nearest known token when one is close enough to be a likely typo.
  2. Streets and house numbers. The production parser is run on the verified text, exactly
       as it will be on the hypothesis, and the parsed street is checked against
       public.roads and the (house, street) pair against public.parcels. A street the city
       does not have is blocking; a missing parcel is advisory (new builds exist).
  3. Curation slips. A call whose note carries [PA] or mentions a cut-off recording but
       which is still flagged for training. The operator's flag is authoritative; this only
       reports the contradiction.

Read-only. Exit status 1 when blocking issues exist, so a runner stops before training.
"""
import os
import re
import sys
import difflib
import logging
import argparse
from collections import Counter, defaultdict

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import cfr_dispatch                      # _load_env() on import sets DATABASE_URL
from cfr_dispatch.parser import parse_dispatch_announcement, sanitize_transcript
from cfr_dispatch.config import UNITS_VOCABULARY

# A token seen in this many distinct verified transcripts is treated as a real word.
# Typos recur rarely; template words, unit names and common streets recur constantly.
# Chosen from the corpus shape 2026-09-02 (typos observed appeared once each), not tuned.
ATTESTED_MIN = 3

# difflib ratio at or above which an unknown token is reported as a probable typo of the
# suggestion. Observed typos: norbur/norbury 0.92, probelm/problem 0.86, driveuse/drive 0.77.
TYPO_RATIO = 0.75

WORD = re.compile(r"[a-z][a-z'\-]*")


def _tokens(text):
    return WORD.findall((text or "").lower())


def load_known_vocabulary(conn):
    """Every token the city, the vocabulary table, or the corpus vouches for."""
    from sqlalchemy import text as sql
    known = set()
    for (name, rtype) in conn.execute(sql("SELECT roadname, roadtype FROM public.roads")):
        known.update(_tokens(name)); known.update(_tokens(rtype))
    for (term,) in conn.execute(sql("SELECT term FROM public.vocabulary WHERE is_active")):
        known.update(_tokens(term))
    return known


def load_streets(conn):
    """Road names -> set, and (house, street) pairs from parcels -> set."""
    from sqlalchemy import text as sql
    roads = {r[0].strip().lower() for r in conn.execute(sql("SELECT DISTINCT roadname FROM public.roads")) if r[0]}
    parcels = {(str(h).strip(), s.strip().lower())
               for (h, s) in conn.execute(sql("SELECT house, street FROM public.parcels WHERE house IS NOT NULL AND street IS NOT NULL"))}
    parcel_streets = {s for (_, s) in parcels}
    return roads, parcels, parcel_streets


def flagged_calls(conn):
    from sqlalchemy import text as sql
    return conn.execute(sql(
        "SELECT dispatch_id, verified_transcript, "
        "       COALESCE(target->>'review_notes', review_notes) AS notes "
        "FROM public.dispatches "
        "WHERE feedback_submitted AND verified_transcript IS NOT NULL "
        "AND btrim(verified_transcript) <> :e "
        "AND COALESCE((target->>:k)::boolean, TRUE) ORDER BY dispatch_id"),
        {"e": "", "k": "include_in_training"}).fetchall()


ADDR = re.compile(r"^(\d+)\s+(.+?)(?:\s+([A-Za-z]+))?$")


def parsed_streets(verified):
    """(house, street_name, kind) triples the production parser extracts from the text."""
    out = []
    try:
        cands = parse_dispatch_announcement(sanitize_transcript(verified), UNITS_VOCABULARY)
    except Exception:
        return out
    c = cands[0] if cands else None
    if not c:
        return out
    addr = (c.address or "").strip()
    m = ADDR.match(addr)
    if m:
        house, name = m.group(1), m.group(2).strip().lower()
        # the parser keeps the suffix on the name in some shapes; strip a trailing type word
        parts = name.split()
        if len(parts) > 1 and len(parts[-1]) <= 6:
            name = " ".join(parts[:-1])
        out.append((house, name, "address"))
    for xs in (getattr(c, "x_street_1", None), getattr(c, "x_street_2", None)):
        if xs:
            parts = xs.strip().lower().split()
            if len(parts) > 1 and len(parts[-1]) <= 6:
                parts = parts[:-1]
            out.append((None, " ".join(parts), "cross street"))
    return out


def run_check(conn):
    """Returns (blocking_count, advisory_count, report_lines)."""
    rows = flagged_calls(conn)
    known = load_known_vocabulary(conn)
    roads, parcels, parcel_streets = load_streets(conn)
    known_list = sorted(known)
    road_list = sorted(roads)

    doc_freq = Counter()
    for _, verified, _ in rows:
        doc_freq.update(set(_tokens(verified)))
    attested = {t for t, n in doc_freq.items() if n >= ATTESTED_MIN}
    accept = known | attested

    blocking, advisory = 0, 0
    lines = []
    per_call = defaultdict(list)

    for did, verified, notes in rows:
        # 3. curation slips
        n = notes or ""
        if re.search(r"\[PA\]", n, re.I):
            per_call[did].append(("BLOCK", "tagged [PA] in review notes but still flagged for training")); blocking += 1
        elif re.search(r"cut ?off|truncat", n, re.I):
            per_call[did].append(("ADVISE", "review note mentions a cut-off recording")); advisory += 1

        # 1. unknown tokens
        for tok in sorted(set(_tokens(verified)) - accept):
            if tok.isdigit():
                continue
            near = difflib.get_close_matches(tok, known_list, n=1, cutoff=TYPO_RATIO)
            if near:
                per_call[did].append(("BLOCK", "'%s' is not a known word -- probable typo of '%s'" % (tok, near[0]))); blocking += 1
            else:
                per_call[did].append(("ADVISE", "'%s' is not a known word (business or place name?)" % tok)); advisory += 1

        # 2. streets and parcels, via the production parser
        for house, name, kind in parsed_streets(verified):
            if not name:
                continue
            if name not in roads:
                near = difflib.get_close_matches(name, road_list, n=1, cutoff=0.7)
                hint = (" -- did you mean '%s'?" % near[0]) if near else ""
                per_call[did].append(("BLOCK", "%s street '%s' is not in public.roads%s" % (kind, name, hint))); blocking += 1
            elif house and name in parcel_streets and (house, name) not in parcels:
                per_call[did].append(("ADVISE", "no parcel %s on %s (new build, or a wrong number?)" % (house, name))); advisory += 1

    for did in sorted(per_call):
        lines.append(did)
        for level, msg in per_call[did]:
            lines.append("    %-6s %s" % (level, msg))
    lines.append("")
    lines.append("checked %d flagged transcripts: %d blocking, %d advisory, across %d call(s)"
                 % (len(rows), blocking, advisory, len(per_call)))
    return blocking, advisory, lines


def main():
    ap = argparse.ArgumentParser(description="Spell- and street-check verified transcripts before training.")
    ap.add_argument("--quiet", action="store_true", help="summary line only")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)

    from sqlalchemy import create_engine
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("DATABASE_URL is not set; it is loaded from backend/.env by importing cfr_dispatch.")

    with create_engine(db_url).connect() as conn:
        blocking, advisory, lines = run_check(conn)
    print("\n".join(lines if not args.quiet else lines[-1:]))
    sys.exit(1 if blocking else 0)


if __name__ == "__main__":
    main()
