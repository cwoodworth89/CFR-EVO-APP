import os
import time
import datetime
import logging
import multiprocessing
from logging.handlers import TimedRotatingFileHandler

from cfr_dispatch.config.cloud import VERBOSITY_LEVEL
from cfr_dispatch.worker import background_worker_loop, get_shared_validator
from cfr_dispatch.audio_listener import run_audio_listener_loop
from cfr_dispatch.pipeline import (
    build_dispatch_payload,
    process_full_dispatch
)

def setup_logging():
    """Configures global daily 08:00 shift rotation log handlers and stream formatters."""
    logging.Formatter.converter = time.localtime
    logger = logging.getLogger()
    
    if VERBOSITY_LEVEL == 0:
        log_level = logging.ERROR
    elif VERBOSITY_LEVEL == 1:
        log_level = logging.INFO
    else:
        log_level = logging.DEBUG
        
    logger.setLevel(log_level)
    if logger.hasHandlers():
        logger.handlers.clear()
        
    # Timed Rotating File Handler (rotates daily at 08:00, retains 10 backups)
    file_handler = TimedRotatingFileHandler(
        'dispatch.log',
        when='D',
        interval=1,
        backupCount=10,
        atTime=datetime.time(8, 0, 0)
    )
    file_handler.setLevel(logging.DEBUG if VERBOSITY_LEVEL >= 2 else logging.INFO)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)-8s - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO if VERBOSITY_LEVEL >= 1 else logging.WARNING)
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)-8s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # Silence verbose third-party loggers
    logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

def process_and_post_payload(*args, **kwargs):
    """Backward compatibility alias for build_dispatch_payload."""
    return build_dispatch_payload(*args, **kwargs)

def run_dispatch_system():
    """Main program entrypoint. Initiates multiprocessing worker and PortAudio listener loop."""
    setup_logging()
    local_api_url = os.environ.get("LOCAL_API_URL", "http://localhost:8000")
    logging.info(f"CFR EVO Orchestrator initializing. API Gateway: {local_api_url}")
    
    dispatch_queue = multiprocessing.Queue(maxsize=10)
    logging.info("Starting background worker process...")
    worker_process = multiprocessing.Process(target=background_worker_loop, args=(dispatch_queue,), daemon=True)
    worker_process.start()

    try:
        run_audio_listener_loop(dispatch_queue)
    except KeyboardInterrupt:
        logging.info("Listener stopped by user.")
    finally:
        dispatch_queue.put(None)
        logging.info("CFR EVO Dispatch System shut down.")

if __name__ == "__main__":
    run_dispatch_system()
