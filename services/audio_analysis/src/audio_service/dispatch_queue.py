"""Handing work to the background dispatch worker without ever blocking the listener.

WHY THIS EXISTS
---------------
The audio listener passed work to the pipeline worker with a plain blocking
`multiprocessing.Queue.put()` on a queue bounded at `maxsize=10`. If the worker stalled or
died -- and it is `daemon=True` with no supervision, so a crash is permanent and silent --
the queue filled and `put()` blocked **the audio listener** indefinitely.

The listener would simply stop capturing tones. No error, no warning: the system would look
like a quiet night while being deaf. For a dispatch system that is the worst available
failure mode, because nothing distinguishes it from no calls arriving.

One of the two producers is worse still: the `phase_1_check` enqueue runs *inside* the
capture loop, so blocking there stalls the capture of a dispatch already in progress.

THE RULE: the listener never blocks. Losing a task loudly beats going deaf silently.

PRIORITY
--------
The two task types are not equally important:

* `phase_2_finalize` carries the **complete audio buffer** and is what persists and
  broadcasts the dispatch. Losing one loses the call.
* `phase_1_check` is an optimistic early alert on a partial buffer. Dropping one costs some
  seconds of notification latency; phase 2 still runs and still produces the full record.

So when the queue is full, a `phase_1_check` is discarded, and a `phase_2_finalize` is
admitted by displacing an older queued item rather than being dropped itself.
"""
import logging
from queue import Full, Empty

PHASE_1 = "phase_1_check"


def enqueue_dispatch_task(dispatch_queue, task: dict) -> bool:
    """Enqueue a worker task without blocking. Returns True if it was accepted.

    A full queue means the worker is not draining, which is itself an incident: it is logged
    at ERROR or CRITICAL rather than swallowed, so it appears in the journal.
    """
    task_type = task.get("type", "unknown")
    dispatch_id = task.get("dispatch_id", "unknown")

    try:
        dispatch_queue.put_nowait(task)
        return True
    except Full:
        pass

    if task_type == PHASE_1:
        logging.error(
            "[%s] Dispatch worker queue is FULL -- discarding %s. The worker is not "
            "draining; phase 2 will still run and produce the full record, but early "
            "notification is delayed. Check that the worker process is alive.",
            dispatch_id, PHASE_1,
        )
        return False

    # phase_2_finalize, or anything unrecognised: too important to drop. Make room.
    try:
        displaced = dispatch_queue.get_nowait()
        logging.critical(
            "[%s] Dispatch worker queue is FULL -- displaced a queued %s for [%s] to admit "
            "this %s. The worker is not draining and dispatch work is being LOST. "
            "Investigate the worker process immediately.",
            dispatch_id,
            (displaced or {}).get("type", "unknown") if isinstance(displaced, dict) else "task",
            (displaced or {}).get("dispatch_id", "unknown") if isinstance(displaced, dict) else "unknown",
            task_type,
        )
    except Empty:
        # Drained between the failed put and here; just retry.
        pass
    except Exception as e:
        logging.critical("[%s] Could not make room in the dispatch queue: %s", dispatch_id, e)

    try:
        dispatch_queue.put_nowait(task)
        return True
    except Full:
        logging.critical(
            "[%s] Dispatch worker queue still FULL -- %s could NOT be queued and this "
            "dispatch is LOST. The audio was captured but will not be processed, persisted "
            "or broadcast.",
            dispatch_id, task_type,
        )
        return False
