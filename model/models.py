"""
model/models.py

Gerarchia OOP dei dispositivi (Device -> Sensor / Actuator)
e classi Descriptor per il partizionamento SenML.
Inoltre definisce CafeRoomState (il Digital Twin di una singola stanza).
"""

import time
import json
import uuid

# ---------------------------------------------------------------------------
# STATO CONDIVISO DELLA STANZA (Digital Twin) - Data Model
# ---------------------------------------------------------------------------
class CafeRoomState:
    """Rappresenta l'ombra digitale (Digital Twin) di una specifica stanza"""
    def __init__(self, room_id):
        self.room_id = room_id
        self.current_people = 0
        self.current_brightness = 40.0
        self.k = 0.15
        self.last_entry_total = 0
        self.last_exit_total = 0
        self.last_seen_actuator = 0.0 # Timestamp dell'ultimo heartbeat dell'attuatore

# ---------------------------------------------------------------------------
# CLASSE BASE: Device
# ---------------------------------------------------------------------------
class Device:
    def __init__(self, device_id: str, device_type: str, manufacturer: str = "SmartCafe-Inc"):
        if not device_id:
            device_id = str(uuid.uuid4())
        self.device_id = device_id
        self.type = device_type
        self.manufacturer = manufacturer

    def __repr__(self):
        return f"<Device id={self.device_id} type={self.type}>"


# ---------------------------------------------------------------------------
# SOTTOCLASSE: Sensor - Eredita da Device, aggiunge value e timestamp (fondamentale per heartbeat)
# ---------------------------------------------------------------------------
class Sensor(Device):
    def __init__(self, device_id: str, device_type: str, manufacturer: str = "SmartCafe-Inc"):
        super().__init__(device_id, device_type, manufacturer)
        self.value = 0
        self.timestamp = self._current_timestamp_ms()

    @staticmethod
    def _current_timestamp_ms() -> int:
        return int(time.time() * 1000)

    def update_value(self, new_value):
        self.value = new_value
        self.timestamp = self._current_timestamp_ms()


# ---------------------------------------------------------------------------
# SOTTOCLASSE: Actuator - Eredita da Device, aggiunge status
# ---------------------------------------------------------------------------
class Actuator(Device):
    def __init__(self, device_id: str, device_type: str, manufacturer: str = "SmartCafe-Inc"):
        super().__init__(device_id, device_type, manufacturer)
        self.status = 0

    def set_status(self, new_status):
        self.status = new_status


# ---------------------------------------------------------------------------
# DESCRIPTOR: SensorDescriptor - per trasformare i dati dei sensori in SenML e poi JSON
# ---------------------------------------------------------------------------
class SensorDescriptor:
    def __init__(self, sensor: Sensor, measurement_name: str = "cumulative_count", unit: str = "count"):
        self.sensor = sensor
        self.measurement_name = measurement_name
        self.unit = unit

    def to_senml_pack(self) -> list:
        return [
            {
                "bn": self.sensor.device_id,
                "n": self.measurement_name,
                "u": self.unit,
                "v": self.sensor.value,
                "t": self.sensor.timestamp,
            }
        ]

    def to_json(self) -> str:
        return json.dumps(self.to_senml_pack())


# ---------------------------------------------------------------------------
# DESCRIPTOR: ActuatorDescriptor - per trasformare i dati degli attuatori in SenML e poi JSON
# ---------------------------------------------------------------------------
class ActuatorDescriptor:
    def __init__(self, actuator: Actuator, measurement_name: str = "brightness_level", unit: str = "%"):
        self.actuator = actuator
        self.measurement_name = measurement_name
        self.unit = unit

    def to_senml_pack(self) -> list:
        return [
            {
                "bn": self.actuator.device_id,
                "n": self.measurement_name,
                "u": self.unit,
                "v": self.actuator.status,
                "t": Sensor._current_timestamp_ms(),
            }
        ]

    def to_json(self) -> str:
        return json.dumps(self.to_senml_pack())

    @staticmethod
    def from_json(payload: str) -> float:
        data = json.loads(payload)
        if not isinstance(data, list) or len(data) == 0 or "v" not in data[0]:
            raise ValueError("Payload SenML non valido: campo 'v' mancante")
        return data[0]["v"]


# ---------------------------------------------------------------------------
# SOTTOCLASSE SPECIALIZZATA: PersonCounterSensor - gestisce i sensori di conteggio persone, aggiunge validazione direzione, registra passaggio e cumulativo passaggi e topic
# ---------------------------------------------------------------------------
class PersonCounterSensor(Sensor):
    VALID_DIRECTIONS = ("entry", "exit")

    def __init__(self, room_id: str, direction: str, device_id: str = None, manufacturer: str = "SmartCafe-Inc"):
        if direction not in self.VALID_DIRECTIONS:
            raise ValueError(f"direction deve essere uno tra {self.VALID_DIRECTIONS}, ricevuto: {direction}")

        if not device_id:
            device_id = f"counter-{room_id}-{direction}-001"

        super().__init__(device_id, device_type="it.unimore.cafe.sensor.counter", manufacturer=manufacturer)
        self.room_id = room_id
        self.direction = direction
        self.cumulative_count = 0

    def register_passage(self):
        self.cumulative_count += 1
        self.update_value(self.cumulative_count)

    @property
    def topic(self) -> str:
        return f"cafe/{self.room_id}/counter/{self.direction}"


# ---------------------------------------------------------------------------
# SOTTOCLASSE SPECIALIZZATA: SmartLightingActuator - gestisce l'attuatore di illuminazione, topic
# ---------------------------------------------------------------------------
class SmartLightingActuator(Actuator):
    def __init__(self, room_id: str, device_id: str = None, manufacturer: str = "SmartCafe-Inc"):
        if not device_id:
            device_id = f"lighting-{room_id}-001"
            
        super().__init__(device_id, device_type="it.unimore.cafe.actuator.lighting", manufacturer=manufacturer)
        self.room_id = room_id

    @property
    def topic(self) -> str:
        return f"cafe/{self.room_id}/lighting/cmd"
