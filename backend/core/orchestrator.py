"""
Orchestrateur IA avec chargement dynamique des intents/slots depuis YAML
Intégration avec Gemini 2.0 Flash pour la détection d'intents
"""
import yaml
import os
from typing import Dict, Optional, List, Tuple, Any
from dataclasses import dataclass, field
from pathlib import Path
import google.generativeai as genai
import json
import logging
import requests
from datetime import datetime, timedelta

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Slot:
    """Représentation d'un slot"""
    name: str
    type: str
    required: bool = True
    description: str = ""
    examples: List[str] = field(default_factory=list)
    value: Optional[Any] = None

@dataclass
class Intent:
    """Représentation d'un intent"""
    name: str
    description: str
    slots: Dict[str, Slot]
    examples: List[str] = field(default_factory=list)
    response_template: str = ""

@dataclass
class ConversationState:
    """État de la conversation"""
    intent: Optional[Intent] = None
    filled_slots: Dict[str, Any] = field(default_factory=dict)
    context: Dict = field(default_factory=dict)
    history: List[Dict] = field(default_factory=list)
    session_id: str = ""

class YAMLOrchestrator:
    """Orchestrateur principal avec chargement YAML dynamique"""
    
    def __init__(self, yaml_path: str, gemini_api_key: str, mistral_api_key: str = None, rag_service=None, weather_service=None, supabase_service=None, water_temperature_service=None):
        """
        Initialise l'orchestrateur
        
        Args:
            yaml_path: Chemin vers le fichier intents_slots.yaml
            gemini_api_key: Clé API Gemini
            rag_service: Service RAG pour POIs
            weather_service: Service météo
            supabase_service: Service Supabase pour données réelles
            water_temperature_service: Service température de l'eau
        """
        self.intents = self._load_intents_from_yaml(yaml_path)
        self.rag_service = rag_service
        self.weather_service = weather_service
        self.supabase_service = supabase_service
        self.water_temperature_service = water_temperature_service
        
        # Configurer Gemini
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Configurer Mistral comme fallback
        self.mistral_api_key = mistral_api_key
        
        logger.info(f"Orchestrateur initialisé avec {len(self.intents)} intents")
        
        # Classification des intents pour réponses intelligentes
        self.physical_location_intents = {'restaurant', 'hebergement', 'shopping', 'musee', 'office_tourisme'}
        self.event_intents = {'evenement', 'visite_guidee'}
        self.activity_intents = {'randonnee', 'activite_sportive', 'ski', 'baignade'}
        self.info_intents = {'meteo', 'water_temperature', 'transport_public', 'urgence', 'wifi_gratuit'}
        
        # Vérifier la connexion Supabase si disponible
        if self.supabase_service:
            try:
                health = self.supabase_service.health_check()
                if health.get('status') == 'healthy':
                    logger.info(f"✅ Supabase connecté: {health.get('pois_count', 0)} POIs disponibles")
                else:
                    logger.warning(f"⚠️ Supabase en erreur: {health.get('message')}")
            except Exception as e:
                logger.error(f"❌ Erreur vérification Supabase: {e}")
    
    def _load_intents_from_yaml(self, yaml_path: str) -> Dict[str, Intent]:
        """Charge les intents et slots depuis le fichier YAML au format existant"""
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            intents = {}
            
            # Le format existant a 'intents' comme dict avec les clés d'intent
            intents_data = data.get('intents', {})
            
            for intent_name, intent_config in intents_data.items():
                # Ignorer les commentaires YAML (qui deviennent des strings ou None)
                if isinstance(intent_config, str) or intent_config is None:
                    continue
                    
                slots = {}
                
                # Charger les slots obligatoires et optionnels
                slots_obligatoires = intent_config.get('slots_obligatoires', [])
                slots_optionnels = intent_config.get('slots_optionnels', [])
                
                # Créer les slots obligatoires
                for slot_name in slots_obligatoires:
                    slot = Slot(
                        name=slot_name,
                        type='text',
                        required=True,
                        description=f"Slot obligatoire {slot_name}",
                        examples=[]
                    )
                    slots[slot_name] = slot
                
                # Créer les slots optionnels
                for slot_name in slots_optionnels:
                    slot = Slot(
                        name=slot_name,
                        type='text',
                        required=False,
                        description=f"Slot optionnel {slot_name}",
                        examples=[]
                    )
                    slots[slot_name] = slot
                
                # Créer l'intent
                intent = Intent(
                    name=intent_name,
                    description=intent_config.get('description', ''),
                    slots=slots,
                    examples=[],  # Pas d'exemples dans le format actuel
                    response_template=f"Réponse pour {intent_name}"
                )
                
                intents[intent_name] = intent
            
            # Ajouter un intent général par défaut s'il n'existe pas
            if 'general_chat' not in intents:
                general_intent = Intent(
                    name='general_chat',
                    description='Conversation générale et accueil',
                    slots={},
                    examples=['bonjour', 'salut', 'merci', 'au revoir'],
                    response_template='Je suis ravi de vous aider à découvrir la région !'
                )
                intents['general_chat'] = general_intent
            
            logger.info(f"Chargé {len(intents)} intents: {list(intents.keys())}")
            return intents
            
        except Exception as e:
            logger.error(f"Erreur lors du chargement du YAML: {e}")
            raise
    
    async def detect_intent(self, message: str, context: Dict = None) -> Optional[Intent]:
        """
        Détecte l'intent d'un message utilisateur via Gemini
        
        Args:
            message: Message utilisateur
            context: Contexte de conversation
            
        Returns:
            Intent détecté ou None
        """
        # Préparer le prompt pour Gemini
        intent_list = [
            {
                "name": intent.name,
                "description": intent.description,
                "examples": intent.examples
            }
            for intent in self.intents.values()
        ]
        
        prompt = f"""Tu es un assistant de détection d'intentions pour un chatbot touristique.
        
Message utilisateur : "{message}"

Intents disponibles :
{json.dumps(intent_list, ensure_ascii=False, indent=2)}

Analyse le message et retourne UNIQUEMENT le nom de l'intent qui correspond le mieux.
Si aucun intent ne correspond vraiment, retourne "general_chat".

Réponse (nom de l'intent seulement) :"""

        try:
            response = self.model.generate_content(prompt)
            intent_name = response.text.strip().lower()
            
            # Vérifier si l'intent existe
            if intent_name in self.intents:
                logger.info(f"Intent détecté: {intent_name}")
                return self.intents[intent_name]
            else:
                logger.warning(f"Intent inconnu: {intent_name}, utilisation de general_chat")
                return self.intents.get('general_chat')
                
        except Exception as e:
            logger.error(f"Erreur détection intent: {e}")
            # Fallback avec Mistral si disponible
            if self.mistral_api_key:
                try:
                    logger.info("🔄 Fallback vers Mistral pour détection intent")
                    response = self.call_mistral(prompt)
                    intent_name = response.strip().lower()
                    
                    if intent_name in self.intents:
                        logger.info(f"Intent détecté via Mistral: {intent_name}")
                        return self.intents[intent_name]
                    else:
                        logger.warning(f"Intent Mistral inconnu: {intent_name}")
                        return self.intents.get('general_chat')
                        
                except Exception as mistral_error:
                    logger.error(f"Erreur Mistral fallback: {mistral_error}")
                    
            return self.intents.get('general_chat')
    
    async def extract_slots(self, message: str, intent: Intent, state: ConversationState) -> Dict[str, Any]:
        """
        Extrait les valeurs des slots depuis le message via Gemini
        
        Args:
            message: Message utilisateur
            intent: Intent détecté
            state: État de la conversation
            
        Returns:
            Dictionnaire des slots extraits
        """
        if not intent.slots:
            return {}
        
        # Préparer les slots pour l'extraction
        slots_info = []
        for slot_name, slot in intent.slots.items():
            slots_info.append({
                "name": slot_name,
                "type": slot.type,
                "description": slot.description,
                "examples": slot.examples,
                "required": slot.required
            })
        
        # Inclure l'historique pour le contexte
        history_text = ""
        if state.history:
            history_text = "\n".join([
                f"{msg['role']}: {msg['content']}" 
                for msg in state.history[-3:]  # Derniers 3 messages
            ])
        
        # Inclure le contexte territorial si disponible
        territory_context = ""
        if hasattr(state, 'context') and state.context.get('territory'):
            territory_context = f"\nTerritoire actuel: {state.context['territory']}"
        
        prompt = f"""Tu es un assistant d'extraction d'informations pour un chatbot touristique.

Historique récent:
{history_text}{territory_context}

Message actuel: "{message}"

Intent détecté: {intent.name}

Slots à extraire:
{json.dumps(slots_info, ensure_ascii=False, indent=2)}

Extrait les valeurs des slots depuis le message et l'historique.
Retourne UNIQUEMENT un objet JSON valide avec les slots trouvés.
Ne pas inventer de valeurs, seulement extraire ce qui est explicitement mentionné.

Réponse JSON:"""

        try:
            response = self.model.generate_content(prompt)
            # Nettoyer la réponse pour obtenir seulement le JSON
            json_text = response.text.strip()
            if "```json" in json_text:
                json_text = json_text.split("```json")[1].split("```")[0]
            elif "```" in json_text:
                json_text = json_text.split("```")[1].split("```")[0]
            
            extracted = json.loads(json_text)
            logger.info(f"Slots extraits: {extracted}")
            return extracted
            
        except Exception as e:
            logger.error(f"Erreur extraction slots: {e}")
            # Fallback avec Mistral si disponible
            if self.mistral_api_key:
                try:
                    logger.info("🔄 Fallback vers Mistral pour extraction slots")
                    response = self.call_mistral(prompt)
                    # Nettoyer la réponse pour obtenir seulement le JSON
                    json_text = response.strip()
                    if "```json" in json_text:
                        json_text = json_text.split("```json")[1].split("```")[0]
                    elif "```" in json_text:
                        json_text = json_text.split("```")[1].split("```")[0]
                    
                    extracted = json.loads(json_text)
                    logger.info(f"Slots extraits via Mistral: {extracted}")
                    return extracted
                    
                except Exception as mistral_error:
                    logger.error(f"Erreur Mistral extraction slots: {mistral_error}")
                    
            # Fallback simple en dernier recours
            return self.simple_slot_extraction(message, intent)
    
    def auto_fill_slots_from_context(self, intent: Intent, filled_slots: Dict[str, Any], state: ConversationState) -> Dict[str, Any]:
        """
        Auto-remplit les slots manquants avec des valeurs par défaut du contexte
        
        Args:
            intent: Intent actuel
            filled_slots: Slots déjà remplis
            state: État de la conversation
            
        Returns:
            Slots mis à jour avec auto-remplissage
        """
        updated_slots = filled_slots.copy()
        
        # Auto-remplir la localisation avec le territoire si manquant
        if ('localisation' in intent.slots and 
            'localisation' not in updated_slots and 
            hasattr(state, 'context') and 
            state.context.get('territory')):
            
            territory_map = {
                'annecy': 'Annecy',
                'chamonix': 'Chamonix',
                'chambery': 'Chambéry'
            }
            territory_name = territory_map.get(state.context['territory'], state.context['territory'])
            updated_slots['localisation'] = territory_name
            logger.info(f"🎯 Auto-remplissage localisation: {territory_name}")
        
        return updated_slots
    
    def call_mistral(self, prompt: str) -> str:
        """
        Appelle l'API Mistral comme fallback
        
        Args:
            prompt: Le prompt à envoyer
            
        Returns:
            Réponse de Mistral
        """
        if not self.mistral_api_key:
            raise Exception("Clé API Mistral non configurée")
            
        headers = {
            "Authorization": f"Bearer {self.mistral_api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "mistral-small-latest",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 1000,
            "temperature": 0.3
        }
        
        try:
            response = requests.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            return result["choices"][0]["message"]["content"].strip()
            
        except Exception as e:
            logger.error(f"Erreur appel Mistral: {e}")
            raise
    
    def simple_slot_extraction(self, message: str, intent: Intent) -> Dict[str, Any]:
        """
        Extraction simple de slots sans IA en cas de fallback
        
        Args:
            message: Message utilisateur
            intent: Intent détecté
            
        Returns:
            Dictionnaire des slots extraits simplement
        """
        slots = {}
        message_lower = message.lower()
        
        # Extraction basique par mots-clés
        if 'date_heure' in intent.slots:
            time_patterns = ['ce soir', 'demain', 'midi', 'soir', '19h', '20h', 'aujourd\'hui']
            for pattern in time_patterns:
                if pattern in message_lower:
                    slots['date_heure'] = pattern
                    break
        
        if 'type_cuisine' in intent.slots:
            cuisine_patterns = {
                'savoyard': 'savoyarde', 'savoyarde': 'savoyarde',
                'italien': 'italienne', 'italienne': 'italienne',
                'chinois': 'chinoise', 'chinoise': 'chinoise',
                'français': 'française', 'française': 'française',
                'local': 'local', 'locale': 'local',
                'traditionnel': 'traditionnel', 'traditionnelle': 'traditionnel',
                'gastronomique': 'gastronomique'
            }
            for pattern, cuisine in cuisine_patterns.items():
                if pattern in message_lower:
                    slots['type_cuisine'] = cuisine
                    break
        
        if 'terrasse' in intent.slots and 'terrasse' in message_lower:
            slots['terrasse'] = 'avec terrasse'
            
        logger.info(f"🔧 Extraction simple: {slots}")
        return slots
    
    def _analyze_intent_context(self, intent: Intent, pois: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyse intelligente du contexte pour adapter la réponse
        
        Args:
            intent: Intent détecté
            pois: Liste des POIs trouvés
            
        Returns:
            Dictionnaire avec les instructions de rendu
        """
        context = {
            'intent_category': 'general',
            'needs_geolocation': False,
            'needs_temporal_validation': False,
            'template_type': 'general'
        }
        
        # Analyser le type d'intent
        if intent.name in self.physical_location_intents:
            context.update({
                'intent_category': 'physical_location',
                'needs_geolocation': True,
                'template_type': 'location_with_maps'
            })
        elif intent.name in self.event_intents:
            context.update({
                'intent_category': 'event',
                'needs_temporal_validation': True,
                'template_type': 'event_without_maps'
            })
        elif intent.name in self.activity_intents:
            context.update({
                'intent_category': 'activity',
                'needs_geolocation': True,  # Peut être utile pour certaines activités
                'template_type': 'activity_selective_maps'
            })
        elif intent.name in self.info_intents:
            context.update({
                'intent_category': 'information',
                'template_type': 'weather_formatted' if intent.name == 'meteo' else 'information_only'
            })
        
        # Analyser les POIs pour affiner le contexte
        if pois:
            poi_analysis = self._analyze_poi_content(pois)
            context.update(poi_analysis)
            
        return context
    
    def _analyze_poi_content(self, pois: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyse le contenu des POIs pour déterminer leur nature
        
        Args:
            pois: Liste des POIs
            
        Returns:
            Analyse du contenu
        """
        analysis = {
            'has_physical_locations': False,
            'has_events': False,
            'has_temporal_issues': [],
            'poi_classifications': []
        }
        
        for poi in pois:
            poi_type = poi.get('type', '').lower()
            name = poi.get('name', '').lower()
            description = poi.get('description', '').lower()
            
            # Classification du POI
            classification = self._classify_single_poi(poi_type, name, description)
            analysis['poi_classifications'].append(classification)
            
            if classification == 'physical_location':
                analysis['has_physical_locations'] = True
            elif classification == 'event':
                analysis['has_events'] = True
                # Vérifier les dates pour les événements
                temporal_issue = self._validate_event_dates(poi)
                if temporal_issue:
                    analysis['has_temporal_issues'].append(temporal_issue)
        
        return analysis
    
    def _classify_single_poi(self, poi_type: str, name: str, description: str) -> str:
        """
        Classifie un POI selon sa nature
        
        Returns:
            'physical_location', 'event', 'activity', ou 'information'
        """
        # Lieux physiques
        physical_keywords = ['restaurant', 'hotel', 'magasin', 'cafe', 'bar', 'musee', 'shop', 'store']
        if (poi_type in ['restaurant', 'hotel', 'shop', 'accommodation', 'store', 'cafe', 'bar', 'museum'] or
            any(keyword in name for keyword in physical_keywords)):
            return 'physical_location'
        
        # Événements
        event_keywords = ['fete', 'festival', 'marche', 'concert', 'spectacle', 'evenement']
        if (poi_type in ['event', 'festival', 'concert'] or
            any(keyword in name for keyword in event_keywords) or
            any(keyword in description for keyword in event_keywords)):
            return 'event'
        
        # Activités
        activity_keywords = ['randonnee', 'trail', 'sentier', 'parcours', 'piste', 'sport']
        if (poi_type in ['activity', 'sport', 'nature', 'outdoor'] or
            any(keyword in name for keyword in activity_keywords)):
            return 'activity'
        
        return 'information'
    
    def _validate_event_dates(self, poi: Dict[str, Any]) -> Optional[str]:
        """
        Valide les dates d'un événement
        
        Returns:
            Message d'alerte ou None
        """
        start_date = poi.get('start_date') or poi.get('date_debut') or poi.get('date')
        if not start_date:
            return None
            
        try:
            event_date = datetime.fromisoformat(str(start_date).replace('Z', '+00:00'))
            now = datetime.now()
            
            # Événement passé depuis plus de 7 jours
            if event_date < now - timedelta(days=7):
                return f"⚠️ L'événement '{poi.get('name')}' semble être passé ({event_date.strftime('%d/%m/%Y')})"
            
            # Événement trop éloigné (plus d'un an)
            elif event_date > now + timedelta(days=365):
                return f"⚠️ L'événement '{poi.get('name')}' semble très éloigné ({event_date.strftime('%d/%m/%Y')})"
                
        except (ValueError, TypeError):
            pass
            
        return None
    
    def _generate_smart_prompt(self, intent: Intent, filled_slots: Dict[str, Any], 
                              pois: List[Dict[str, Any]], context: Dict[str, Any]) -> str:
        """
        Génère un prompt intelligent adapté au contexte
        
        Args:
            intent: Intent détecté
            filled_slots: Slots remplis
            pois: POIs trouvés
            context: Contexte analysé
            
        Returns:
            Prompt optimisé pour l'IA
        """
        base_prompt = f"""Tu es un assistant touristique expert et chaleureux.

Intent: {intent.name} - {intent.description}
Informations utilisateur: {json.dumps(filled_slots, ensure_ascii=False)}

"""
        
        if pois:
            base_prompt += f"""Résultats de recherche (POIs pertinents):
{json.dumps(pois, ensure_ascii=False, indent=2)}

"""
        
        # Ajouter les instructions selon le template
        template_type = context.get('template_type', 'general')
        
        if template_type == 'location_with_maps':
            base_prompt += self._get_location_template_instructions(context)
        elif template_type == 'event_without_maps':
            base_prompt += self._get_event_template_instructions(context)
        elif template_type == 'activity_selective_maps':
            base_prompt += self._get_activity_template_instructions(context)
        elif template_type == 'weather_formatted':
            base_prompt += self._get_weather_template_instructions()
        else:
            base_prompt += self._get_general_template_instructions()
            
        return base_prompt
    
    def _get_location_template_instructions(self, context: Dict[str, Any]) -> str:
        """Instructions pour les lieux physiques (avec liens cartes)"""
        instructions = """
FORMAT DE RÉPONSE - LIEUX PHYSIQUES:

Pour chaque restaurant, hôtel, magasin, musée (lieu physique), utilise cette structure:

<div class="poi-item">
<h3>[Nom du lieu]</h3>
<p>[Description courte - 1-2 phrases]</p>
<div class="poi-links">
<a href="[URL exacte maps_links.google_maps]" target="_blank" class="map-link google">📍 Google Maps</a>
<a href="[URL exacte maps_links.apple_maps]" target="_blank" class="map-link apple">🗺️ Apple Plans</a>
</div>
</div>

RÈGLES:
- TOUJOURS inclure les liens cartographiques pour les lieux physiques
- Utiliser les URLs exactes depuis maps_links.google_maps et maps_links.apple_maps
- Si pas de liens disponibles, écrire "Liens cartographiques à venir"
"""
        
        # Ajouter alertes temporelles si nécessaire
        if context.get('has_temporal_issues'):
            instructions += f"""
⚠️ ALERTES DÉTECTÉES:
{chr(10).join(context['has_temporal_issues'])}
"""
        
        return instructions + "\nRéponse:"
    
    def _get_event_template_instructions(self, context: Dict[str, Any]) -> str:
        """Instructions pour les événements (sans liens cartes)"""
        return """
FORMAT DE RÉPONSE - ÉVÉNEMENTS:

Pour chaque événement, festival, marché, spectacle, utilise cette structure:

<div class="poi-item">
<h3>[Nom de l'événement]</h3>
<p>[Description avec dates, horaires et lieu général]</p>
</div>

RÈGLES:
- NE PAS inclure de liens cartographiques pour les événements
- Mentionner les dates et horaires si disponibles
- Indiquer le lieu général (ex: "Centre-ville d'Annecy")
- Vérifier la cohérence des dates avec la période actuelle

Réponse:"""
    
    def _get_activity_template_instructions(self, context: Dict[str, Any]) -> str:
        """Instructions pour les activités (liens sélectifs)"""
        return """
FORMAT DE RÉPONSE - ACTIVITÉS:

Pour les lieux d'activité précis (bases de loisirs, centres sportifs), utilise la structure avec liens:

<div class="poi-item">
<h3>[Nom du lieu d'activité]</h3>
<p>[Description de l'activité et du lieu]</p>
<div class="poi-links">
<a href="[URL maps_links.google_maps]" target="_blank" class="map-link google">📍 Google Maps</a>
<a href="[URL maps_links.apple_maps]" target="_blank" class="map-link apple">🗺️ Apple Plans</a>
</div>
</div>

Pour les activités générales (randonnées, sports sans lieu précis), utilise la structure sans liens:

<div class="poi-item">
<h3>[Nom de l'activité]</h3>
<p>[Description avec conseils pratiques et conditions]</p>
</div>

RÈGLES:
- Liens cartographiques SEULEMENT pour les lieux d'activité précis
- Pas de liens pour les activités générales ou les sentiers longs

Réponse:"""
    
    def _get_weather_template_instructions(self) -> str:
        """Instructions spécialisées pour la météo avec rendu HTML structuré"""
        return """
FORMAT DE RÉPONSE MÉTÉO:

Tu dois générer une réponse météo structurée en HTML pour un rendu optimal.

Pour la météo ACTUELLE, utilise ce format exact:
<div class="weather-item current-weather">
<div class="weather-header">
<h3>🌤️ Météo actuelle à [VILLE]</h3>
<div class="weather-main">
<span class="temperature">[XX]°C</span>
<span class="description">[Description]</span>
</div>
</div>
<div class="weather-details">
<div class="weather-detail">
<span class="label">Ressenti:</span>
<span class="value">[XX]°C</span>
</div>
<div class="weather-detail">
<span class="label">Humidité:</span>
<span class="value">[XX]%</span>
</div>
<div class="weather-detail">
<span class="label">Vent:</span>
<span class="value">[XX] km/h</span>
</div>
</div>
<div class="weather-times">
<span>☀️ Lever: [HH:MM]</span>
<span>🌅 Coucher: [HH:MM]</span>
</div>
</div>

Pour les PRÉVISIONS, utilise ce format exact:
<div class="weather-item forecast-weather">
<h3>📅 Prévisions météo pour [VILLE]</h3>
<div class="forecast-days">
<div class="forecast-day">
<div class="day-name">[Jour]</div>
<div class="day-temp">[XX]°C / [XX]°C</div>
<div class="day-desc">[Description]</div>
<div class="day-rain">☂️ [XX]%</div>
</div>
[répéter pour chaque jour jusqu'à 5 jours max]
</div>
</div>

RÈGLES ABSOLUES:
- PAS de markdown (**, *, etc.) - uniquement HTML pur
- PAS de balises ```html``` ou ``` - HTML direct seulement
- Utiliser les émojis pour rendre visuellement attractif
- Données exactes depuis les informations météo fournies
- HTML valide et bien structuré
- Classes CSS exactes comme indiquées
- Commencer directement par <div class="weather-item">

Réponse:"""
    
    def _get_general_template_instructions(self) -> str:
        """Instructions générales"""
        return """
FORMAT DE RÉPONSE GÉNÉRAL:

Adapte ta réponse selon le type d'information demandée.
Si tu proposes des lieux physiques spécifiques, inclus les liens cartographiques.
Si ce sont des informations générales, focus sur le contenu informatif.

Réponse:"""
    
    def check_missing_slots(self, intent: Intent, filled_slots: Dict[str, Any]) -> List[Slot]:
        """
        Vérifie quels slots obligatoires sont manquants
        
        Args:
            intent: Intent actuel
            filled_slots: Slots déjà remplis
            
        Returns:
            Liste des slots manquants
        """
        missing = []
        
        for slot_name, slot in intent.slots.items():
            if slot.required and slot_name not in filled_slots:
                missing.append(slot)
        
        return missing
    
    async def generate_clarification(self, missing_slots: List[Slot], intent: Intent, state: ConversationState) -> str:
        """
        Génère une clarification naturelle pour les slots manquants
        
        Args:
            missing_slots: Liste des slots manquants
            intent: Intent actuel
            state: État de la conversation
            
        Returns:
            Question de clarification
        """
        if not missing_slots:
            return ""
        
        # Prendre le premier slot manquant prioritaire
        slot = missing_slots[0]
        
        # Contexte pour personnaliser la question
        filled_info = []
        for slot_name, value in state.filled_slots.items():
            filled_info.append(f"{slot_name}: {value}")
        
        prompt = f"""Tu es un assistant touristique conversationnel et chaleureux.

L'utilisateur veut: {intent.description}
Informations déjà connues: {', '.join(filled_info) if filled_info else 'Aucune'}

Il manque l'information suivante:
- Nom: {slot.name}
- Description: {slot.description}
- Exemples: {', '.join(slot.examples)}

Génère une question naturelle et amicale pour obtenir cette information.
La question doit être courte et directe.

Question:"""

        try:
            response = self.model.generate_content(prompt)
            clarification = response.text.strip()
            
            # Ajouter des suggestions si pertinent
            if slot.examples:
                clarification += f"\n\nPar exemple : {', '.join(slot.examples[:3])}"
            
            return clarification
            
        except Exception as e:
            logger.error(f"Erreur génération clarification: {e}")
            # Fallback simple
            return f"Pouvez-vous préciser {slot.description.lower()} ?"
    
    async def generate_response_with_rag(self, intent: Intent, filled_slots: Dict[str, Any], state: ConversationState) -> str:
        """
        Génère la réponse finale en utilisant le RAG si nécessaire
        
        Args:
            intent: Intent complété
            filled_slots: Tous les slots remplis
            state: État de la conversation
            
        Returns:
            Réponse finale
        """
        logger.info(f"🎯 generate_response_with_rag appelé pour intent: {intent.name}")
        
        # Déterminer si on a besoin du RAG
        needs_rag = intent.name in ['search_activity', 'search_restaurant', 'search_accommodation', 
                                    'search_poi', 'plan_visit', 'get_recommendations',
                                    'restaurant', 'randonnee', 'activite_sportive', 'hebergement']
        logger.info(f"🔍 needs_rag pour {intent.name}: {needs_rag}")
        needs_weather = intent.name in ['weather_info', 'weather_activity', 'meteo']
        needs_water_temp = intent.name in ['water_temperature', 'swimming_advice', 'lake_info', 'baignade']
        
        logger.info(f"🔍 needs_weather pour {intent.name}: {needs_weather}")
        logger.info(f"🔍 weather_service disponible: {self.weather_service is not None}")
        
        rag_results = []
        weather_data = None
        water_temp_data = None
        
        # Récupérer les données réelles depuis Supabase
        if needs_rag and self.supabase_service:
            # D'abord récupérer le territoire
            territory = None
            territory_id = None
            
            # Si on a un territoire dans le state ou déterminer depuis le contexte
            if hasattr(state, 'territory_slug'):
                territory_slug = state.territory_slug
                logger.info(f"🔍 Territoire depuis state.territory_slug: {territory_slug}")
            elif hasattr(state, 'context') and state.context.get('territory'):
                territory_slug = state.context['territory']
                logger.info(f"🔍 Territoire depuis state.context: {territory_slug}")
            else:
                territory_slug = 'annecy'  # Par défaut
                logger.info(f"🔍 Territoire par défaut: {territory_slug}")
            
            logger.info(f"🎯 Recherche RAG pour intent '{intent.name}' avec territoire '{territory_slug}'")
            
            try:
                territory = self.supabase_service.get_territory_by_slug(territory_slug)
                if territory:
                    territory_id = territory['id']
                    logger.info(f"✅ Territoire trouvé: {territory['name']}")
                else:
                    logger.error(f"❌ Territoire {territory_slug} non trouvé")
            except Exception as e:
                logger.error(f"❌ Erreur récupération territoire: {e}")
            
            # Récupérer les POIs selon l'intent
            if territory_id:
                try:
                    if intent.name in ['search_restaurant', 'restaurant']:
                        # Détecter les préférences de cuisine depuis les slots
                        cuisine_preference = None
                        if 'type_cuisine' in filled_slots:
                            cuisine_preference = filled_slots['type_cuisine']
                        elif 'local' in filled_slots or any(keyword in str(filled_slots.values()).lower() for keyword in ['local', 'traditionnel', 'savoyard']):
                            cuisine_preference = 'local'
                        
                        rag_results = self.supabase_service.get_restaurants(territory_id, limit=5, cuisine_preference=cuisine_preference)
                        logger.info(f"✅ {len(rag_results)} restaurants trouvés (cuisine: {cuisine_preference})")
                    
                    elif intent.name in ['search_activity', 'randonnee', 'activite_sportive']:
                        rag_results = self.supabase_service.get_activities(territory_id, outdoor=True, limit=5)
                        logger.info(f"✅ {len(rag_results)} activités trouvées")
                    
                    elif intent.name in ['search_poi', 'plan_visit']:
                        # Recherche générale dans tous les POIs
                        search_text = filled_slots.get('type', filled_slots.get('theme', 'visite'))
                        rag_results = self.supabase_service.search_pois_by_text(territory_id, search_text, limit=5)
                        logger.info(f"✅ {len(rag_results)} POIs trouvés pour '{search_text}'")
                    
                    else:
                        # Recherche générale
                        rag_results = self.supabase_service.get_pois_by_territory(territory_id, limit=5)
                        logger.info(f"✅ {len(rag_results)} POIs généraux trouvés")
                        
                except Exception as e:
                    logger.error(f"❌ Erreur récupération POIs Supabase: {e}")
                    rag_results = []
            else:
                rag_results = []
        
        # Fallback sur RAG service classique si pas de Supabase
        elif needs_rag and self.rag_service:
            # Construire la requête RAG
            query_parts = []
            if 'type' in filled_slots:
                query_parts.append(filled_slots['type'])
            if 'location' in filled_slots:
                query_parts.append(f"à {filled_slots['location']}")
            if 'theme' in filled_slots:
                query_parts.append(filled_slots['theme'])
            if 'budget' in filled_slots:
                query_parts.append(f"budget {filled_slots['budget']}")
            
            query = " ".join(query_parts)
            logger.info(f"Requête RAG fallback: {query}")
            
            try:
                rag_results = await self.rag_service.search(query, limit=5)
            except Exception as e:
                logger.error(f"Erreur RAG: {e}")
                rag_results = []
        
        # Appeler le service météo si nécessaire
        if needs_weather and self.weather_service:
            location = filled_slots.get('localisation', filled_slots.get('location', 'Annecy'))
            date = filled_slots.get('date', 'aujourd\'hui')
            
            try:
                logger.info(f"🌤️ Appel service météo pour {location}, date: {date}")
                
                # Décider entre météo actuelle ou prévisions selon la date
                if date in ['aujourd\'hui', 'maintenant', 'actuellement']:
                    weather_data = await self.weather_service.get_current_weather(location)
                    logger.info(f"✅ Météo actuelle récupérée: {weather_data}")
                else:
                    # Pour les prévisions, utiliser 5 jours par défaut
                    weather_data = await self.weather_service.get_forecast(location, 5)
                    logger.info(f"✅ Prévisions météo récupérées: {weather_data}")
                    
            except Exception as e:
                logger.error(f"❌ Erreur service météo: {e}")
                weather_data = None
        
        # Appeler le service température de l'eau si nécessaire
        if needs_water_temp and self.water_temperature_service:
            location = filled_slots.get('location', filled_slots.get('plan_eau', 'lac d\'Annecy'))
            # Récupérer le territoire depuis le contexte ou par défaut
            territory_slug = state.context.get('territory', 'annecy') if hasattr(state, 'context') else 'annecy'
            
            try:
                if intent.name == 'swimming_advice' or 'combinaison' in filled_slots.get('question', ''):
                    water_temp_data = await self.water_temperature_service.get_swimming_advice(location, territory_slug)
                else:
                    water_temp_data = await self.water_temperature_service.get_water_temperature(location, territory_slug)
                logger.info(f"✅ Données température eau récupérées pour {location}")
            except Exception as e:
                logger.error(f"Erreur température eau: {e}")
        
        # ANALYSE INTELLIGENTE du contexte
        context = self._analyze_intent_context(intent, rag_results)
        logger.info(f"🧠 Analyse intelligente: {context}")
        
        # Log détaillé pour debug
        if rag_results:
            logger.info(f"🔍 Analyse de {len(rag_results)} POIs:")
            for i, poi in enumerate(rag_results[:3]):
                logger.info(f"   POI #{i+1}: {poi.get('name')} (type: {poi.get('type')})")
        
        # Ajouter les données supplémentaires au prompt si nécessaire
        additional_data = {}
        if weather_data:
            additional_data['weather'] = weather_data
        if water_temp_data:
            additional_data['water_temperature'] = water_temp_data
        
        # GÉNÉRATION INTELLIGENTE du prompt adaptatif
        prompt = self._generate_smart_prompt(intent, filled_slots, rag_results, context)
        
        # Ajouter les données supplémentaires si présentes
        if additional_data:
            prompt += f"\nDonnées supplémentaires:\n{json.dumps(additional_data, ensure_ascii=False, indent=2)}\n"

        try:
            # Log du prompt final envoyé à l'IA (tronqué pour lisibilité)
            logger.info(f"📤 Prompt envoyé à l'IA ({len(prompt)} caractères):")
            logger.info(f"   Début: {prompt[:200]}...")
            logger.info(f"   Fin: ...{prompt[-200:]}")
            
            response = self.model.generate_content(prompt)
            ai_response = response.text.strip()
            
            # Log de la réponse IA pour vérifier si elle contient les liens
            logger.info(f"📥 Réponse IA reçue ({len(ai_response)} caractères):")
            logger.info(f"   Contient 'https://': {('https://' in ai_response)}")
            logger.info(f"   Contient 'maps.google': {('maps.google' in ai_response)}")
            logger.info(f"   Contient 'maps.apple': {('maps.apple' in ai_response)}")
            logger.info(f"   Contient 'maps_links': {('maps_links' in ai_response)}")
            logger.info(f"   Réponse: {ai_response}")
            
            return ai_response
            
        except Exception as e:
            logger.error(f"Erreur génération réponse: {e}")
            # Fallback avec Mistral si disponible
            if self.mistral_api_key:
                try:
                    logger.info("🔄 Fallback vers Mistral pour génération réponse")
                    ai_response = self.call_mistral(prompt)
                    
                    # Log de la réponse Mistral
                    logger.info(f"📥 Réponse Mistral reçue ({len(ai_response)} caractères):")
                    logger.info(f"   Contient 'https://': {('https://' in ai_response)}")
                    logger.info(f"   Contient 'maps.google': {('maps.google' in ai_response)}")
                    logger.info(f"   Contient 'maps.apple': {('maps.apple' in ai_response)}")
                    logger.info(f"   Contient 'maps_links': {('maps_links' in ai_response)}")
                    logger.info(f"   Réponse: {ai_response}")
                    
                    return ai_response
                    
                except Exception as mistral_error:
                    logger.error(f"Erreur Mistral fallback: {mistral_error}")
            
            return "Désolé, je rencontre un problème pour générer la réponse. Pouvez-vous reformuler votre demande ?"
    
    async def process_message(self, message: str, session_id: str, state: Optional[ConversationState] = None) -> Dict:
        """
        Point d'entrée principal pour traiter un message
        
        Args:
            message: Message utilisateur
            session_id: ID de session
            state: État de conversation existant
            
        Returns:
            Dictionnaire avec la réponse et l'état mis à jour
        """
        # Initialiser l'état si nécessaire
        if state is None:
            state = ConversationState(session_id=session_id)
        
        # Ajouter le message à l'historique
        state.history.append({"role": "user", "content": message})
        
        # Détecter l'intent si pas déjà fait
        if not state.intent:
            state.intent = await self.detect_intent(message, state.context)
            if not state.intent:
                # Intent non détecté, chat général
                return {
                    "type": "response",
                    "message": "Je ne suis pas sûr de comprendre. Pouvez-vous reformuler votre demande ?",
                    "state": state,
                    "complete": True
                }
        
        # Extraire les slots du message
        extracted_slots = await self.extract_slots(message, state.intent, state)
        
        # Fusionner avec les slots existants
        state.filled_slots.update(extracted_slots)
        
        # Auto-remplir les slots manquants avec le contexte
        state.filled_slots = self.auto_fill_slots_from_context(state.intent, state.filled_slots, state)
        
        # Vérifier les slots manquants
        missing_slots = self.check_missing_slots(state.intent, state.filled_slots)
        
        if missing_slots:
            # Générer une clarification
            clarification = await self.generate_clarification(missing_slots, state.intent, state)
            
            # Ajouter à l'historique
            state.history.append({"role": "assistant", "content": clarification})
            
            return {
                "type": "clarification",
                "message": clarification,
                "state": state,
                "complete": False,
                "missing_slots": [slot.name for slot in missing_slots]
            }
        else:
            # Tous les slots sont remplis, générer la réponse finale
            response = await self.generate_response_with_rag(state.intent, state.filled_slots, state)
            
            # Ajouter à l'historique
            state.history.append({"role": "assistant", "content": response})
            
            # Réinitialiser pour la prochaine requête mais garder le contexte territorial
            preserved_context = {
                "previous_intent": state.intent.name,
                "territory": state.context.get("territory") if hasattr(state, 'context') else None
            }
            new_state = ConversationState(
                session_id=session_id,
                context=preserved_context,
                history=state.history[-10:]  # Garder les 10 derniers messages
            )
            
            return {
                "type": "response",
                "message": response,
                "state": new_state,
                "complete": True,
                "intent": state.intent.name,
                "slots": state.filled_slots
            }