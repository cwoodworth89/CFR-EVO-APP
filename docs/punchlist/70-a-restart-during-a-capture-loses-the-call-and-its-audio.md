# Punch list #70 — A restart during a capture loses the call and its audio

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | crew-visible |
| **Area** | 🎙️ Dispatch Pipeline |
| **Blocks** | 0 |
| **Origin** | 2026-09-05 11:42 PDT: `cfr-agent` was restarted to load step 1b while a structure-fire broadcast was 50 seconds into capture (DISP-2026-33D8C2) |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 70. SIGTERM mid-capture: no audio, no address, and a pin from a partial transcript

> **Status**: ✅ **Closed 2026-09-06 — the first restart under the new code, 13:54 kiosk time, shows the handler in the journal: SIGTERM caught, listener told to stop, worker exiting on its signal, then systemd's stop.** *(Opened as: 🟡 Built and deployed 2026-09-05 19:48 PDT (`e0b0632`, unit `TimeoutStopSec=150`); closes on > the first restart whose journal shows the drain. *(Opened as: > 🔴 Open.)* Crew-visible: a real structure fire reached the kiosk with no address and no > recording. The restart was the assistant's, unasked, and is the first cause; the agent's > shutdown behaviour is the second.)*

### What happened

```
11:41:17  TONES CONFIRMED: 'Chief Tone'   STATE: CAPTURING DISPATCH (ID: DISP-2026-33D8C2)
11:41:23  worker: phase-1 STT on 10 s, then 13 s, 16 s ... of the capture
11:42:07  SIGTERM (kill -TERM on the main PID, followed by a 15 s wait)
11:42:24  new process: "Successfully opened audio stream"
```

The capture never finished. No WAV was written (`audio_url` is null, `audio_duration` null),
phase 2 never ran, and the row the kiosk shows is the last phase-1 payload, built on a
transcript that ends *"respond emergency structure fire 166 coquitlam map grid 68"*. The model
in service completes cut audio with the template's tail, so the "166", the "coquitlam" and
the grid are not evidence of anything the dispatcher said. The geocoder read *166 Coquitlam*
as a house number on a street named Coquitlam and, finding no parcel, placed the call at the
street centroid of Coquitlam Ave with the approximate-location banner. Round 2 of the
broadcast played after the new process started, but tones precede round 1 only, so it was
not captured.

Nothing in this system can recover the address; CAD or the radio is the source for that call.

The payload the kiosk showed was published by phase 1 at 11:41:40, 23 seconds in, before the
restart: the model completed the cut chunk with *"166 coquitlam map grid 68"* and the completion
check accepted it. That is its own defect, #72; the restart is what stopped phase 2 from
correcting it.

### Two defects

1. **Process rule, already in force:** the agent is not restarted without the operator
   choosing the moment, and never with `CAPTURING DISPATCH` open in the log. Deploys are a
   `git pull`; the restart is the operator's.
2. **The agent has no graceful stop.** `kill -TERM` (what `systemctl restart` sends) ends
   the process mid-capture. It should stop taking new captures, finish the one in progress
   through phase 2 and the WAV write, then exit, with `TimeoutStopSec` on the unit long
   enough for a 75 s broadcast plus transcription. Until that exists, a restart is only safe
   between calls, and the operator cannot see from the kiosk whether one is in progress.

### To decide

Whether a partial phase-1 transcript that ends in the template's tail should produce a
placed pin at all, or the Tier 1 unresolved card. The banner said what the pin was, which is
the current design (#12); a structure fire pinned at the midpoint of Coquitlam Ave is what
that design produces from cut audio.

### Built 2026-09-05

`backend/cfr_dispatch/shutdown.py`. The main process turns SIGTERM into a flag; the listener
returns at the next quiet moment, or after the capture in progress has ended and been queued
(`audio_listener.py`). The worker ignores SIGTERM and exits on the poison pill, so systemd's
control-group signal cannot cut phase 2 short (`worker.py`). On the way out the orchestrator
stops the supervisor respawning, sends the pill and waits up to 60 s for the worker to drain
(`drain_and_stop`). Tests in `test_shutdown.py`: the flag, the ignore, the order, the timeout.

**Still to do, by the operator, since `tcfire` can restart the unit without a password but
cannot edit it:** the unit's stop timeout is 90 s, which cuts a 75 s capture plus phase 2
short. `setup_kiosk.sh` now writes `TimeoutStopSec=150`; on the running kiosk:

```bash
sudo systemctl edit cfr-agent
```
and add, then save:
```
[Service]
TimeoutStopSec=150
```
then `sudo systemctl daemon-reload` and a restart. **Done by the operator at 19:48 PDT**: the
drop-in is in place, the effective timeout reads 2 min 30 s, and the process started at 19:46
carries the handler. The next restart is the proof: the journal should show *Stop requested*
and *Worker drained* rather than an instant deactivation. `tools/kiosk_capture_state.sh` stays the pre-restart check
until the first restart under the new code proves the drain in the journal.

### Closed 2026-09-06

Operator's go; `tools/kiosk_capture_state.sh` said safe (last capture finalised, tones 1303 s
earlier); `sudo systemctl restart cfr-agent` at 13:54:33. The journal, in order:

```
SIGTERM received: finishing any capture in progress, then exiting.
Stop requested with no capture in progress; listener exiting.
CFR EVO Dispatch System shut down.
Worker received shutdown signal. Exiting.
cfr-agent.service: Deactivated successfully.
```

Before this change the same restart was an instant kill (the 11:42 loss on 2026-09-05). What
this proves is the no-capture path: the signal is caught, the listener leaves at its own quiet
point, the worker drains on the poison pill, systemd waits. The in-capture path (listener
finishes the broadcast and queues it, worker finishes phase 2, up to the 150 s
`TimeoutStopSec`) is covered by `backend/tests/test_shutdown.py` and has not yet been seen
live; the pre-restart check stays the practice, and the first restart that lands during a
capture is the remaining evidence. Reopen if that journal shows anything but a finalised call.
