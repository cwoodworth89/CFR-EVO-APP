# Punch list #83 — Phase 1's transcript is deleted, so the first screen crews see cannot be measured

| | |
|:--|:--|
| **Status** | OPEN — not built |
| **Severity** | ⚪ hygiene (measurement) — promoted from the backlog by the operator 2026-09-13, because phase 1 is what crews read first |
| **Area** | 📡 Pipeline · 🎙️ STT |
| **Origin** | Operator call review of DISP-2026-E301A3, 2026-09-13: *"Why is the phase 1 transcript deleted? Isn't that important data so we can check our STT progress?"* |

[← punch list index](../debug_and_qa_punchlist.md)

---

## What is kept and what is not

| Data | Kept |
|:--|:--|
| The full recording's transcript, `dispatches.raw_transcript` (phase 2, from the whole WAV) | yes |
| The recording itself | yes |
| `dispatches.sanitized_transcript` | yes, but it is **not** the STT: phase 2 rebuilds it from the parsed fields (`reconstruct_template_transcript`) |
| **Phase 1's chunk transcript** — the 16–22 s partial the first payload was built from — its chunk length, and its parse | **no** |

## Why it is lost

Phase 1 writes its transcript and candidates to `public.dispatch_sessions`
(`backend/cfr_dispatch/session_store.py`), a hand-off table between the listener and the
worker, added so a failed broadcast could not produce a duplicate dispatch (#25, #29). Phase 2
reads the row and deletes it (`backend/cfr_dispatch/worker.py:69`, `self._store.cleanup`), then
overwrites `raw_transcript` on the dispatch record with the full recording's. Phase 1 logs no
transcript text. Nobody decided to discard it; the table was built as temporary storage.

## What it costs

* **Phase 1 defects cannot be diagnosed after the fact.** DISP-2026-E301A3 showed
  "NUMBER 505 NEARLY 505" and no cross streets in phase 1; phase 2's transcript says "near", and
  what phase 1 heard is gone (#81).
* **Phase 1 cannot be measured.** The only stand-in is `tools/harness_phase1.py`, which replays
  the recording in the listener's chunks — and on 2026-09-13 it did not reproduce production on
  either of the two calls checked (it passed the completion check at 22 s where production
  passed at about 16 s, and at 16 s on a made-up "6 Coquitlam" where production passed at about
  20 s). #72's rule A was measured with that harness.

## The change

Write phase 1's chunk transcript, the chunk length in seconds, and its parsed fields (address,
units, grid, talk group, near roads, subaddress) to the dispatch record **once**, at phase 1, in a
field phase 2 never overwrites. The real chunk then replaces the replay as the record of what the
first screen was built from, and every call adds a measurement.

**What would falsify its value:** if the stored chunks show phase 1 and the replay harness
agreeing on most calls, the harness was adequate and this is only a diagnostic convenience.
Check on the first two weeks of stored chunks.

Supersedes the backlog line of 2026-09-13 ("The phase 1 transcript is not kept anywhere…").
