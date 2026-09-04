import os
import sys

from _repo import BACKEND  # tools/_repo.py locates the repo and puts backend/ and services/*/src on sys.path
backend_dir = str(BACKEND)
root_dir = os.path.dirname(backend_dir)
service_path = os.path.join(root_dir, "services", "dispatch_notifications", "src")
if service_path not in sys.path:
    sys.path.append(service_path)

from notification_service.ntfy_broker import post_to_ntfy

def main():
    print("--- Sending Dual Notification Push (Local Container + Cloud Relay) ---")
    payload = {
        "dispatch_id": "TEST-DUAL-PUSH",
        "incident_type": "Structure Fire - Test",
        "responding_units": ["E1", "E2", "R2"],
        "target": {
            "address": "2648 Sandstone Cres",
            "lat": 49.28,
            "lng": -122.80
        }
    }
    success = post_to_ntfy(payload, ["chief-master", "engine-1"])
    print(f"Dual Push Result: {success}")

if __name__ == "__main__":
    main()
