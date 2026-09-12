"""Punch list #79 — the measurement that justified changing match_radio_channel.

Replays every stored raw_transcript through the parser, captures the fragment actually handed
to match_radio_channel, and diffs the shipped first-in-list rule against the token-overlap
rule that replaced it. Read-only: writes nothing.

Run against the pre-fix tree on the kiosk, 2026-09-11:

    624 raw transcripts · 584 reached the matcher · 1029 fragments
    1026 identical · 3 changed, all 3 'combined response venue port man[n]'
    10 Combined Response Coquitlam -> Combined Venue Port Mann
    (DISP-2026-07CC85, DISP-2026-B772D2)

No fragment the first-in-list rule resolved correctly is decided differently. Kept because
the claim "this changes nothing else" is the whole basis for the change (CLAUDE.md §7.6) and
should be re-runnable, not remembered. The `proposed` function below is the rule as it was
proposed; the shipped one is in cfr_dispatch/parser/channels.py.

    ssh tcfire@100.95.146.94
    cd /home/tcfire/CFR-EVO-APP/backend
    export DATABASE_URL=$(grep -m1 '^DATABASE_URL=' .env | cut -d= -f2-)
    ../.venv/bin/python tools/oneshot/2026-09-11_replay_channel_match.py
"""
import collections
import os
import sys
from unittest.mock import MagicMock

# The package __init__ pulls in audio_listener, which initializes PortAudio on import and
# fails on a headless ssh session (and must not touch the live capture). Nothing below
# uses audio; stub it before cfr_dispatch is imported.
sys.modules.setdefault("sounddevice", MagicMock())

import psycopg2
import regex as re

from cfr_dispatch.config import UNITS_VOCABULARY, RADIO_CHANNELS
import cfr_dispatch.parser.announcement as ann
from cfr_dispatch.parser.announcement import parse_dispatch_announcement, split_rounds
from cfr_dispatch.parser.sanitize import sanitize_transcript
from cfr_dispatch.parser.channels import match_radio_channel as shipped

captured = []


def spy(raw, channels):
    captured.append(raw)
    return shipped(raw, channels)


ann.match_radio_channel = spy


def _tokens(text):
    return re.findall(r'[a-z0-9]+', (text or "").lower())


def proposed(talk_group_raw, radio_channels):
    raw_tokens = _tokens(talk_group_raw)
    if not raw_tokens:
        return None
    raw_set = set(raw_tokens)
    channel_tokens = {ch: _tokens(ch) for ch in radio_channels}
    raw_digits = [t for t in raw_tokens if t.isdigit()]
    if raw_digits:
        hit = [ch for ch, toks in channel_tokens.items()
               if any(d in toks for d in raw_digits)]
        return hit[0] if len(hit) == 1 else None
    counts = collections.Counter()
    for toks in channel_tokens.values():
        counts.update(set(toks))
    scored = []
    for ch, toks in channel_tokens.items():
        unique = {t for t in toks if counts[t] == 1 and not t.isdigit()}
        if unique & raw_set:
            scored.append((len(set(toks) & raw_set), ch))
    if not scored:
        return None
    scored.sort(key=lambda p: (-p[0], p[1]))
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None
    return scored[0][1]


conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()
cur.execute("SELECT dispatch_id, raw_transcript FROM dispatches "
            "WHERE raw_transcript IS NOT NULL AND raw_transcript <> '' ORDER BY dispatch_id")
rows = cur.fetchall()

frag_by_call = {}
errors = 0
for did, raw in rows:
    captured.clear()
    try:
        for seg in split_rounds(sanitize_transcript(raw), UNITS_VOCABULARY):
            if len(seg.split()) > 2:
                parse_dispatch_announcement(seg, UNITS_VOCABULARY)
    except Exception as exc:  # noqa: BLE001
        errors += 1
        print("ERR", did, type(exc).__name__, exc)
    if captured:
        frag_by_call[did] = list(captured)

diffs = collections.Counter()
examples = {}
agree = collections.Counter()
for did, frags in frag_by_call.items():
    for f in frags:
        a = shipped(f, RADIO_CHANNELS)
        b = proposed(f, RADIO_CHANNELS)
        if a == b:
            agree[a] += 1
        else:
            key = (f.strip()[:80], a, b)
            diffs[key] += 1
            examples.setdefault(key, did)

print()
print("channels in vocabulary :", len(RADIO_CHANNELS))
print("dispatches with raw    :", len(rows), "| parse errors:", errors)
print("calls reaching matcher :", len(frag_by_call))
print("fragments agreeing     :", sum(agree.values()), dict(agree))
print("distinct disagreements :", len(diffs), "| fragments affected:", sum(diffs.values()))
print()
for (f, a, b), n in diffs.most_common():
    print("n=%-4d %s" % (n, examples[(f, a, b)]))
    print("   frag : %r" % f)
    print("   now  : %s" % a)
    print("   new  : %s" % b)
