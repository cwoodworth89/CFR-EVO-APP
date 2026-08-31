# Punch list #28 — A stalled worker could block the audio listener — fixed

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | operational |
| **Area** | ⚙️ Dispatch Worker Process Architecture |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L1202 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 28. A stalled worker could block the audio listener — fixed
> **Status**: ✅ **Closed 2026-08-22.**

`dispatch_queue` is a `multiprocessing.Queue(maxsize=10)` and both producers used a
**blocking** `put()`:

* `audio_listener.py` — `phase_2_finalize`, carrying the complete audio buffer.
* `sound_capture.py` — `phase_1_check`, enqueued **inside the capture loop**.

If the worker stalled or died, the queue filled and `put()` blocked the audio listener
indefinitely. It would stop capturing tones with no error and no warning: the system would
look like a quiet night while being deaf. For a dispatch system that is the worst available
failure mode, because nothing distinguishes it from no calls arriving. The `phase_1_check`
case was worse still, stalling capture of a dispatch already in progress.

**Fix**: `audio_service.enqueue_dispatch_task` — never blocks, and prioritises by task type,
because the two are not equally important:

* `phase_2_finalize` carries the full audio and is what persists and broadcasts the call.
  Losing one loses the call, so it is admitted by **displacing an older queued item**.
* `phase_1_check` is an optimistic early alert on a partial buffer. Dropping one costs
  notification latency; phase 2 still produces the full record. It is **discarded**.

A full queue is logged at ERROR (phase 1) or CRITICAL (phase 2) rather than swallowed, so it
reaches the journal — which it now can, since #26.

Verified against a genuinely full queue:

```
phase_1_check    accepted=False  elapsed=0.000s   -> ERROR, discarded
phase_2_finalize accepted=True   elapsed=0.000s   -> CRITICAL, displaced OLD-0
survivors: ['OLD-1', 'OLD-2', 'NEW-P2']
```

The newest call gets through and neither call blocks.
