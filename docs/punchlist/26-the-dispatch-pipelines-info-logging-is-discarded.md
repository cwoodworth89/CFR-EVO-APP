# Punch list #26 — The dispatch pipeline's INFO logging is discarded

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | hygiene |
| **Area** | 🧱 Duplicated & Unsourced Frontend Constants |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L1086 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 26. The dispatch pipeline's INFO logging is discarded
> **Status**: ✅ **Closed 2026-08-22.** Root cause found and fixed; **requires an agent
> restart to take effect**.
>
> **Cause**: Python 3.14 changed the default multiprocessing start method on Linux from
> `fork` to `forkserver` (verified on the kiosk: `get_start_method()` → `forkserver` under
> 3.14.4). A forked child inherits the parent's configured logging; a forkserver child does
> not. `orchestration.run_dispatch_system` configured logging and *then* spawned the
> worker — correct under `fork`, silently broken on 3.14.
>
> **Fix**: `setup_logging` moved to `cfr_dispatch/logging_setup.py` and called *inside*
> `background_worker_loop`, which is correct under any start method. The worker writes
> `dispatch-worker.log` rather than sharing the orchestrator's file, because a
> `TimedRotatingFileHandler` is not safe across processes — both would race on the
> rotation rename.
>
> **Verified** with a forkserver child on the kiosk: INFO now appears in the configured
> format on stderr (so systemd captures it) and in the worker's own file, where previously
> only `WARNING:root:` survived.
>
> Recorded in `docs/standards/dependency-behaviour.md`.
>
> Original finding follows.
>
> ⚠️ **Open — found 2026-08-22 while trying to diagnose #25.**

The two-phase pipeline runs in a **separate process** from the audio agent, and that
process never configures logging. It therefore uses the default root logger at **WARNING**,
so every `logging.info` in the pipeline is dropped.

Evidence, from the same journal:

```
2026-08-22 14:34:04,724 - INFO - TONES CONFIRMED: 'Rescue Tone'        <- agent, configured
WARNING:root:[DISP-2026-5AC92A] Phase 2 transcription returned empty   <- worker, default
```

Different format, and different PIDs (`cfr-agent[1949135]` vs `cfr-agent[1949225]`). Only
WARNING and above survive from the worker.

**What is lost:**

* `Published {event_type} event to Mosquitto` — **zero** occurrences today despite
  dispatches arriving. This is why the broadcast sequence for #25 could not be read back.
* `[METRICS] Phase 1 TTA: …` and `[METRICS] Phase 2 Finalized …` — zero. These carry the
  DSP / STT / GIS / MQTT timings, so the performance-metrics work has no source data.
* Every geocoder and parser INFO line, including the ones added this session to report
  why an address was unresolved.

The system is therefore **not diagnosable from its logs** for anything that does not raise
a warning. A dispatch that resolves to the wrong place leaves no trace of how it got there.

**Fix**: configure logging in the worker process entry point with the same format and level
as the agent. Until then, treat "the logs show nothing" as "the logs are not recording",
not as evidence that nothing happened.

---

## ⚙️ Dispatch Worker Process Architecture

The two-phase pipeline runs in a `multiprocessing.Process` spawned by
`orchestration.run_dispatch_system`. The separation is justified — Whisper int8 inference
takes seconds and must not stall PortAudio capture, and a pipeline crash must not take the
audio listener down with it. These items are about how that separation is *implemented*.
