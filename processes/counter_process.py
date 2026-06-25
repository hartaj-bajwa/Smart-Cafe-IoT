"""
counter_process.py

Eseguibile per avviare un PersonCounterSensor parametrizzato.
python counter_process.py <room_id> <direction>
"""

import sys
import os
import time
import random
import logging
import paho.mqtt.client as mqtt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.models import PersonCounterSensor, SensorDescriptor

MQTT_BROKER_HOST = "localhost"
MQTT_BROKER_PORT = 1883
MIN_PASSAGE_INTERVAL_SEC = 2
MAX_PASSAGE_INTERVAL_SEC = 6

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("counter_process")

def build_mqtt_client(client_id: str) -> mqtt.Client:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    try:
        client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, keepalive=60)
        client.loop_start()
    except Exception as e:
        logger.error("Impossibile connettersi al broker MQTT: %s", e)
        raise
    return client

def run_counter(room_id: str, direction: str):
    sensor = PersonCounterSensor(room_id=room_id, direction=direction)
    descriptor = SensorDescriptor(sensor, measurement_name="cumulative_count", unit="count")

    client = build_mqtt_client(client_id=sensor.device_id)
    logger.info("Person Counter Sensor avviato | room=%s | direction=%s | topic=%s", room_id, direction, sensor.topic)

    try:
        while True:
            wait_time = random.uniform(MIN_PASSAGE_INTERVAL_SEC, MAX_PASSAGE_INTERVAL_SEC)
            time.sleep(wait_time)

            sensor.register_passage()
            try:
                payload = descriptor.to_json()
                client.publish(sensor.topic, payload, qos=1)
                logger.info(
                    "Passaggio rilevato (%s) | cumulative_count=%d | topic=%s",
                    direction, sensor.cumulative_count, sensor.topic
                )
            except Exception as publish_error:
                logger.error("Errore durante la pubblicazione MQTT: %s", publish_error)

    except KeyboardInterrupt:
        logger.info("Chiusura in corso...")
    finally:
        client.loop_stop()
        client.disconnect()
        logger.info("Person Counter Sensor arrestato correttamente.")

if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[2] not in ("entry", "exit"):
        print("Utilizzo: python counter_process.py <room_id> <entry|exit>")
        sys.exit(1)

    run_counter(room_id=sys.argv[1], direction=sys.argv[2])
