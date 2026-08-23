# backend/scripts/normalize_call_type_vocabulary.py
"""One-time canonicalization of public.vocabulary category='call_type'. See punch-list #33.

The call-type vocabulary had grown a second ROW wherever the string the parser must
recognise differed from the string the department displays. That made locale variants into
rival canonical terms, and left ground truth split across both spellings.

This script separates the two jobs:
  * canonical term  -> the single active vocabulary row, shown on the kiosk and offered
                       to reviewers
  * recognition alias -> vocabulary.metadata->'aliases', matched against but never shown

Canonical spellings below were set by operator decision on 2026-08-23. Nothing in
docs/standards/ governs the call-type list (source='cfr_curated'), so this is department
policy, not a standard -- if E-Comm / Coquitlam Fire publishes an official list it
supersedes these choices (CLAUDE.md §7.2).

Dry-run by default. Pass --apply to write.

    python backend/scripts/normalize_call_type_vocabulary.py
    python backend/scripts/normalize_call_type_vocabulary.py --apply
"""
import argparse
import json
import os
import sys

import psycopg2
import psycopg2.extras

# Rows with zero usage in BOTH public.dispatches.incident_type and .verified_incident as of
# 2026-08-23. Retired rather than deleted so the row history survives.
DEAD_TERMS = [
    "Alarms Activated",
    "Alarms Activated - High Risk",
    "Medical Aid - Cardiac Problems",
    # Operator ruling 2026-08-23: not spoken call types.
    #
    # "Vehicle Rollover" -- "Motor Vehicle Incident - Rollover" IS spoken and stays; this
    # bare form is not. Neither term has ever been used, and no transcript in the corpus
    # contains "roll" at all, so this retires the duplicate before it can win a match.
    "Vehicle Rollover",
    # "Public Assist" -- zero occurrences in any raw_transcript, incident_type or
    # verified_incident. "Assist" and "Lift Assist" are the spoken forms and remain.
    "Public Assist",
]

# (retired term, canonical term, keep_as_alias)
#
# "Breathing Problems": faster-whisper wrote "breathing problem" (singular) in 24/24
# transcripts, so the plural is never the recognised form -- no alias needed.
#
# "Wildland Fire - Smoldering": faster-whisper wrote "smoldering" 5/5 and "smouldering"
# 0/5, so the American spelling IS the recognised form and must be kept as an alias.
# Retiring it outright would drop the qualifier on every smouldering call.
MERGES = [
    ("Medical Aid - Breathing Problems", "Medical Aid - Breathing Problem", False),
    ("Wildland Fire - Smoldering", "Wildland Fire - Smouldering", True),
]

# Terms reviewers confirmed as ground truth that had no vocabulary row, so the parser could
# never emit them regardless of parse quality. Confirmed present in verified_incident.
MISSING_TERMS = [
    "Structure Fire - Detached Structure",
    "Tent Fire - High Risk",
    "Medical Aid - Airway Obstruction",
    "Odor - Unknown Source",
    # Operator ruling 2026-08-23: "Assist", "Lift Assist" and "Medical Aid - Assist" are
    # three DISTINCT call types, not variants of one. Bare "Assist" was the only one with
    # no vocabulary row, so dispatch saying "respond routine, assist, 1331 Green Bank
    # Court" classified as "Unknown Incident" -- confirmed on 3 calls. Spoken 22 times in
    # the corpus (16 of them "lift assist").
    "Assist",
]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    args = ap.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("DATABASE_URL is not set. Refusing to guess a database (CLAUDE.md §3).")

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    print(f"{'APPLYING' if args.apply else 'DRY RUN'} against {db_url.split('@')[-1]}\n")

    # 1. Retire dead duplicate rows.
    for term in DEAD_TERMS:
        cur.execute(
            "SELECT count(*) FROM dispatches WHERE incident_type=%s OR verified_incident=%s",
            (term, term),
        )
        used = cur.fetchone()[0]
        if used:
            # Guard: the zero-usage measurement is from 2026-08-23. If a call has landed on
            # this term since, retiring it silently would strand that record.
            print(f"  SKIP  retire {term!r} -- now used by {used} dispatch(es), re-measure first")
            continue
        cur.execute(
            "UPDATE vocabulary SET is_active=FALSE, updated_at=now() "
            "WHERE category='call_type' AND term=%s AND is_active",
            (term,),
        )
        print(f"  retire (dead)      {term!r}  rows={cur.rowcount}")

    # 2. Merge locale/pluralisation variants into their canonical term.
    for old, canon, keep_alias in MERGES:
        cur.execute(
            "SELECT count(*) FROM vocabulary WHERE category='call_type' AND term=%s", (canon,)
        )
        if not cur.fetchone()[0]:
            print(f"  ERROR canonical term {canon!r} missing -- aborting")
            conn.rollback()
            sys.exit(1)

        # Ground truth is canonicalised: verified_incident records WHAT THE CALL WAS, and
        # the two spellings state the same fact. Historical incident_type is deliberately
        # NOT rewritten -- it records what the system output at the time, and rewriting it
        # would destroy the was-broken/still-broken distinction the audit depends on
        # (parser_audit_handoff.md §4.2).
        cur.execute(
            "UPDATE dispatches SET verified_incident=%s WHERE verified_incident=%s",
            (canon, old),
        )
        print(f"  migrate verified   {old!r} -> {canon!r}  rows={cur.rowcount}")

        if keep_alias:
            cur.execute(
                "UPDATE vocabulary "
                "SET metadata = coalesce(metadata,'{}'::jsonb) || %s::jsonb, updated_at=now() "
                "WHERE category='call_type' AND term=%s",
                (json.dumps({"aliases": [old]}), canon),
            )
            print(f"  alias              {old!r} -> metadata of {canon!r}  rows={cur.rowcount}")

        cur.execute(
            "UPDATE vocabulary SET is_active=FALSE, updated_at=now() "
            "WHERE category='call_type' AND term=%s AND is_active",
            (old,),
        )
        print(f"  retire (merged)    {old!r}  rows={cur.rowcount}")

    # 3. Add confirmed ground-truth terms that had no row.
    for term in MISSING_TERMS:
        cur.execute(
            "INSERT INTO vocabulary (category, term, term_normalized, sort_order, source, is_active) "
            "VALUES ('call_type', %s, lower(%s), 0, 'hitl_verified', TRUE) "
            "ON CONFLICT DO NOTHING",
            (term, term),
        )
        print(f"  add                {term!r}  rows={cur.rowcount}")

    cur.execute("SELECT count(*) FROM vocabulary WHERE category='call_type' AND is_active")
    print(f"\nactive call_type rows after: {cur.fetchone()[0]}")

    if args.apply:
        conn.commit()
        print("committed.")
    else:
        conn.rollback()
        print("rolled back (dry run). Re-run with --apply to write.")
    conn.close()


if __name__ == "__main__":
    main()
