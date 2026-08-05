import requests
import urllib3

# Global Patch: Disable SSL certificate verification to handle SSL-intercepting municipal firewalls
original_request = requests.Session.request
def patched_request(self, *args, **kwargs):
    kwargs['verify'] = False
    return original_request(self, *args, **kwargs)
requests.Session.request = patched_request

# Silence InsecureRequestWarning messages in logs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import threading
import logging
from cfr_dispatch.orchestration import run_dispatch_system

def start_api_server():
    try:
        import os
        import sys
        import uvicorn
        base_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(base_dir)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        if base_dir not in sys.path:
            sys.path.insert(0, base_dir)
        logging.info("Starting local FastAPI API gateway on port 8000...")
        uvicorn.run("api.server:app", host="0.0.0.0", port=8000, log_level="info")
    except Exception as e:
        logging.warning(f"Could not bind API server in main thread: {e}")

if __name__ == "__main__":
    api_thread = threading.Thread(target=start_api_server, daemon=True)
    api_thread.start()
    run_dispatch_system()