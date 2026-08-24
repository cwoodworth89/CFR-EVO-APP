# backend/scripts/fix_tahsis_spelling.py
"""Correct the "Tasis" -> "Tahsis" misspelling in DISP-2026-DD2342 ground truth.

Operator request 2026-08-23 ("flag Tahsis Ave for spelling review across all of our data").

`public.road_names` -- City of Coquitlam municipal open data, the authority for street
spelling -- holds exactly one match: "Tahsis Avenue". "Tasis" is not a Coquitlam road.

A full sweep of every verified_address against public.road_names found no other
mismatches; the only two were "Port Mann Bridge" (a real landmark, not a road_names entry)
and "Block Ponderosa St" (an artifact of the "1080 block Ponderosa Street" phrasing).

Why this one matters more than a cosmetic typo: DD2342 is rated PERFECT with
include_in_training = true and model_updated = false, so the misspelling is queued as a
Whisper training label and has not been consumed yet. Correcting it now prevents teaching
the model a street name that does not exist.

Note for the STT side, NOT addressed here: faster-whisper wrote "Tassus" for Tahsis in 2 of
3 corpus occurrences. That is a consistent mis-recognition and belongs as a street-vocabulary
alias, the same pattern as "Smoldering" for "Smouldering" (punch-list #43), rather than being
left to fuzzy matching.

Dry-run by default. Pass --apply to write.
"""
import argparse
import os
import sys

import psycopg2

DISPATCH_ID = "DISP-2026-DD2342"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    args = ap.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("DATABASE_URL is not set. Refusing to guess a database (CLAUDE.md §3).")

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur = conn.cursor()

    # Guard: confirm the authoritative spelling still exists before rewriting anything to it.
    cur.execute("SELECT road_name FROM road_names WHERE road_name ILIKE '%tahsis%'")
    authoritative = [r[0] for r in cur.fetchall()]
    if "Tahsis Avenue" not in authoritative:
        conn.rollback()
        sys.exit(f"public.road_names does not contain 'Tahsis Avenue' (found {authoritative}). "
                 f"Refusing to normalise to a spelling the municipal data does not confirm.")
    print(f"authority: public.road_names -> {authoritative}\n")

    cur.execute(
        "SELECT verified_address, verified_transcript FROM dispatches WHERE dispatch_id = %s",
        (DISPATCH_ID,),
    )
    row = cur.fetchone()
    if not row:
        conn.rollback()
        sys.exit(f"{DISPATCH_ID} not found.")
    print(f"BEFORE  verified_address    : {row[0]!r}")
    print(f"        verified_transcript : {row[1]!r}\n")

    cur.execute(
        """
        UPDATE dispatches
           SET verified_address    = regexp_replace(verified_address,    '[Tt]asis', 'Tahsis', 'g'),
               verified_transcript = regexp_replace(verified_transcript, '[Tt]asis', 'tahsis', 'g')
         WHERE dispatch_id = %s
        """,
        (DISPATCH_ID,),
    )
    print(f"rows updated: {cur.rowcount}")

    cur.execute(
        "SELECT verified_address, verified_transcript FROM dispatches WHERE dispatch_id = %s",
        (DISPATCH_ID,),
    )
    row = cur.fetchone()
    print(f"\nAFTER   verified_address    : {row[0]!r}")
    print(f"        verified_transcript : {row[1]!r}")

    # Nothing anywhere should still carry the bad spelling.
    cur.execute(
        "SELECT count(*) FROM dispatches "
        "WHERE verified_address ILIKE '%tasis%' OR verified_transcript ILIKE '%tasis%'"
    )
    remaining = cur.fetchone()[0]
    print(f"\nrecords still containing 'tasis' in verified data: {remaining}")

    if args.apply:
        conn.commit()
        print("committed.")
    else:
        conn.rollback()
        print("rolled back (dry run). Re-run with --apply to write.")
    conn.close()


if __name__ == "__main__":
    main()
