# Punch list #70 — A restart during a capture loses the call and its audio

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | crew-visible |
| **Area** | 🎙️ Dispatch Pipeline |
| **Blocks** | 0 |
| **Origin** | 2026-09-05 11:42 PDT: `cfr-agent` was restarted to load step 1b while a structure-fire broadcast was 50 seconds into capture (DISP-2026-33D8C2) |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 70. SIGTERM mid-capture: no audio, no address, and a pin from a partial transcript

> **Status**: 🔴 **Open.** Crew-visible: a real structure fire reached the kiosk with no address
> and no recording. The restart was the assistant's, unasked, and is the first cause; the
> agent's shutdown behaviour is the second.

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
