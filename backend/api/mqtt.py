"""
MQTT Event Broadcasting for CFR EVO API Gateway.
Manages Mosquitto MQTT connection and real-time dispatch state broadcasting.
"""
import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import paho.mqtt.client as mqtt

# MQTT Configuration
MQTT_HOST = os.environ.get("MQTT_BROKER_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_BROKER_PORT", "1883"))
MQTT_TOPIC = os.environ.get("MQTT_DISPATCH_TOPIC", "cfr/dispatches")

mqtt_client: Optional[mqtt.Client] = None


def init_mqtt():
    """Initializes and connects the Mosquitto MQTT client loop."""
    global mqtt_client
    try:
        mqtt_client = mqtt.Client(client_id="CFR_FastAPI_Gateway")
        mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        mqtt_client.loop_start()
        logging.info(f"Connected to Mosquitto MQTT broker at {MQTT_HOST}:{MQTT_PORT}")
    except Exception as e:
        logging.warning(
            f"Could not connect to MQTT broker ({MQTT_HOST}:{MQTT_PORT}): {e}. "
            "Dispatches will still save to DB."
        )


def publish_mqtt_event(event_type: str, record_dict: Dict[str, Any]):
    """Publishes a real-time event (INSERT, UPDATE, DELETE) to the station kiosk topic."""
    global mqtt_client
    if not mqtt_client:
        return
    try:
        payload = {
            "eventType": event_type,
            "new": record_dict,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        mqtt_client.publish(MQTT_TOPIC, json.dumps(payload, default=str), qos=1)
        logging.info(f"Published MQTT event '{event_type}' to topic '{MQTT_TOPIC}'")
    except Exception as e:
        logging.error(f"Failed to publish MQTT message: {e}")
