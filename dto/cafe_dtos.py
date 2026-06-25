import time
from model.models import CafeRoomState

class RoomStatusDTO:
    """
    Data Transfer Object per esporre lo stato della stanza in formato JSON (REST).
    Si occupa di derivare dati complessi (come lo stato online dell'attuatore) 
    senza appesantire il modello di dominio.
    """
    @staticmethod #metodo statico, no istanza necessaria
    def from_state(state: CafeRoomState) -> dict:
        current_time = time.time()
        
        # Logica Health Check: online se l'ultimo heartbeat è stato ricevuto entro gli ultimi 15 secondi
        is_online = False
        if state.last_seen_actuator > 0 and (current_time - state.last_seen_actuator) <= 15.0:
            is_online = True

        return {
            "room_id": state.room_id,
            "current_people": state.current_people,
            "current_brightness": state.current_brightness,
            "k": state.k,
            "actuator_online": is_online,
            "last_update": int(current_time)
        }
