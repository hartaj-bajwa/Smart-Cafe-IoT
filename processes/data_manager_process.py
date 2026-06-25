"""
data_manager_process.py

Server Flask + MQTT Manager (Digital Twin).
Gestisce più stanze dinamicamente.
"""

import math
import logging
import threading
import json
import sys
import os
import time

# Permette di importare i package model, resources, dto dalla directory superiore
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from flask_restful import Api
import paho.mqtt.client as mqtt

from model.models import CafeRoomState, ActuatorDescriptor, SmartLightingActuator
from resources.cafe_resources import StatusResource, ConfigResource

MQTT_BROKER_HOST = "localhost"
MQTT_BROKER_PORT = 1883
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("data_manager")

class CafeDataManager:
    def __init__(self):
        self._lock = threading.Lock()
        self.states = {} # Mappa room_id -> CafeRoomState

    def _recompute_brightness(self, room_id):
        state = self.states[room_id]
        state.current_brightness = round(40 + 30 * (1 - math.exp(-state.k * state.current_people)), 2)

    def update_occupancy(self, room_id, direction, total_count):
        with self._lock:
            if room_id not in self.states:
                self.states[room_id] = CafeRoomState(room_id)
                logger.info(f"Nuova stanza rilevata: {room_id}. Digital Twin creato.")
            
            state = self.states[room_id]
            if direction == "entry": 
                state.last_entry_total = total_count
            elif direction == "exit":
                state.last_exit_total = total_count
            
            # Calcolo n = Entrate - Uscite
            n = state.last_entry_total - state.last_exit_total
            if n < 0: n = 0
            state.current_people = n
            
            self._recompute_brightness(room_id)
            return state.current_brightness

dm = CafeDataManager()
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="data-manager-001")

def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        logger.info("Connesso al broker MQTT. Sottoscrizione ai topic...")
        client.subscribe("cafe/+/counter/+")
        client.subscribe("cafe/+/lighting/status")
    else:
        logger.error("Connessione MQTT fallita con codice %s", reason_code)

def on_message(client, userdata, msg):
    topic = msg.topic
    try:
        payload_str = msg.payload.decode("utf-8")
        parts = topic.split('/')
        if len(parts) >= 4 and parts[0] == 'cafe':
            room_id = parts[1]
            device_cat = parts[2]
            direction = parts[3]

            if device_cat == 'lighting' and direction == 'status':
                with dm._lock:
                    if room_id not in dm.states:
                        dm.states[room_id] = CafeRoomState(room_id)
                    dm.states[room_id].last_seen_actuator = time.time()
                return

            if device_cat == 'counter':
                data = json.loads(payload_str)
                if not isinstance(data, list) or len(data) == 0 or "v" not in data[0]:
                    return
                total = int(data[0]["v"])
                
                new_brightness = dm.update_occupancy(room_id, direction, total)
                logger.info(f"[{room_id}] {direction} -> persone={dm.states[room_id].current_people}, lum={new_brightness}%")
                
                # Comando MQTT all'attuatore specifico della stanza
                from model.models import SmartLightingActuator, ActuatorDescriptor
                temp_actuator = SmartLightingActuator(room_id=room_id)
                temp_actuator.set_status(new_brightness)
                desc = ActuatorDescriptor(temp_actuator)
                client.publish(temp_actuator.topic, desc.to_json(), qos=1)
    except Exception as e:
        logger.error("Errore on_message: %s", e)

mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

app = Flask(__name__)
api = Api(app)

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <title>Smart Cafe Global Monitor</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background-color: #f4f4f9; color: #333; }
        .grid { display: flex; flex-wrap: wrap; gap: 20px; }
        .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); width: 300px; }
        h1 { font-size: 24px; margin-bottom: 20px; width: 100%; }
        h2 { font-size: 20px; margin-top: 0; color: #555; }
        p { font-size: 16px; margin: 8px 0; }
        .val { font-weight: bold; color: #0056b3; }
    </style>
    <script>
        function updateDashboard() {
            fetch('/status')
                .then(response => response.json())
                .then(data => {
                    const grid = document.getElementById('grid');
                    grid.innerHTML = '';
                    let totalPeople = 0;
                    for (const [roomId, state] of Object.entries(data)) {
                        if (roomId === "error") continue;
                        totalPeople += state.current_people;

                        const actuatorStatus = state.actuator_online 
                            ? '<span style="color: green;">🟢 ONLINE</span>' 
                            : '<span style="color: red;">🔴 OFFLINE</span>';

                        grid.innerHTML += `
                            <div class="card">
                                <h2>Stanza: ${state.room_id}</h2>
                                <p>Attuatore Luci: ${actuatorStatus}</p>
                                <p>Persone presenti: <span class="val">${state.current_people}</span></p>
                                <p>Luminosità: <span class="val">${state.current_brightness}%</span></p>
                                <p>Reattività (k): <span class="val">${state.k}</span></p>
                            </div>
                        `;
                    }
                    const totalEl = document.getElementById('total-people');
                    if (totalEl) totalEl.innerText = totalPeople;
                })
                .catch(error => console.error('Errore nel fetch:', error));
        }
        setInterval(updateDashboard, 2000);
        window.onload = updateDashboard;
    </script>
</head>
<body>
    <h1>Smart Cafe Global Monitor</h1>
    <div style="background: #0056b3; color: white; padding: 15px; border-radius: 8px; margin-bottom: 20px; font-size: 18px; width: 300px; text-align: center;">
        Totale Persone (Tutte le Stanze): <br>
        <span id="total-people" style="font-size: 32px; font-weight: bold;">0</span>
    </div>
    <div class="grid" id="grid">
        <p>In attesa di dati...</p>
    </div>
</body>
</html>
"""

@app.route("/")
def index():
    return DASHBOARD_HTML

api.add_resource(StatusResource, '/status', '/status/<string:room_id>', resource_class_kwargs={'data_manager': dm})
api.add_resource(ConfigResource, '/config/<string:room_id>', resource_class_kwargs={'data_manager': dm})

if __name__ == '__main__':
    logger.info("Avvio DataManager Process (Digital Twin)")
    try:
        mqtt_client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, keepalive=60)
        mqtt_client.loop_start()
    except Exception as e:
        logger.error("Impossibile connettersi al broker: %s", e)
        exit(1)
        
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False, use_reloader=False)
