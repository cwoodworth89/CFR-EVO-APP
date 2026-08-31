# Punch list #27 — The worker process is unsupervised

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | operational |
| **Area** | ⚙️ Dispatch Worker Process Architecture |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L1151 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 27. The worker process is unsupervised
> **Status**: ✅ **Closed 2026-08-22.** `cfr_dispatch/worker_supervisor.py` polls
> `is_alive()` every 15 s from a daemon thread and restarts the worker, logging every
> restart at CRITICAL.
>
> **Crash loops are handled rather than ignored.** Restarting forever buries the cause and
> looks like progress, so restarts are counted in a rolling window (5 in 600 s). Past the
> ceiling the supervisor stops restarting and **keeps reporting on every check** — going
> quiet after giving up would recreate the silent-dead-worker failure this exists to
> prevent.
>
> Verified with a worker that exits immediately:
>
> ```
> CRITICAL ProbeWorker died (exitcode 9). Restarting -- restart 1 of 3 ...
> CRITICAL ProbeWorker died (exitcode 9). Restarting -- restart 2 of 3 ...
> CRITICAL ProbeWorker died (exitcode 9). Restarting -- restart 3 of 3 ...
> CRITICAL ... restarted 3 times in 60 seconds. Refusing to restart again ...
> CRITICAL ProbeWorker is DEAD and the supervisor has stopped restarting it ...   (repeats)
> ```
>
> and a healthy worker left untouched (same pid, 0 restarts).
>
> Original finding follows.
>
> ⚠️ **Open — found 2026-08-22.**

`orchestration.py`:

```python
worker_process = multiprocessing.Process(target=background_worker_loop, args=(dispatch_queue,), daemon=True)
worker_process.start()
```

That is the only reference to it. The process is never checked with `is_alive()`, never
restarted, and emits no health signal. **A worker crash is permanent and silent** until
someone restarts the whole service.

Before #28 was fixed this compounded badly: a dead worker stopped draining the queue, the
queue filled, and the blocking `put()` then stopped the audio listener entirely. That path
is closed, but a dead worker still means no dispatch is ever processed, persisted or
broadcast — while the listener keeps happily detecting tones.

**Fix direction**: check `worker_process.is_alive()` from the listener loop, restart it, and
log the restart at CRITICAL. Restarting is cheap relative to the alternative — the worker
reloads the Whisper model and the GIS validator on start, which is seconds.

**Watch for**: a crash loop. If the worker dies repeatedly on the same task, restarting
forever is worse than stopping loudly. A restart counter with a ceiling, and a distinct
log line when the ceiling is hit, is the honest version.
