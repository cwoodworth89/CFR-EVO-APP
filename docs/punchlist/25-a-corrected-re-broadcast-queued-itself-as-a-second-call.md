# Punch list #25 — A corrected re-broadcast queued itself as a second call

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | operational |
| **Area** | 🧱 Duplicated & Unsourced Frontend Constants |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L1015 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 25. A corrected re-broadcast queued itself as a second call
> **Status**: ✅ **Closed 2026-08-22 (kiosk side).** Reported by the operator from a live call.

A call arrived, displayed correctly, and simultaneously raised the amber *"1 New Call
Queued — Tap to View Next"* banner. Tapping it cleared the banner and appeared to do
nothing else.

`useKioskQueue.handleInsert` had **no de-duplication**: it queued any INSERT arriving while
a call was active, without ever comparing `dispatch_id`. Tapping "view next" activated a
near-identical copy of the call already on screen, which reads as nothing happening.

> [!IMPORTANT]
> **Root cause corrected 2026-08-22.** This item first attributed the duplicate to phase 2
> re-broadcasting a corrected payload as an INSERT. **That was wrong**, and the broadcast
> log — readable only after #26 restored the pipeline's logging — settles it. For
> `DISP-2026-F33FA3` the backend published exactly one INSERT and one UPDATE:
>
> ```
> 15:12:00  Published INSERT event to Mosquitto MQTT   (phase 1)
> 15:12:20  Published UPDATE event to Mosquitto MQTT   (phase 2, Match=True, Corrected=False)
> ```
>
> The operator still saw the queued-call banner, and the reporter confirmed it appears
> **immediately**, not after a correction. The cause is **MQTT QoS 1 redelivery**: both
> publish and subscribe use `qos=1`, which guarantees *at-least-once* delivery. Duplicates
> are part of that contract — the protocol carries a DUP flag for exactly this — and the
> subscriber is required to be idempotent. Exactly-once is QoS 2.
>
> The de-duplication below is therefore **not a workaround for a backend defect**. The
> backend is correct; this is the idempotency QoS 1 requires of every subscriber. See
> `docs/standards/dependency-behaviour.md`.
>
> A duplicate delivery and a phase 2 correction produce the *same visible symptom*, which
> is why this could not be settled from the symptom alone.

The two payloads genuinely differed. For `DISP-2026-282647` the screen showed **map grid
61** while the stored record has **grid 68** — the operator was reading uncorrected phase 1
values with the correction sitting unread in the queue.

**Fix**: identity is `dispatch_id`. A re-broadcast of the active call merges and flashes
"CALL UPDATED", a re-broadcast of a queued call replaces it in place, and only a genuinely
different incident queues and chimes. Correct regardless of which event type carries the
correction.

**Fixed alongside**: `handleUpdate` matched on `id` **or `address`**. The corpus holds three
separate overdose dispatches at `3030 Gordon Ave`, so two active at once would have
overwritten each other's units, transcript and coordinates. It now matches on dispatch
identity only.

**Backend, not yet fixed — a latent ordering defect.** `phase1.py` broadcasts before it
records its session:

```
publish_mqtt_dispatch(db_payload, event_type="INSERT")   # line 132
...
session_manager.record_phase_1_success(...)              # line 150
```

If anything in that broadcast block raises, an INSERT has been emitted with no phase 1
session stored. Phase 2 then finds `p1_data` empty, takes the "Phase 1 was skipped"
single-phase branch, and publishes a **second INSERT** (`phase2.py:135`) rather than the
UPDATE the correction path uses. Recording the session *before* broadcasting would make an
un-tracked INSERT impossible.

Ruled out as causes: the correction paths publish `UPDATE` correctly
(`phase2.py:222/305/336/351`); `cleanup_session` runs in a `finally` after phase 2, so the
ordering is right; and the session TTL is 600 s against a 46 s dispatch, so eviction is not
plausible.

**Whether this is what happened was not established** — see #26.
