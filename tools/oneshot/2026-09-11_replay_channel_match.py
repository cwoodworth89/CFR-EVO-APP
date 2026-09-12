"""Punch list #79 — score match_radio_channel against the operator's verified transcripts.

Replays every stored raw_transcript through the parser, takes the channel the pipeline would
publish, and compares it to `verified_talkgroup` where the operator has set one. Read-only.

Kept because "this changes nothing except where intended" is the whole basis for changing a
rule that decides an operational value (CLAUDE.md §7.6), and that claim should be re-runnable
rather than remembered.

Three rules were measured with it on 2026-09-11, in order:

  1. first-qualifying-in-list (shipped)   — the #19a rule, order-dependent
  2. plain word overlap, whole roster     — 1015/1029 fragments identical, but 10 calls that
                                            had a correct channel fell to unresolved
  3. the operator's cascade (shipped)     — number, then "venue", then what is left

Against ground truth, rule 3 over 587 calls:

    537 with a verified talk group
    536 correct · 0 wrong · 1 unresolved

    14 calls differ from what is stored, every one an improvement:
      11  nothing            -> the right channel
       2  the WRONG channel  -> 10 Combined Response Coquitlam   (DISP-2026-90674A filed as
                                5 Coquitlam, DISP-2026-F24935 as 6 Coquitlam)
       1  10 Combined Resp.  -> Combined Response Venue Port Mann (DISP-2026-07CC85)

    The single unresolved call is DISP-2026-747823, where the STT lost the talk-group clause
    entirely -- the fragment holds only address and incident words. Nothing to match, and
    unresolved is the correct answer.

Run:

    ssh tcfire@100.95.146.94
    cd /home/tcfire/CFR-EVO-APP/backend
    export DATABASE_URL=$(grep -m1 '^DATABASE_URL=' .env | cut -d= -f2-)
    ../.venv/bin/python ../tools/oneshot/2026-09-11_replay_channel_match.py
"""
import collections
import os
import sys
from unittest.mock import MagicMock

# The package __init__ pulls in audio_listener, which initialises PortAudio on import and
# fails on a headless ssh session -- and must not touch the live capture. Nothing below uses
# audio; stub it before cfr_dispatch is imported.
sys.modules.setdefault("sounddevice", MagicMock())

import psycopg2

from cfr_dispatch.config import UNITS_VOCABULARY, RADIO_CHANNELS
import cfr_dispatch.parser.announcement as ann
from cfr_dispatch.parser.announcement import parse_dispatch_announcement, split_rounds
from cfr_dispatch.parser.sanitize import sanitize_transcript
from cfr_dispatch.parser.channels import match_radio_channel

captured = []
ann.match_radio_channel = lambda raw, chans: (
    captured.append(raw), match_radio_channel(raw, chans))[1]


def published_channel(raw_transcript):
    """The channel the pipeline would publish, and the fragments it saw getting there."""
    captured.clear()
    try:
        for segment in split_rounds(sanitize_transcript(raw_transcript), UNITS_VOCABULARY):
            if len(segment.split()) > 2:
                parse_dispatch_announcement(segment, UNITS_VOCABULARY)
    except Exception as exc:  # noqa: BLE001
        return None, [], exc
    fragments = list(captured)
    resolved = next((c for c in (match_radio_channel(f, RADIO_CHANNELS) for f in fragments) if c), None)
    return resolved, fragments, None


def main():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute("""SELECT dispatch_id, raw_transcript, verified_talkgroup,
                          target->>'radio_channel'
                   FROM public.dispatches
                   WHERE raw_transcript IS NOT NULL AND raw_transcript <> ''
                   ORDER BY dispatch_id""")

    tally = collections.Counter()
    wrong, unresolved, changed = [], [], []
    for dispatch_id, raw, truth, stored in cur.fetchall():
        resolved, fragments, err = published_channel(raw)
        if err:
            tally["parse errors"] += 1
        if not fragments:
            continue
        tally["calls"] += 1
        if resolved != stored:
            changed.append((dispatch_id, stored, resolved))
        if not truth:
            tally["no ground truth"] += 1
            continue
        tally["with ground truth"] += 1
        if resolved == truth:
            tally["  correct"] += 1
        elif resolved is None:
            tally["  unresolved"] += 1
            unresolved.append((dispatch_id, truth, fragments))
        else:
            tally["  WRONG"] += 1
            wrong.append((dispatch_id, truth, resolved, fragments))

    print("channels in vocabulary:", len(RADIO_CHANNELS))
    for channel in RADIO_CHANNELS:
        print("   ", channel)
    print()
    for key, n in tally.most_common():
        print("  %-22s %d" % (key, n))

    print("\nWRONG against ground truth (%d):" % len(wrong))
    for dispatch_id, truth, got, fragments in wrong:
        print("  %s  truth=%s  got=%s" % (dispatch_id, truth, got))
        for f in fragments:
            print("      %r" % f.strip()[:90])

    print("\nUnresolved despite a ground truth (%d):" % len(unresolved))
    for dispatch_id, truth, fragments in unresolved:
        print("  %s  truth=%s" % (dispatch_id, truth))
        for f in fragments:
            print("      %r" % f.strip()[:90])

    print("\nDiffers from the stored value (%d):" % len(changed))
    for dispatch_id, stored, resolved in changed:
        print("  %s  stored=%-34s now=%s" % (dispatch_id, stored, resolved))


if __name__ == "__main__":
    main()
