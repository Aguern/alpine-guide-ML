"""
Cache Manager pour Alpine Guide Widget
Réduit drastiquement les appels à Gemini et améliore les performances
"""
import redis
import json
import hashlib
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CacheManager:
    """
    Gestionnaire de cache intelligent pour Alpine Guide
    Objectif : Servir 80% des requêtes depuis le cache
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        """Initialise la connexion Redis"""
        try:
            self.redis = redis.from_url(redis_url, decode_responses=True)
            self.redis.ping()
            logger.info("✅ Cache Redis connecté")
        except Exception as e:
            logger.warning(f"⚠️ Redis non disponible, utilisation cache mémoire: {e}")
            self.redis = None
            self._memory_cache = {}
        
        # TTL par type de requête (en secondes)
        self.ttl_config = {
            "restaurant": 86400,      # 24h - restaurants changent peu
            "randonnee": 604800,      # 7 jours - sentiers stables
            "meteo": 3600,            # 1h - météo change souvent
            "activite_sportive": 43200,  # 12h - activités assez stables
            "ski": 21600,             # 6h - conditions ski variables
            "general_chat": 300,      # 5min - conversations générales
            "intent_detection": 86400, # 24h - détection d'intent stable
            "slot_extraction": 3600,   # 1h - extraction slots variable
            "rag_results": 3600,      # 1h - résultats RAG
            "weather_data": 1800,     # 30min - données météo
            "default": 1800           # 30min par défaut
        }
    
    def _generate_cache_key(self, prefix: str, data: Dict[str, Any]) -> str:
        """Génère une clé de cache unique"""
        # Trier les clés pour avoir une clé stable
        sorted_data = json.dumps(data, sort_keys=True, ensure_ascii=False)
        hash_key = hashlib.md5(sorted_data.encode()).hexdigest()[:12]
        return f"alpine:{prefix}:{hash_key}"
    
    def get(self, key: str) -> Optional[Any]:
        """Récupère une valeur du cache"""
        try:
            if self.redis:
                value = self.redis.get(key)
                if value:
                    return json.loads(value)
            else:
                # Cache mémoire fallback
                if key in self._memory_cache:
                    data, expiry = self._memory_cache[key]
                    if datetime.now() < expiry:
                        return data
                    else:
                        del self._memory_cache[key]
            return None
        except Exception as e:
            logger.error(f"Erreur lecture cache {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Stocke une valeur dans le cache"""
        try:
            if ttl is None:
                ttl = self.ttl_config["default"]
            
            json_value = json.dumps(value, ensure_ascii=False)
            
            if self.redis:
                return self.redis.setex(key, ttl, json_value)
            else:
                # Cache mémoire fallback
                expiry = datetime.now() + timedelta(seconds=ttl)
                self._memory_cache[key] = (value, expiry)
                return True
        except Exception as e:
            logger.error(f"Erreur écriture cache {key}: {e}")
            return False
    
    def cache_intent_detection(self, message: str, territory: str = "default") -> Optional[str]:
        """Cache pour détection d'intent"""
        cache_key = self._generate_cache_key("intent", {
            "message": message.lower().strip(),
            "territory": territory
        })
        return self.get(cache_key)
    
    def store_intent_detection(self, message: str, intent: str, territory: str = "default") -> bool:
        """Stocke le résultat de détection d'intent"""
        cache_key = self._generate_cache_key("intent", {
            "message": message.lower().strip(),
            "territory": territory
        })
        return self.set(cache_key, intent, self.ttl_config["intent_detection"])
    
    def cache_slot_extraction(self, message: str, intent: str, history: list = None) -> Optional[Dict]:
        """Cache pour extraction de slots"""
        cache_key = self._generate_cache_key("slots", {
            "message": message.lower().strip(),
            "intent": intent,
            "history": history[-2:] if history else []  # Seulement les 2 derniers messages
        })
        return self.get(cache_key)
    
    def store_slot_extraction(self, message: str, intent: str, slots: Dict, history: list = None) -> bool:
        """Stocke le résultat d'extraction de slots"""
        cache_key = self._generate_cache_key("slots", {
            "message": message.lower().strip(),
            "intent": intent,
            "history": history[-2:] if history else []
        })
        return self.set(cache_key, slots, self.ttl_config["slot_extraction"])
    
    def cache_final_response(self, intent: str, filled_slots: Dict, territory: str = "default") -> Optional[str]:
        """Cache pour réponse finale"""
        # Exclure les slots temporels du cache (date, heure)
        cache_slots = {k: v for k, v in filled_slots.items() 
                      if k not in ['date', 'heure', 'date_heure']}
        
        cache_key = self._generate_cache_key("response", {
            "intent": intent,
            "slots": cache_slots,
            "territory": territory
        })
        return self.get(cache_key)
    
    def store_final_response(self, intent: str, filled_slots: Dict, response: str, territory: str = "default") -> bool:
        """Stocke la réponse finale"""
        cache_slots = {k: v for k, v in filled_slots.items() 
                      if k not in ['date', 'heure', 'date_heure']}
        
        cache_key = self._generate_cache_key("response", {
            "intent": intent,
            "slots": cache_slots,
            "territory": territory
        })
        
        ttl = self.ttl_config.get(intent, self.ttl_config["default"])
        return self.set(cache_key, response, ttl)
    
    def cache_rag_results(self, query: str, territory: str = "default") -> Optional[list]:
        """Cache pour résultats RAG"""
        cache_key = self._generate_cache_key("rag", {
            "query": query.lower().strip(),
            "territory": territory
        })
        return self.get(cache_key)
    
    def store_rag_results(self, query: str, results: list, territory: str = "default") -> bool:
        """Stocke les résultats RAG"""
        cache_key = self._generate_cache_key("rag", {
            "query": query.lower().strip(),
            "territory": territory
        })
        return self.set(cache_key, results, self.ttl_config["rag_results"])
    
    def cache_weather_data(self, location: str, date: str = "today") -> Optional[Dict]:
        """Cache pour données météo"""
        cache_key = self._generate_cache_key("weather", {
            "location": location.lower().strip(),
            "date": date
        })
        return self.get(cache_key)
    
    def store_weather_data(self, location: str, weather_data: Dict, date: str = "today") -> bool:
        """Stocke les données météo"""
        cache_key = self._generate_cache_key("weather", {
            "location": location.lower().strip(),
            "date": date
        })
        return self.set(cache_key, weather_data, self.ttl_config["weather_data"])
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du cache"""
        try:
            if self.redis:
                info = self.redis.info()
                return {
                    "connected_clients": info.get('connected_clients', 0),
                    "used_memory": info.get('used_memory_human', '0B'),
                    "keyspace_hits": info.get('keyspace_hits', 0),
                    "keyspace_misses": info.get('keyspace_misses', 0),
                    "total_keys": self.redis.dbsize()
                }
            else:
                return {
                    "memory_cache_size": len(self._memory_cache),
                    "type": "memory_fallback"
                }
        except Exception as e:
            logger.error(f"Erreur stats cache: {e}")
            return {"error": str(e)}
    
    def clear_cache(self, pattern: str = "alpine:*") -> int:
        """Vide le cache selon un pattern"""
        try:
            if self.redis:
                keys = self.redis.keys(pattern)
                if keys:
                    return self.redis.delete(*keys)
                return 0
            else:
                keys_to_delete = [k for k in self._memory_cache.keys() if k.startswith("alpine:")]
                for key in keys_to_delete:
                    del self._memory_cache[key]
                return len(keys_to_delete)
        except Exception as e:
            logger.error(f"Erreur suppression cache: {e}")
            return 0
    
    def health_check(self) -> Dict[str, Any]:
        """Vérifie la santé du cache"""
        try:
            if self.redis:
                self.redis.ping()
                return {"status": "healthy", "type": "redis"}
            else:
                return {"status": "healthy", "type": "memory", "size": len(self._memory_cache)}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}