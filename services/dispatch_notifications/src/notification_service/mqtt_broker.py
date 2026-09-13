import os
import json
import logging
from datetime import datetime, timezone
import paho.mqtt.client as mqtt

MQTT_HOST = os.environ.get("MQTT_BROKER_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_BROKER_PORT", "1883"))
MQTT_TOPIC = os.environ.get("MQTT_DISPATCH_TOPIC", "cfr/dispatches")

def publish_mqtt_dispatch(payload: dict, event_type: str = "INSERT", is_test: bool = None) -> bool:
    """
    Publishes dispatch payload directly to Mosquitto MQTT broker for real-time station alerts.
    Station kiosks listen over WebSockets on port 9001 (or TCP 1883).
    """
    if is_test is None:
        is_test = bool(payload.get("is_test", False))
        
    try:
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"cfr-dispatch-publisher-{os.getpid()}"
        )
        client.connect(MQTT_HOST, MQTT_PORT, keepalive=10)
        # The network loop reads the broker's PUBACK. Without it wait_for_publish below never
        # saw one and returned only at its 3 s timeout, on every publish: measured on the
        # kiosk 2026-09-13, 3003 ms per call against 1 ms with the loop running, while the
        # message itself arrived in 7 ms either way (paho-mqtt 2.1.0 returns silently on
        # that timeout).
        client.loop_start()

        envelope = {
            "event": event_type,
            "topic": MQTT_TOPIC,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "is_test": is_test,
            "payload": payload
        }
        
        msg = json.dumps(envelope)
        result = client.publish(MQTT_TOPIC, msg, qos=1)
        result.wait_for_publish(timeout=3.0)
        acknowledged = result.is_published()
        client.disconnect()
        client.loop_stop()
        if not acknowledged:
            logging.warning(f"{event_type} event sent to Mosquitto MQTT but not acknowledged within 3 s.")
            return False
        logging.info(f"Published {event_type} event to Mosquitto MQTT ({MQTT_HOST}:{MQTT_PORT}/{MQTT_TOPIC}) [is_test={is_test}].")
        return True
    except Exception as e:
        logging.warning(f"Could not publish alert to Mosquitto MQTT: {e}")
        return False
