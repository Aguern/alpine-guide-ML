"""
Endpoint de chat optimisé pour Alpine Guide Widget
Point d'entrée unique avec cache intelligent et performances optimisées
"""
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import logging
import asyncio
import os
from datetime import datetime
import sys
import uvicorn
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

# Ajouter le chemin vers les modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.orchestrator import YAMLOrchestrator, ConversationState
from core.cache_manager import CacheManager
from collectors.weather import WeatherCollector
from collectors.water_temperature import WaterTemperatureCollector
from services.supabase_service import SupabaseService

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Modèles Pydantic
class ChatMessage(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    session_id: str = Field(..., min_length=1, max_length=100)
    territory: str = Field(default="annecy", max_length=50)
    language: str = Field(default="fr", max_length=5)

class ChatResponse(BaseModel):
    type: str  # "response", "clarification", "error"
    message: str
    complete: bool
    intent: Optional[str] = None
    slots: Optional[Dict[str, Any]] = None
    missing_slots: Optional[List[str]] = None
    suggestions: Optional[List[str]] = None
    cached: bool = False
    response_time_ms: Optional[int] = None

class HealthResponse(BaseModel):
    status: str
    services: Dict[str, Any]
    cache_stats: Dict[str, Any]
    timestamp: str

# Application FastAPI
app = FastAPI(
    title="Alpine Guide Widget API",
    description="API optimisée pour le widget Alpine Guide",
    version="1.0.0"
)

# CORS pour intégration widget
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # À restreindre en production
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Services globaux
cache_manager: Optional[CacheManager] = None
orchestrator: Optional[YAMLOrchestrator] = None
weather_service: Optional[WeatherCollector] = None
conversation_states: Dict[str, ConversationState] = {}

# Configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
MISTRAL_API_KEY = os.getenv('MISTRAL_API_KEY')
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
INTENTS_YAML_PATH = os.path.join(os.path.dirname(__file__), '..', 'core', 'intents_slots.yaml')

# Clés API par territoire
TERRITORY_API_KEYS = {
    'annecy': os.getenv('WIDGET_API_KEY_ANNECY'),
    'chamonix': os.getenv('WIDGET_API_KEY_CHAMONIX'),
    'chambery': os.getenv('WIDGET_API_KEY_CHAMBERY')
}

@app.on_event("startup")
async def startup_event():
    """Initialisation des services au démarrage"""
    global cache_manager, orchestrator, weather_service
    
    logger.info("🚀 Démarrage Alpine Guide Widget API [VERSION AVEC LIENS CARTES]...")
    
    # Initialiser le cache
    cache_manager = CacheManager(REDIS_URL)
    logger.info("✅ Cache manager initialisé")
    
    # Service météo (instancié APRÈS load_dotenv)
    weather_service = WeatherCollector()
    
    # Initialiser l'orchestrateur
    if not GEMINI_API_KEY:
        logger.error("❌ GEMINI_API_KEY manquante")
        raise ValueError("GEMINI_API_KEY required")
    
    # Service température de l'eau avec chemin de configuration
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'territories')
    water_temp_service = WaterTemperatureCollector(config_path=config_path)
    
    # Service RAG simple (peut être étendu)
    class SimpleRAGService:
        async def search(self, query: str, limit: int = 5) -> List[Dict]:
            # Ici, on pourrait intégrer les collecteurs de données
            # Pour l'instant, on retourne une liste vide
            return []
    
    rag_service = SimpleRAGService()
    
    # Initialiser le service Supabase pour les données réelles
    supabase_service = None
    try:
        supabase_service = SupabaseService()
        logger.info("✅ Service Supabase initialisé")
    except Exception as e:
        logger.warning(f"⚠️ Service Supabase non disponible: {e}")
        logger.info("🔄 Fonctionnement en mode fallback sans données réelles")
    
    orchestrator = YAMLOrchestrator(
        yaml_path=INTENTS_YAML_PATH,
        gemini_api_key=GEMINI_API_KEY,
        mistral_api_key=MISTRAL_API_KEY,
        rag_service=rag_service,
        weather_service=weather_service,
        supabase_service=supabase_service,
        water_temperature_service=water_temp_service
    )
    
    logger.info("🎯 Orchestrateur IA initialisé")
    logger.info("✅ Alpine Guide Widget API prête !")

def get_cache_manager() -> CacheManager:
    """Dependency injection pour le cache"""
    if cache_manager is None:
        raise HTTPException(status_code=503, detail="Cache non disponible")
    return cache_manager

def get_orchestrator() -> YAMLOrchestrator:
    """Dependency injection pour l'orchestrateur"""
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="Orchestrateur non disponible")
    return orchestrator

def validate_territory_api_key(api_key: str, territory: str) -> bool:
    """Valide la clé API pour un territoire donné"""
    expected_key = TERRITORY_API_KEYS.get(territory)
    if not expected_key:
        return False
    return api_key == expected_key

def get_api_key_from_request(request: Request) -> Optional[str]:
    """Extrait la clé API depuis les headers ou query params"""
    # Vérifier dans les headers
    api_key = request.headers.get("X-API-Key") or request.headers.get("Authorization")
    if api_key and api_key.startswith("Bearer "):
        api_key = api_key[7:]  # Supprimer "Bearer "
    
    # Vérifier dans les query params si pas trouvé
    if not api_key:
        api_key = request.query_params.get("api_key")
    
    return api_key

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    chat_message: ChatMessage,
    request: Request,
    cache: CacheManager = Depends(get_cache_manager),
    orch: YAMLOrchestrator = Depends(get_orchestrator)
):
    """
    Endpoint principal de chat avec cache intelligent et validation API key
    """
    start_time = datetime.now()
    cached = False
    
    try:
        # Validation de la clé API
        api_key = get_api_key_from_request(request)
        if not api_key:
            raise HTTPException(status_code=401, detail="Clé API manquante")
        
        if not validate_territory_api_key(api_key, chat_message.territory):
            raise HTTPException(status_code=403, detail="Clé API invalide pour ce territoire")
        
        logger.info(f"Requête chat validée pour territoire: {chat_message.territory}")
        
        # Vérifier le cache pour éviter les appels Gemini
        cached_response = cache.cache_final_response(
            intent="unknown",  # On ne connaît pas encore l'intent
            filled_slots={},
            territory=chat_message.territory
        )
        
        # Récupérer l'état de conversation
        state = conversation_states.get(chat_message.session_id)
        
        # Ajouter le territoire au contexte de l'état (toujours)
        if state:
            if not hasattr(state, 'context'):
                state.context = {}
            state.context['territory'] = chat_message.territory
        else:
            # Créer un état temporaire avec le territoire
            from core.orchestrator import ConversationState
            state = ConversationState(
                session_id=chat_message.session_id,
                context={'territory': chat_message.territory}
            )
        
        # Traitement principal
        result = await orch.process_message(
            message=chat_message.message,
            session_id=chat_message.session_id,
            state=state
        )
        
        # Mettre à jour l'état
        conversation_states[chat_message.session_id] = result["state"]
        
        # Calculer le temps de réponse
        response_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # Mettre en cache si approprié
        if result["complete"] and result.get("intent"):
            cache.store_final_response(
                intent=result["intent"],
                filled_slots=result.get("slots", {}),
                response=result["message"],
                territory=chat_message.territory
            )
        
        # Suggestions contextuelles
        suggestions = await _generate_suggestions(result, chat_message.territory)
        
        return ChatResponse(
            type=result["type"],
            message=result["message"],
            complete=result["complete"],
            intent=result.get("intent"),
            slots=result.get("slots"),
            missing_slots=result.get("missing_slots"),
            suggestions=suggestions,
            cached=cached,
            response_time_ms=response_time
        )
        
    except Exception as e:
        logger.error(f"Erreur endpoint chat: {e}")
        response_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        return ChatResponse(
            type="error",
            message="Désolé, je rencontre un problème technique. Pouvez-vous reformuler votre demande ?",
            complete=False,
            response_time_ms=response_time
        )

@app.get("/health", response_model=HealthResponse)
async def health_check(
    cache: CacheManager = Depends(get_cache_manager)
):
    """
    Endpoint de santé pour monitoring
    """
    services = {
        "orchestrator": {"status": "healthy" if orchestrator else "down"},
        "cache": cache.health_check(),
        "weather": weather_service.health_check() if weather_service else {"status": "down"}
    }
    
    cache_stats = cache.get_cache_stats()
    
    # Statut global
    overall_status = "healthy"
    if not orchestrator:
        overall_status = "degraded"
    
    return HealthResponse(
        status=overall_status,
        services=services,
        cache_stats=cache_stats,
        timestamp=datetime.now().isoformat()
    )

@app.get("/cache/stats")
async def cache_stats(cache: CacheManager = Depends(get_cache_manager)):
    """Statistiques détaillées du cache"""
    return cache.get_cache_stats()

@app.delete("/cache/clear")
async def clear_cache(
    cache: CacheManager = Depends(get_cache_manager),
    pattern: str = "alpine:*"
):
    """Vider le cache (admin)"""
    cleared = cache.clear_cache(pattern)
    return {"cleared_keys": cleared, "pattern": pattern}

@app.get("/territories/{territory}/config")
async def get_territory_config(territory: str):
    """Configuration d'un territoire pour le widget"""
    # Configuration par défaut - peut être étendue avec base de données
    configs = {
        "annecy": {
            "name": "Annecy - Lac et Montagnes",
            "center": {"lat": 45.8992, "lng": 6.1294},
            "zoom": 11,
            "primaryColor": "#0066CC",
            "features": ["chat", "weather", "activities"]
        },
        "chamonix": {
            "name": "Chamonix Mont-Blanc",
            "center": {"lat": 45.9237, "lng": 6.8694},
            "zoom": 12,
            "primaryColor": "#FF6B35",
            "features": ["chat", "weather", "skiing"]
        }
    }
    
    config = configs.get(territory)
    if not config:
        raise HTTPException(status_code=404, detail="Territoire non trouvé")
    
    return config

async def _generate_suggestions(result: Dict, territory: str) -> List[str]:
    """Génère des suggestions contextuelles"""
    if not result.get("complete") or not result.get("intent"):
        return []
    
    intent = result["intent"]
    suggestions_map = {
        "meteo": [
            "Météo pour demain ?",
            "Prévisions sur 3 jours",
            "Conditions de ski"
        ],
        "restaurant": [
            "Restaurants avec terrasse",
            "Spécialités locales",
            "Restaurants familiaux"
        ],
        "randonnee": [
            "Randonnées faciles",
            "Balades en famille",
            "Sentiers avec vue lac"
        ]
    }
    
    return suggestions_map.get(intent, [])

# Middleware pour logging des requêtes
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now()
    
    # Traiter la requête
    response = await call_next(request)
    
    # Logger les performances
    process_time = (datetime.now() - start_time).total_seconds()
    
    logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time:.3f}s"
    )
    
    return response

if __name__ == "__main__":
    # Démarrage en mode développement
    uvicorn.run(
        "chat_endpoint:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )