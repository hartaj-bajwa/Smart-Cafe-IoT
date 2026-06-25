"""
resources/cafe_resources.py

Risorse REST di Flask configurate per gestire il DataManager e accedere allo stato
tramite l'oggetto dict.
"""

from flask import request
from flask_restful import Resource
import logging
from dto.cafe_dtos import RoomStatusDTO

logger = logging.getLogger("resources")

class StatusResource(Resource): #risora REST, espone stato stanze tramite GET
    def __init__(self, **kwargs): #**kwargs=qualsiasi numero di argomenti posizionali o keyword, in questo caso riceve il data_manager
        self.data_manager = kwargs['data_manager']

    def get(self, room_id=None):
        if room_id:
            with self.data_manager._lock:
                state = self.data_manager.states.get(room_id)
            return RoomStatusDTO.from_state(state) if state else ({"error": "Room not found"}, 404)
        
        with self.data_manager._lock:
            states_dict = {rid: RoomStatusDTO.from_state(s) for rid, s in self.data_manager.states.items()}
        return states_dict, 200

class ConfigResource(Resource):
    def __init__(self, **kwargs):
        self.data_manager = kwargs['data_manager']

    def put(self, room_id):
        try:
            json_data = request.get_json(force=True, silent=False)
            if not json_data or 'k' not in json_data:
                return {"error": "Missing 'k' field in payload"}, 400
                
            new_k = float(json_data['k'])
            
            with self.data_manager._lock:
                if room_id in self.data_manager.states:
                    if 0.05 <= new_k <= 0.5:
                        self.data_manager.states[room_id].k = new_k #Aggiorna il parametro k
                        self.data_manager._recompute_brightness(room_id) #Ricalcola la luminosita' con il nuovo K
                        logger.info(f"Parametro k aggiornato per la stanza {room_id} -> k={new_k:.3f}")
                        return {"message": f"K updated for {room_id}"}, 200 
                    else:
                        return {"error": "Invalid K value. Range must be 0.05 - 0.5"}, 400
                else:
                    return {"error": "Room not found"}, 404
                    
        except (TypeError, ValueError) as ve:
            return {"error": f"Valore di k non valido: {ve}"}, 400
        except Exception as e:
            logger.error("Errore imprevisto durante l'aggiornamento di k: %s", e)
            return {"error": "Internal Server Error"}, 500
