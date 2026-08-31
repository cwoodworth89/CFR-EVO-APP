# Punch list #59 — Phase 2 crashed after saving audio, before recording its URL

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | operational |
| **Area** | 🎙️ Dispatch Pipeline |
| **Blocks** | 1 |
| **Origin** | Reported by the operator 2026-08-31: "no audio file player available" |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 59. An UnboundLocalError silently emptied `audio_url` on every dispatch

> **Status**: ✅ **Closed 2026-08-31.** Fixed (`ba76b72`), deployed, and the affected records
> backfilled from the files already on disk.

**The recordings were never at risk.** 543 `.wav` files sit in
`backend/audio_files/recordings/`, including every affected call, and the API served them
`200 audio/x-wav` with the correct byte count throughout. Only the database column was empty —
and `VerificationSidebar.jsx:204` gates the entire player block on `selectedCall.audio_url`, so
a NULL column renders **no player at all** rather than a broken one. That is why it read as
"the audio player has disappeared".

#### The cause

```
INFO  [DISP-2026-C1ECB0] Successfully saved audio file locally to .../DISP-2026-C1ECB0.wav
INFO  [DISP-2026-C1ECB0] [Phase 2] Verification MATCH: Address confirmed ('2979 glen dr')
ERROR [DISP-2026-C1ECB0] Error in process_phase_2_finalize:
      cannot access local variable 'responding_units' where it is not associated with a value
```

`responding_units` is bound **only** inside the `if not p1_data:` single-phase fallback
(`phase2.py:162`). On the normal path — where Phase 1 ran — it is never assigned, yet both
`compute_review_flags` calls reached for it. The correct name there is `p2_responding_units`,
bound in the MATCH branch and again in the correction branch, and already used correctly by
every neighbouring line in the same dicts.

#### Why the damage looked selective

Audio is written to disk, the `target` PATCH lands, *then* the crash happens — before the
update carrying `audio_url` and `audio_duration`. So an affected record has `map_grid`,
`radio_channel`, `review_flags`, `routing_metrics` and `rings` all present and looks fully
processed, missing exactly one thing.

| Day | Calls | Missing audio |
|:--|--:|--:|
| ≤ 2026-08-29 | — | **0** |
| 2026-08-30 | 11 | 5 |
| 2026-08-31 | 11 | 10 |

The start date matches `compute_review_flags` arriving on 2026-08-30 with the
confidence-score replacement (**#45b**).

#### Backfill

15 records repaired: `audio_url` set from the file that already existed, `audio_duration` read
from each **WAV header** rather than assumed. One record, `DISP-2026-52BB4C` (2026-08-15,
`2601 Lougheed Hwy`), has no file on disk and was deliberately **left NULL** — an absent
recording reported as absent (§6.1), not given a URL pointing at nothing.

Three records from 2026-08-06 carry a URL with no duration. Those predate duration tracking
and are unrelated.

#### What did not catch it

`pyflakes` reports nothing here — it is not a flow analysis and cannot see a name bound in one
branch and read in another. The frontend has a pre-commit guard for exactly this class
(`no-undef` and TDZ, `.githooks/pre-commit`) precisely because such code compiles cleanly and
throws at runtime; **Python has no equivalent guard in this repo.**

The error was in `journalctl -u cfr-agent` from the first occurrence, with the dispatch id and
the variable name, and went unread for two days. Punch-list **#26** restored that logging in
August; nothing watches it.
