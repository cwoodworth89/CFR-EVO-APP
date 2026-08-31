# Punch list #29 — Phase 1 session state lives only in worker memory

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | operational |
| **Area** | ⚙️ Dispatch Worker Process Architecture |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L1238 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 29. Phase 1 session state lives only in worker memory
> **Status**: ✅ **Closed 2026-08-22.** Phase 1 state is now persisted in
> **`public.dispatch_sessions`** (`cfr_dispatch/session_store.py`), so it survives a worker
> restart. `DispatchSessionManager` keeps the same interface, so phase 1 and phase 2 call
> it unchanged.
>
> `candidates` are `DispatchData` dataclasses stored as JSON and rebuilt on read, because
> phase 2 reads `.address` and `.intersection` off them as attributes. Unknown keys are
> dropped and missing ones default, so a session written before a deploy does not crash the
> worker reading it after one — these rows outlive a restart by design.
>
> **The ordering defect is fixed too.** `phase1.py` now records the session *before*
> broadcasting. It was the other way round, so any exception in the broadcast block left an
> INSERT published with no session stored — and phase 2, finding nothing, took the
> "Phase 1 was skipped" branch and published a second INSERT. Recording first makes an
> untracked INSERT impossible.
>
> Verified across a real process boundary — written by one process, read by another:
>
> ```
> read back: transcript='CLEAN' units=['E1'] target.lat=49.27533
> count=2  types=['DispatchData', 'DispatchData']
> phase2-style pick -> address='3025 Lougheed Hwy'
>                      intersection='Lougheed Hwy & Westwood St'  map_grid='82'
> is_triggered before cleanup: True / after: False
> ```
>
> Execution profiles stay in memory deliberately: rolling metrics for one process, not
> dispatch state.
>
> Original finding follows.
>
> ⚠️ **Open — found 2026-08-22.**

`DispatchSessionManager` holds phase 1 candidates in a plain dict inside the worker
process (`worker.py`, `_phase_1_candidates`). Nothing persists it.

If the worker dies, every in-flight dispatch loses its phase 1 context. Phase 2 then finds
`p1_data` empty and takes the **"Phase 1 was skipped"** single-phase branch
(`phase2.py:127`), which publishes a second `INSERT` rather than the `UPDATE` the
correction path uses — the exact mechanism implicated in #25.

It is also inconsistent with the rest of the system: PostgreSQL is the single source of
truth for dispatches, vocabulary, hydrants, intersections and road closures, and this is
the one piece of dispatch state that is not in it.

**Fix direction**: persist phase 1 candidates to Postgres keyed by `dispatch_id`, with the
existing 600 s TTL enforced by a timestamp column. Phase 2 then reads them regardless of
which process — or which *instance* of the worker — handled phase 1.

**Related and worth fixing with it**: `phase1.py` broadcasts its `INSERT` *before* calling
`record_phase_1_success`. Any exception in that broadcast block leaves an INSERT emitted
with no session recorded, producing the same "phase 1 was skipped" outcome. Recording the
session first would make an untracked INSERT impossible.

---

## 🏷️ Response Terminology & Status Colour
