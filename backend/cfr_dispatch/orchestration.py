import os
import time
import datetime
import logging
import multiprocessing

from cfr_dispatch.logging_setup import setup_logging
from cfr_dispatch.worker import background_worker_loop, get_shared_validator
from cfr_dispatch.worker_supervisor import WorkerSupervisor
from cfr_dispatch.audio_listener import run_audio_listener_loop
from cfr_dispatch.pipeline import (
    build_dispatch_payload
)

# setup_logging moved to cfr_dispatch.logging_setup so the worker process can call it too.
# It is not inherited across a multiprocessing spawn on Python 3.14, whose default start
# method on Linux is forkserver -- see that module for the full explanation.
def run_dispatch_system():
    """Main program entrypoint. Initiates multiprocessing worker and PortAudio listener loop."""
    setup_logging()
    local_api_url = os.environ.get("LOCAL_API_URL", "http://localhost:8000")
    logging.info(f"CFR EVO Orchestrator initializing. API Gateway: {local_api_url}")
    
    dispatch_queue = multiprocessing.Queue(maxsize=10)
    logging.info("Starting background worker process...")

    # Supervised, not fire-and-forget. The worker used to be started once and never looked
    # at again, so a crash was permanent and silent: the listener kept capturing dispatches
    # that nothing would process, persist or broadcast (punch-list #27).
    supervisor = WorkerSupervisor(
        target=background_worker_loop,
        args=(dispatch_queue,),
    )
    supervisor.start()

    try:
        run_audio_listener_loop(dispatch_queue)
    except KeyboardInterrupt:
        logging.info("Listener stopped by user.")
    finally:
        supervisor.stop()
        dispatch_queue.put(None)
        logging.info("CFR EVO Dispatch System shut down.")

if __name__ == "__main__":
    run_dispatch_system()
