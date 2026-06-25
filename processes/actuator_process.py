"""
actuator_process.py

Eseguibile per avviare un SmartLightingActuator parametrizzato.
python actuator_process.py <room_id>
"""

import sys
import os
import time
import logging
import threading
import paho.mqtt.client as mqtt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.models import SmartLightingActuator, ActuatorDescriptor

MQTT_BROKER_HOST = "localhost"
MQTT_BROKER_PORT = 1883

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("actuator_process")

actuator = None

def on_connect(client, userdata, flags, reason_code, properties=None):  #eseguita all'avvenuta connessione al broker, si iscrive al topic dei comandi dell'attuatore
    if reason_code == 0:
        logger.info("Connesso al broker MQTT. Sottoscrizione a %s", actuator.topic)
        client.subscribe(actuator.topic, qos=1)
    else:
        logger.error("Connessione fallita, reason_code=%s", reason_code)

def on_message(client, userdata, msg): #eseguita alla ricezione mex da topic sottoscritto, estrae valore luminosita', aggiorna attuatore
    try:
        payload_str = msg.payload.decode("utf-8") #decodifica binario in stringa
        brightness = ActuatorDescriptor.from_json(payload_str) #deserializza stringa in valore float

        if 0.0 <= brightness <= 100.0:
            actuator.set_status(brightness)
            bars = int(brightness / 2)
            bar_str = "#" * bars + "-" * (50 - bars)
            logger.info("Comando ricevuto -> Luminosita': %.2f%% |%s|", brightness, bar_str)
        else:
            logger.warning("Valore luminosita' fuori range (0-100): %s", brightness)

    except ValueError as ve:
        logger.error("Payload MQTT non valido: %s", ve)
    except Exception as e:
        logger.error("Errore imprevisto gestione messaggio: %s", e)

def heartbeat_loop(client):
    """Thread in background che invia un heartbeat (Health Check) ogni 5 secondi."""
    while True:
        try:
            if actuator: #se attuatore inizializzato
                topic = f"cafe/{actuator.room_id}/lighting/status"
                client.publish(topic, payload='{"status": "online"}', qos=1)
        except Exception as e:
            logger.error("Errore nell'invio dell'heartbeat: %s", e)
        time.sleep(5)

def run_actuator(room_id: str):
    global actuator
    actuator = SmartLightingActuator(room_id=room_id)
    
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=actuator.device_id)
    client.on_connect = on_connect
    client.on_message = on_message

    logger.info("Smart Lighting Controller avviato per room_id=%s", room_id)

    try:
        client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, keepalive=60)
        
        # Avvio il thread dell'heartbeat
        threading.Thread(target=heartbeat_loop, args=(client,), daemon=True).start()
        
        client.loop_forever()
    except KeyboardInterrupt:
        logger.info("Chiusura in corso...")
    except Exception as e:
        logger.error("Errore MQTT: %s", e)
    finally:
        client.disconnect()
        logger.info("Smart Lighting Controller arrestato correttamente.")

if __name__ == "__main__": #verifca se file eseguito come script, e che abbia 2 argomenti (il primo è il file, il secondo è il room_id)
    if len(sys.argv) != 2:
        print("Utilizzo: python actuator_process.py <room_id>")
        sys.exit(1)

    run_actuator(room_id=sys.argv[1])
