import requests
import json
import time

url = "http://100.95.146.94:8000/api/dispatches"

payload = {
    "dispatch_id": f"DISP-TEST-{int(time.time())}",
    "incident_type": "Medical Aid - Collapse",
    "responding_units": ["E1", "R2"],
    "target": {
        "address": "3030 Gordon Ave",
        "subaddress": "Rain City Housing",
        "intersection": "Christmas Way and Westwood St",
        "map_grid": "68",
        "radio_channel": "10 Combined Response",
        "captured_tones": ["Rescue Tone"],
        "lat": 49.2701565,
        "lng": -122.7918275,
        "rings": []
    },
    "raw_transcript": "Coquitlam Engine 1 Rescue 2 respond emergency medical aid collapse 3030 Gordon Avenue Rain City Housing near Christmas Way and Westwood Street use talk group 10 combined response Coquitlam map grid 68",
    "sanitized_transcript": "Coquitlam Engine 1, Rescue 2, respond emergency, medical aid - collapse, 3030 Gordon Ave Rain City Housing, near Christmas Way and Westwood St, use talk group 10 combined response coquitlam, map grid 68",
    "confidence_score": 100.0,
    "verify_location": False
}

print(f"Injecting test call payload to {url}...")
res = requests.post(url, json=payload)
print(f"Response Status: {res.status_code}")
if res.status_code in (200, 201):
    print("Test Call Successfully Injected and Processed!")
    print(json.dumps(res.json(), indent=2))
else:
    print(f"Error: {res.text}")
