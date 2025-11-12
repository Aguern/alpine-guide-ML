"""
Service de gestion des sessions utilisateur pour maintenir l'état de l'entonnoir
"""
from typing import Dict, Optional
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class SessionManager:
    """Gestionnaire de sessions pour l'orchestrateur"""
    
    def __init__(self):
        # En production: utiliser Redis ou base de données dédiée
        # Pour MVP: cache en mémoire avec expiration
        self._sessions = {}
        self._session_expiry = {}
        self._session_timeout_hours = 24
    
    async def get_session_context(self, user_id: str, territory_slug: str) -> Dict:
        """Récupère le contexte de session pour un utilisateur"""
        session_key = f"{user_id}_{territory_slug}"
        
        # Vérifier expiration
        if session_key in self._session_expiry:
            if datetime.now() > self._session_expiry[session_key]:
                # Session expirée
                await self._cleanup_expired_session(session_key)
                return {}
        
        session_data = self._sessions.get(session_key, {})
        
        if session_data:
            logger.info(f"Session récupérée pour {user_id}: {list(session_data.keys())}")
        
        return session_data
    
    async def save_session_context(self, user_id: str, territory_slug: str, context: Dict):
        """Sauvegarde le contexte de session"""
        session_key = f"{user_id}_{territory_slug}"
        
        # Nettoyer les données sensibles avant sauvegarde
        clean_context = self._clean_context_for_storage(context)
        
        self._sessions[session_key] = clean_context
        self._session_expiry[session_key] = datetime.now() + timedelta(hours=self._session_timeout_hours)
        
        logger.info(f"Session sauvegardée pour {user_id}: {list(clean_context.keys())}")
    
    async def clear_session(self, user_id: str, territory_slug: str):
        """Efface la session utilisateur"""
        session_key = f"{user_id}_{territory_slug}"
        await self._cleanup_expired_session(session_key)
        logger.info(f"Session effacée pour {user_id}")
    
    async def update_funnel_state(self, user_id: str, territory_slug: str, funnel_data: Dict):
        """Met à jour spécifiquement l'état de l'entonnoir (legacy + DialogueFunnelEngine)"""
        session_context = await self.get_session_context(user_id, territory_slug)
        
        # Support legacy funnel_profile
        if "funnel_profile" not in session_context:
            session_context["funnel_profile"] = {}
        
        # Fusionner intelligemment les données legacy
        if funnel_data.get("profile"):
            session_context["funnel_profile"] = funnel_data["profile"]
        
        # Support nouveau DialogueFunnelEngine (M2)
        if "funnel_state" in funnel_data:
            session_context["funnel_state"] = funnel_data["funnel_state"]
        
        # Ajouter métadonnées de session
        session_context["last_funnel_update"] = datetime.now().isoformat()
        session_context["funnel_active"] = not funnel_data.get("completed", False)
        
        await self.save_session_context(user_id, territory_slug, session_context)
    
    async def update_dialogue_funnel_state(self, user_id: str, territory_slug: str, funnel_state: Dict):
        """Met à jour spécifiquement l'état DialogueFunnelEngine (M2)"""
        session_context = await self.get_session_context(user_id, territory_slug)
        
        # Sauvegarder l'état du nouveau moteur
        session_context["funnel_state"] = funnel_state
        session_context["last_funnel_update"] = datetime.now().isoformat()
        session_context["funnel_active"] = funnel_state.get("current_step") is not None
        
        await self.save_session_context(user_id, territory_slug, session_context)
        logger.info(f"État DialogueFunnelEngine sauvegardé pour {user_id}: étape {funnel_state.get('current_step')}")
    
    def _clean_context_for_storage(self, context: Dict) -> Dict:
        """Nettoie le contexte avant stockage avec protection vacation planning"""
        clean_context = {}
        
        # Garder seulement les données essentielles
        allowed_keys = [
            "funnel_profile",  # Legacy funnel state
            "funnel_state",    # Nouveau DialogueFunnelEngine state
            "last_funnel_update", 
            "funnel_active",
            "planning_active",
            "vacation_planning_state",  # Mode 3: État vacation planning
            "vacation_planning_active",  # Mode 3: Flag vacation planning actif
            "last_activity",
            "user_preferences",
            "is_local_user"
        ]
        
        for key in allowed_keys:
            if key in context:
                try:
                    # Protection spéciale pour vacation_planning_state
                    if key == "vacation_planning_state" and context[key] is not None:
                        # Vérifier que l'état vacation planning est valide
                        vacation_state = context[key]
                        if isinstance(vacation_state, dict):
                            # Validation minimale
                            required_fields = ["user_id", "territory_slug"]
                            if all(field in vacation_state for field in required_fields):
                                clean_context[key] = vacation_state
                                logger.info(f"✅ Vacation planning state sauvegardé: current_step={vacation_state.get('current_step')}")
                            else:
                                logger.warning(f"⚠️ Vacation planning state invalide - champs manquants: {required_fields}")
                                clean_context[key] = None
                        else:
                            # État non-dict, probablement corrompu
                            logger.warning(f"⚠️ Vacation planning state non-dict: {type(vacation_state)}")
                            clean_context[key] = None
                    else:
                        # Autres clés - copie directe
                        clean_context[key] = context[key]
                        
                except Exception as e:
                    logger.error(f"❌ Erreur nettoyage clé '{key}': {e}")
                    # Ne pas inclure la clé si erreur
                    continue
        
        # Ajouter timestamp pour debugging
        clean_context["_last_cleaned"] = datetime.now().isoformat()
        
        return clean_context
    
    async def _cleanup_expired_session(self, session_key: str):
        """Nettoie une session expirée"""
        if session_key in self._sessions:
            del self._sessions[session_key]
        if session_key in self._session_expiry:
            del self._session_expiry[session_key]
    
    async def cleanup_expired_sessions(self):
        """Nettoie toutes les sessions expirées (à appeler périodiquement)"""
        now = datetime.now()
        expired_keys = [
            key for key, expiry in self._session_expiry.items() 
            if now > expiry
        ]
        
        for key in expired_keys:
            await self._cleanup_expired_session(key)
        
        if expired_keys:
            logger.info(f"Nettoyé {len(expired_keys)} sessions expirées")


# Instance singleton
session_manager = SessionManager()