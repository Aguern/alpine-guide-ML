"""
Service Météo Unifié AlpineGuide
Centralise toute la logique météo pour les 3 types de demandes :
1. Flash : Météo temps réel pour recommandations immédiates
2. Interactive : Contexte météo pour conseils personnalisés
3. Planning : Prévisions pour planification séjour
"""
import httpx
import json
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import asyncio
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class WeatherService:
    """Service météo unifié pour tous les types de demandes touristiques"""
    
    def __init__(self):
        # Configuration Open-Meteo
        self.base_url = "https://api.open-meteo.com/v1"
        self.timeout = 10  # Timeout pour les requetes HTTP
        
        # Coordonnees Annecy
        self.default_locations = {
            'annecy': {
                'lat': 45.899247,
                'lon': 6.129384,
                'name': 'Annecy'
            }
        }
        
        # Seuils pour les alertes
        self.thresholds = {
            'precipitation': {
                'light': 2.0,     # mm/h - pluie legere
                'moderate': 5.0,  # mm/h - pluie moderee  
                'heavy': 10.0     # mm/h - forte pluie
            },
            'wind': {
                'moderate': 40,   # km/h - vent modere
                'strong': 60,     # km/h - vent fort
                'storm': 80       # km/h - tempete
            },
            'temperature': {
                'frost': 0,       # gel
                'cold': 5,        # froid
                'hot': 30,        # forte chaleur
                'extreme': 35     # canicule
            }
        }
    
    async def get_forecast(self, location: str = 'annecy', days: int = 3) -> Dict:
        """
        Recupere les previsions Open-Meteo pour une localisation
        
        Args:
            location: Nom de la localisation (defaut: annecy)
            days: Nombre de jours de prevision (1-7)
            
        Returns:
            Dict avec les previsions structurees
        """
        try:
            coords = self.default_locations.get(location, self.default_locations['annecy'])
            
            # Appel a l'API Open-Meteo
            weather_data = await self._fetch_openmeteo_data(coords['lat'], coords['lon'], days)
            
            if not weather_data:
                logger.warning("Pas de donnees Open-Meteo, utilisation des donnees simulees")
                return self._get_mock_forecast(location, days)
            
            # Convertir en format standardise
            forecasts = {
                'location': coords,
                'generated_at': datetime.utcnow().isoformat(),
                'daily': []
            }
            
            # Traiter les donnees par jour
            for day_offset in range(days):
                forecast_date = datetime.now() + timedelta(days=day_offset)
                
                # Extraire les donnees de la journee
                daily_data = self._extract_daily_data(weather_data, day_offset)
                
                # Analyser les risques meteo
                weather_risks = self._analyze_weather_risks(daily_data)
                
                forecasts['daily'].append({
                    'date': forecast_date.strftime('%Y-%m-%d'),
                    'data': daily_data,
                    'risks': weather_risks,
                    'outdoor_score': self._calculate_outdoor_score(daily_data, weather_risks)
                })
            
            return forecasts
            
        except Exception as e:
            logger.error(f"Erreur recuperation previsions Open-Meteo: {e}")
            # Fallback sur des donnees simulees
            return self._get_mock_forecast(location, days)
    
    async def _fetch_openmeteo_data(self, lat: float, lon: float, days: int) -> Optional[Dict]:
        """Recupere les donnees Open-Meteo pour les coordonnees donnees"""
        try:
            params = {
                'latitude': lat,
                'longitude': lon,
                'daily': 'temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max,winddirection_10m_dominant',
                'hourly': 'temperature_2m,precipitation,windspeed_10m,winddirection_10m,cloudcover,relativehumidity_2m',
                'timezone': 'Europe/Paris',
                'forecast_days': min(days, 7)
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/forecast", params=params)
                response.raise_for_status()
                return response.json()
                
        except Exception as e:
            logger.error(f"Erreur requete Open-Meteo: {e}")
            return None
    
    def _extract_daily_data(self, weather_data: Dict, day_offset: int) -> Dict:
        """Extrait les donnees pour une journee specifique depuis Open-Meteo"""
        try:
            daily = weather_data.get('daily', {})
            hourly = weather_data.get('hourly', {})
            
            # Donnees journalieres
            daily_summary = {
                'temperature_min': daily.get('temperature_2m_min', [])[day_offset] if day_offset < len(daily.get('temperature_2m_min', [])) else 15,
                'temperature_max': daily.get('temperature_2m_max', [])[day_offset] if day_offset < len(daily.get('temperature_2m_max', [])) else 20,
                'precipitation_total': daily.get('precipitation_sum', [])[day_offset] if day_offset < len(daily.get('precipitation_sum', [])) else 0,
                'wind_speed_max': daily.get('windspeed_10m_max', [])[day_offset] if day_offset < len(daily.get('windspeed_10m_max', [])) else 10,
            }
            
            # Donnees horaires pour cette journee (24h)
            start_hour = day_offset * 24
            end_hour = start_hour + 24
            
            hourly_data = []
            for hour in range(24):
                idx = start_hour + hour
                if idx < len(hourly.get('time', [])):
                    hourly_data.append({
                        'hour': hour,
                        'temperature': hourly.get('temperature_2m', [])[idx] if idx < len(hourly.get('temperature_2m', [])) else 15,
                        'precipitation': hourly.get('precipitation', [])[idx] if idx < len(hourly.get('precipitation', [])) else 0,
                        'wind_speed': hourly.get('windspeed_10m', [])[idx] if idx < len(hourly.get('windspeed_10m', [])) else 10,
                        'cloud_cover': hourly.get('cloudcover', [])[idx] if idx < len(hourly.get('cloudcover', [])) else 50,
                        'humidity': hourly.get('relativehumidity_2m', [])[idx] if idx < len(hourly.get('relativehumidity_2m', [])) else 70
                    })
                else:
                    # Donnees par defaut si pas assez de donnees
                    hourly_data.append({
                        'hour': hour,
                        'temperature': 15,
                        'precipitation': 0,
                        'wind_speed': 10,
                        'cloud_cover': 50,
                        'humidity': 70
                    })
            
            # Calculer le type de temps dominant
            avg_cloud = sum(h['cloud_cover'] for h in hourly_data) / 24
            total_precip = sum(h['precipitation'] for h in hourly_data)
            
            dominant_weather = self._determine_weather_type_from_data(total_precip, avg_cloud)
            
            return {
                'hourly': hourly_data,
                'summary': {
                    **daily_summary,
                    'dominant_weather': dominant_weather,
                    'precipitation_probability': len([h for h in hourly_data if h['precipitation'] > 0.1]) / 24 * 100
                }
            }
            
        except Exception as e:
            logger.error(f"Erreur extraction donnees Open-Meteo: {e}")
            # Fallback sur donnees par defaut
            return self._get_fallback_daily_data()
    
    def _determine_weather_type_from_data(self, total_precip: float, avg_cloud: float) -> str:
        """Determine le type de temps selon les donnees Open-Meteo"""
        if total_precip > 10:
            return 'rainy'
        elif total_precip > 2:
            return 'showers'
        elif avg_cloud > 70:
            return 'cloudy'
        elif avg_cloud > 30:
            return 'partly_cloudy'
        else:
            return 'sunny'
    
    def _get_fallback_daily_data(self) -> Dict:
        """Donnees par defaut en cas d'erreur"""
        hourly_data = []
        for hour in range(24):
            hourly_data.append({
                'hour': hour,
                'temperature': 15,
                'precipitation': 0,
                'wind_speed': 10,
                'cloud_cover': 50,
                'humidity': 70
            })
        
        return {
            'hourly': hourly_data,
            'summary': {
                'temperature_min': 12,
                'temperature_max': 20,
                'precipitation_total': 0,
                'wind_speed_max': 15,
                'dominant_weather': 'partly_cloudy',
                'precipitation_probability': 0
            }
        }
    
    def _generate_daily_summary(self, hourly_data: List[Dict]) -> Dict:
        """Genere un resume journalier des donnees horaires"""
        temps = [h['temperature'] for h in hourly_data]
        precipitations = [h['precipitation'] for h in hourly_data]
        
        return {
            'temperature_min': min(temps),
            'temperature_max': max(temps),
            'precipitation_total': sum(precipitations),
            'precipitation_probability': len([p for p in precipitations if p > 0]) / 24 * 100,
            'dominant_weather': self._determine_weather_type(hourly_data)
        }
    
    def _determine_weather_type(self, hourly_data: List[Dict]) -> str:
        """Determine le type de temps dominant"""
        total_precip = sum(h['precipitation'] for h in hourly_data)
        avg_cloud = np.mean([h['cloud_cover'] for h in hourly_data])
        
        if total_precip > 10:
            return 'rainy'
        elif total_precip > 2:
            return 'showers'
        elif avg_cloud > 70:
            return 'cloudy'
        elif avg_cloud > 30:
            return 'partly_cloudy'
        else:
            return 'sunny'
    
    def _analyze_weather_risks(self, daily_data: Dict) -> List[Dict]:
        """Analyse les risques meteo pour les activites exterieures"""
        risks = []
        
        for hour_data in daily_data['hourly']:
            hour = hour_data['hour']
            
            # Risque precipitation
            if hour_data['precipitation'] > self.thresholds['precipitation']['heavy']:
                risks.append({
                    'type': 'heavy_rain',
                    'severity': 'high',
                    'time_slot': self._get_time_slot(hour),
                    'hour': hour,
                    'message': f"Fortes pluies prevues vers {hour}h",
                    'outdoor_activities_affected': ['nature', 'activity', 'sport']
                })
            elif hour_data['precipitation'] > self.thresholds['precipitation']['moderate']:
                risks.append({
                    'type': 'moderate_rain',
                    'severity': 'medium',
                    'time_slot': self._get_time_slot(hour),
                    'hour': hour,
                    'message': f"Pluie moderee prevue vers {hour}h",
                    'outdoor_activities_affected': ['nature', 'activity']
                })
            
            # Risque vent
            if hour_data['wind_speed'] > self.thresholds['wind']['strong']:
                risks.append({
                    'type': 'strong_wind',
                    'severity': 'high',
                    'time_slot': self._get_time_slot(hour),
                    'hour': hour,
                    'message': f"Vents forts prevus vers {hour}h",
                    'outdoor_activities_affected': ['nature', 'activity', 'sport']
                })
            
            # Risque temperature
            if hour_data['temperature'] > self.thresholds['temperature']['hot']:
                if hour >= 11 and hour <= 16:  # Heures les plus chaudes
                    risks.append({
                        'type': 'high_temperature',
                        'severity': 'medium',
                        'time_slot': self._get_time_slot(hour),
                        'hour': hour,
                        'message': f"Forte chaleur prevue ({hour_data['temperature']}�C)",
                        'outdoor_activities_affected': ['nature', 'activity', 'sport']
                    })
        
        return risks
    
    def _get_time_slot(self, hour: int) -> str:
        """Convertit une heure en creneau horaire"""
        if hour < 12:
            return 'morning'
        elif hour < 18:
            return 'afternoon'
        else:
            return 'evening'
    
    def _calculate_outdoor_score(self, daily_data: Dict, risks: List[Dict]) -> float:
        """
        Calcule un score de favorabilite pour les activites exterieures (0-1)
        """
        score = 1.0
        
        # Penalites selon les risques
        risk_penalties = {
            'high': 0.5,
            'medium': 0.25,
            'low': 0.1
        }
        
        for risk in risks:
            penalty = risk_penalties.get(risk['severity'], 0)
            score -= penalty
        
        # Bonus pour beau temps
        if daily_data['summary']['dominant_weather'] == 'sunny':
            score += 0.2
        elif daily_data['summary']['dominant_weather'] == 'partly_cloudy':
            score += 0.1
        
        return max(0, min(1, score))
    
    async def check_activity_conflicts(self, journey_day: Dict, weather_forecast: Dict) -> List[Dict]:
        """
        Verifie les conflits entre activites prevues et meteo
        
        Args:
            journey_day: Journee du parcours avec activites
            weather_forecast: Previsions pour cette journee
            
        Returns:
            Liste des conflits detectes avec suggestions
        """
        conflicts = []
        risks = weather_forecast['risks']
        
        # Verifier chaque activite
        for time_slot in ['morning', 'afternoon', 'evening']:
            activities = getattr(journey_day, f'{time_slot}_activities', [])
            
            for activity in activities:
                # Verifier si l'activite est impactee par la meteo
                slot_risks = [r for r in risks if r['time_slot'] == time_slot]
                
                for risk in slot_risks:
                    if activity.type in risk.get('outdoor_activities_affected', []):
                        conflicts.append({
                            'activity': activity,
                            'time_slot': time_slot,
                            'risk': risk,
                            'impact_level': self._assess_impact_level(activity, risk),
                            'suggestions': await self._generate_alternatives(activity, risk, time_slot)
                        })
        
        return conflicts
    
    def _assess_impact_level(self, activity: Dict, risk: Dict) -> str:
        """Evalue le niveau d'impact de la meteo sur l'activite"""
        # Activites tres sensibles a la meteo
        if activity.type in ['nature', 'sport'] and risk['severity'] == 'high':
            return 'critical'
        
        # Impact modere
        if risk['severity'] == 'medium':
            return 'moderate'
        
        return 'low'
    
    async def _generate_alternatives(self, activity: Dict, risk: Dict, time_slot: str) -> List[Dict]:
        """Genere des alternatives intelligentes pour une activite impactee"""
        alternatives = []
        
        # Strategie 1: Decaler l'horaire (pour risques temporaires)
        if risk['type'] in ['moderate_rain', 'high_temperature'] and risk['severity'] != 'high':
            better_slot = self._find_better_time_slot(time_slot, risk)
            if better_slot != time_slot:
                alternatives.append({
                    'type': 'reschedule',
                    'action': 'time_shift',
                    'description': f"Décaler l'activité au {self._get_slot_name(better_slot)}",
                    'new_time_slot': better_slot,
                    'confidence': 0.8,
                    'reason': f"Éviter {risk['message'].lower()}"
                })
        
        # Strategie 2: Remplacer par une activite similaire mais interieure
        if risk['type'] in ['heavy_rain', 'strong_wind', 'storm']:
            indoor_alternatives = self._get_indoor_alternatives(activity)
            for alt in indoor_alternatives:
                alternatives.append({
                    'type': 'replace',
                    'action': 'indoor_substitute',
                    'description': f"Remplacer par {alt['name']}",
                    'suggested_poi_types': alt['types'],
                    'confidence': alt['confidence'],
                    'reason': "Conditions météo défavorables pour l'extérieur",
                    'weather_proof': True
                })
        
        # Strategie 3: Activite partiellement protegee
        if risk['type'] in ['light_rain', 'moderate_rain']:
            protected_alternatives = self._get_protected_alternatives(activity)
            for alt in protected_alternatives:
                alternatives.append({
                    'type': 'modify',
                    'action': 'semi_protected',
                    'description': f"Adapter vers {alt['name']}",
                    'suggested_poi_types': alt['types'],
                    'confidence': alt['confidence'],
                    'reason': "Activité partiellement protégée de la météo"
                })
        
        return alternatives
    
    def _find_better_time_slot(self, current_slot: str, risk: Dict) -> str:
        """Trouve un meilleur creneau horaire"""
        slots = ['morning', 'afternoon', 'evening']
        current_index = slots.index(current_slot)
        
        # Essayer le creneau precedent ou suivant
        if current_index > 0:
            return slots[current_index - 1]
        elif current_index < len(slots) - 1:
            return slots[current_index + 1]
        
        return current_slot
    
    def _get_slot_name(self, slot: str) -> str:
        """Convertit le nom de créneau en français"""
        slot_names = {
            'morning': 'matin',
            'afternoon': 'après-midi', 
            'evening': 'soir'
        }
        return slot_names.get(slot, slot)
    
    def _get_indoor_alternatives(self, activity: Dict) -> List[Dict]:
        """Trouve des alternatives intérieures selon le type d'activité"""
        activity_type = getattr(activity, 'type', 'unknown')
        
        indoor_mapping = {
            'nature': [
                {'name': 'musée naturel', 'types': ['museum', 'culture'], 'confidence': 0.9},
                {'name': 'aquarium/vivarium', 'types': ['attraction', 'family'], 'confidence': 0.8},
                {'name': 'serre botanique', 'types': ['garden', 'culture'], 'confidence': 0.7}
            ],
            'sport': [
                {'name': 'centre sportif indoor', 'types': ['sport', 'indoor'], 'confidence': 0.9},
                {'name': 'escalade indoor', 'types': ['sport', 'climbing'], 'confidence': 0.8},
                {'name': 'piscine couverte', 'types': ['sport', 'swimming'], 'confidence': 0.7}
            ],
            'activity': [
                {'name': 'activité culturelle', 'types': ['culture', 'art'], 'confidence': 0.8},
                {'name': 'shopping/artisanat', 'types': ['shopping', 'culture'], 'confidence': 0.7},
                {'name': 'atelier créatif', 'types': ['activity', 'creative'], 'confidence': 0.6}
            ],
            'cultural': [
                {'name': 'musée', 'types': ['museum', 'culture'], 'confidence': 0.9},
                {'name': 'galerie d\'art', 'types': ['art', 'culture'], 'confidence': 0.8},
                {'name': 'centre culturel', 'types': ['culture', 'event'], 'confidence': 0.7}
            ]
        }
        
        return indoor_mapping.get(activity_type, [
            {'name': 'activité couverte', 'types': ['indoor', 'culture'], 'confidence': 0.6}
        ])
    
    def _get_protected_alternatives(self, activity: Dict) -> List[Dict]:
        """Trouve des alternatives partiellement protégées"""
        activity_type = getattr(activity, 'type', 'unknown')
        
        protected_mapping = {
            'nature': [
                {'name': 'promenade couverte', 'types': ['nature', 'covered'], 'confidence': 0.7},
                {'name': 'marché couvert', 'types': ['market', 'local'], 'confidence': 0.6}
            ],
            'activity': [
                {'name': 'activité sous abri', 'types': ['activity', 'covered'], 'confidence': 0.7},
                {'name': 'visite guidée couverte', 'types': ['tour', 'covered'], 'confidence': 0.6}
            ],
            'cultural': [
                {'name': 'monument avec abri', 'types': ['monument', 'covered'], 'confidence': 0.8},
                {'name': 'église/cathédrale', 'types': ['religious', 'culture'], 'confidence': 0.7}
            ]
        }
        
        return protected_mapping.get(activity_type, [
            {'name': 'activité semi-protégée', 'types': ['covered'], 'confidence': 0.5}
        ])
    
    def _get_mock_forecast(self, location: str, days: int) -> Dict:
        """Donnees simulees pour le developpement"""
        mock_forecasts = {
            'location': self.default_locations.get(location),
            'generated_at': datetime.utcnow().isoformat(),
            'daily': []
        }
        
        for day in range(days):
            date = datetime.now() + timedelta(days=day)
            
            # Simulation de differents scenarios meteo
            scenarios = [
                {  # Beau temps
                    'dominant_weather': 'sunny',
                    'temperature_min': 12,
                    'temperature_max': 22,
                    'precipitation_total': 0,
                    'risks': []
                },
                {  # Pluie l'apres-midi
                    'dominant_weather': 'showers',
                    'temperature_min': 10,
                    'temperature_max': 18,
                    'precipitation_total': 5,
                    'risks': [{
                        'type': 'moderate_rain',
                        'severity': 'medium',
                        'time_slot': 'afternoon',
                        'hour': 14,
                        'message': 'Averses prevues en apres-midi',
                        'outdoor_activities_affected': ['nature', 'activity']
                    }]
                },
                {  # Orage
                    'dominant_weather': 'rainy',
                    'temperature_min': 15,
                    'temperature_max': 25,
                    'precipitation_total': 20,
                    'risks': [{
                        'type': 'heavy_rain',
                        'severity': 'high',
                        'time_slot': 'afternoon',
                        'hour': 15,
                        'message': 'Orages prevus en apres-midi',
                        'outdoor_activities_affected': ['nature', 'activity', 'sport']
                    }]
                }
            ]
            
            # Choisir un scenario aleatoire
            scenario = scenarios[day % len(scenarios)]
            
            mock_forecasts['daily'].append({
                'date': date.strftime('%Y-%m-%d'),
                'data': {
                    'summary': {
                        'dominant_weather': scenario['dominant_weather'],
                        'temperature_min': scenario['temperature_min'],
                        'temperature_max': scenario['temperature_max'],
                        'precipitation_total': scenario['precipitation_total']
                    }
                },
                'risks': scenario['risks'],
                'outdoor_score': 0.2 if scenario['risks'] else 0.9
            })
        
        return mock_forecasts

    # ============================================================================
    # MÉTHODES SPÉCIALISÉES POUR LES 3 TYPES DE DEMANDES TOURISTIQUES
    # ============================================================================
    
    async def get_current_weather(self, latitude: float, longitude: float) -> Optional[Dict]:
        """
        Type 1: FLASH - Météo temps réel pour recommandations immédiates
        Optimisé pour les demandes "maintenant" et "près de moi"
        """
        try:
            # Utiliser l'API current weather d'Open-Meteo
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/forecast",
                    params={
                        "latitude": latitude,
                        "longitude": longitude,
                        "current": "temperature_2m,relative_humidity_2m,is_day,precipitation,weather_code,cloud_cover,wind_speed_10m",
                        "timezone": "Europe/Paris"
                    }
                )
                
                if response.status_code != 200:
                    logger.warning(f"Erreur API météo: {response.status_code}")
                    return self._get_mock_current_weather()
                
                data = response.json()
                current = data.get("current", {})
                
                # Formater pour utilisation Flash
                return {
                    "temperature": current.get("temperature_2m", 15),
                    "humidity": current.get("relative_humidity_2m", 60),
                    "is_day": current.get("is_day", 1) == 1,
                    "is_raining": current.get("precipitation", 0) > 0,
                    "cloud_cover": current.get("cloud_cover", 50),
                    "wind_speed": current.get("wind_speed_10m", 0),
                    "weather_code": current.get("weather_code", 1),
                    "condition": self._get_weather_condition_simple(current),
                    "suitable_for_outdoor": self._is_suitable_for_outdoor(current),
                    "recommendations": self._get_flash_weather_recommendations(current),
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Erreur get_current_weather: {e}")
            return self._get_mock_current_weather()
    
    async def get_interactive_weather_context(
        self, 
        latitude: float, 
        longitude: float,
        user_preferences: Optional[Dict] = None
    ) -> Dict:
        """
        Type 2: INTERACTIVE - Contexte météo pour conseils personnalisés
        Adapte les recommandations selon préférences utilisateur et météo
        """
        try:
            # Récupérer météo actuelle + prévisions 24h
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/forecast",
                    params={
                        "latitude": latitude,
                        "longitude": longitude,
                        "current": "temperature_2m,precipitation,weather_code,cloud_cover,wind_speed_10m",
                        "hourly": "temperature_2m,precipitation_probability,weather_code",
                        "forecast_days": 1,
                        "timezone": "Europe/Paris"
                    }
                )
                
                if response.status_code != 200:
                    return self._get_mock_interactive_weather()
                
                data = response.json()
                current = data.get("current", {})
                hourly = data.get("hourly", {})
                
                # Analyser les prévisions des prochaines heures
                next_hours_analysis = self._analyze_next_hours(hourly)
                
                # Adapter selon préférences utilisateur
                weather_advice = self._generate_personalized_weather_advice(
                    current, next_hours_analysis, user_preferences
                )
                
                return {
                    "current_conditions": {
                        "temperature": current.get("temperature_2m", 15),
                        "condition": self._get_weather_condition_simple(current),
                        "is_favorable": self._is_suitable_for_outdoor(current)
                    },
                    "next_hours": next_hours_analysis,
                    "personalized_advice": weather_advice,
                    "activity_recommendations": self._get_interactive_activity_recommendations(current, user_preferences),
                    "timing_suggestions": self._get_timing_suggestions(next_hours_analysis),
                    "context_for_chat": self._generate_weather_context_text(current, next_hours_analysis)
                }
                
        except Exception as e:
            logger.error(f"Erreur get_interactive_weather_context: {e}")
            return self._get_mock_interactive_weather()
    
    async def get_planning_weather_forecast(
        self,
        latitude: float,
        longitude: float,
        start_date: Optional[str] = None,
        duration_days: int = 7
    ) -> Dict:
        """
        Type 3: PLANNING - Prévisions pour planification séjour
        Prévisions détaillées pour optimiser l'itinéraire
        """
        try:
            # Récupérer prévisions étendues
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/forecast",
                    params={
                        "latitude": latitude,
                        "longitude": longitude,
                        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max",
                        "forecast_days": min(duration_days, 14),  # Max 14 jours
                        "timezone": "Europe/Paris"
                    }
                )
                
                if response.status_code != 200:
                    return self._get_mock_planning_weather(duration_days)
                
                data = response.json()
                daily = data.get("daily", {})
                
                # Analyser jour par jour pour planification
                daily_analysis = self._analyze_daily_for_planning(daily)
                
                # Suggestions d'optimisation d'itinéraire
                itinerary_suggestions = self._generate_itinerary_weather_suggestions(daily_analysis)
                
                return {
                    "forecast_period": {
                        "start_date": start_date or datetime.now().strftime("%Y-%m-%d"),
                        "duration_days": duration_days,
                        "forecast_available_days": len(daily_analysis)
                    },
                    "daily_forecasts": daily_analysis,
                    "itinerary_suggestions": itinerary_suggestions,
                    "best_days": self._identify_best_weather_days(daily_analysis),
                    "weather_risks": self._identify_planning_weather_risks(daily_analysis),
                    "alternative_plans": self._generate_weather_alternative_plans(daily_analysis)
                }
                
        except Exception as e:
            logger.error(f"Erreur get_planning_weather_forecast: {e}")
            return self._get_mock_planning_weather(duration_days)
    
    # ============================================================================
    # MÉTHODES UTILITAIRES POUR LES 3 TYPES
    # ============================================================================
    
    def _get_weather_condition_simple(self, weather_data: Dict) -> str:
        """Détermine la condition météo simplifiée"""
        weather_code = weather_data.get("weather_code", 1)
        
        # Codes WMO simplifiés
        if weather_code in [0, 1]:
            return "sunny"
        elif weather_code in [2, 3]:
            return "cloudy"
        elif weather_code in [51, 53, 55, 56, 57]:
            return "drizzle"
        elif weather_code in [61, 63, 65, 66, 67]:
            return "rainy"
        elif weather_code in [71, 73, 75]:
            return "snowy"
        elif weather_code in [95, 96, 99]:
            return "stormy"
        else:
            return "cloudy"
    
    def _is_suitable_for_outdoor(self, weather_data: Dict) -> bool:
        """Détermine si la météo est favorable aux activités extérieures"""
        precipitation = weather_data.get("precipitation", 0)
        wind_speed = weather_data.get("wind_speed_10m", 0)
        temperature = weather_data.get("temperature_2m", 15)
        
        # Critères de base
        if precipitation > 2:  # Plus de 2mm de pluie
            return False
        if wind_speed > 50:  # Vent fort
            return False
        if temperature < 0 or temperature > 35:  # Températures extrêmes
            return False
        
        return True
    
    def _get_flash_weather_recommendations(self, weather_data: Dict) -> List[str]:
        """Recommandations rapides selon météo actuelle"""
        recommendations = []
        condition = self._get_weather_condition_simple(weather_data)
        
        if condition == "sunny":
            recommendations.extend([
                "Profitez des terrasses et activités en plein air",
                "Idéal pour les randonnées et balades au lac",
                "Parfait pour les visites avec points de vue"
            ])
        elif condition == "rainy":
            recommendations.extend([
                "Privilégiez les musées et activités couvertes",
                "Parfait pour découvrir la gastronomie locale",
                "Visitez les sites historiques avec abri"
            ])
        elif condition == "cloudy":
            recommendations.extend([
                "Conditions idéales pour les activités urbaines",
                "Bonne visibilité pour les balades",
                "Températures agréables pour marcher"
            ])
        
        return recommendations
    
    def _get_timing_suggestions(self, next_hours_analysis: Dict) -> List[str]:
        """Génère des suggestions de timing selon prévisions"""
        suggestions = []
        
        if next_hours_analysis.get("rain_likelihood", 0) > 70:
            suggestions.append("Reportez les activités extérieures de quelques heures")
        
        if next_hours_analysis.get("best_window") is not None:
            hour = next_hours_analysis["best_window"]
            suggestions.append(f"Meilleure fenêtre météo vers {9 + hour}h")
        
        return suggestions or ["Timing flexible selon les conditions"]
    
    def _analyze_next_hours(self, hourly_data: Dict) -> Dict:
        """Analyse les prochaines heures pour contexte interactif"""
        if not hourly_data:
            return {"hours_analyzed": 0, "trend": "stable"}
        
        # Analyser les 6 prochaines heures
        temps = hourly_data.get("temperature_2m", [])[:6]
        precip_prob = hourly_data.get("precipitation_probability", [])[:6]
        
        # Tendances
        temp_trend = "stable"
        if len(temps) >= 2:
            if temps[-1] > temps[0] + 3:
                temp_trend = "rising"
            elif temps[-1] < temps[0] - 3:
                temp_trend = "falling"
        
        rain_likelihood = max(precip_prob) if precip_prob else 0
        
        return {
            "hours_analyzed": len(temps),
            "temperature_trend": temp_trend,
            "rain_likelihood": rain_likelihood,
            "best_window": self._find_best_weather_window(precip_prob),
            "avoid_window": self._find_worst_weather_window(precip_prob)
        }
    
    def _generate_personalized_weather_advice(
        self, 
        current: Dict, 
        next_hours: Dict, 
        user_preferences: Optional[Dict]
    ) -> List[str]:
        """Génère des conseils météo personnalisés"""
        advice = []
        
        # Conseil de base selon conditions actuelles
        if current.get("precipitation", 0) > 0:
            advice.append("Il pleut actuellement, privilégiez les activités couvertes")
        
        # Conseil selon tendance
        if next_hours.get("temperature_trend") == "falling":
            advice.append("Températures en baisse, prévoyez une veste")
        elif next_hours.get("temperature_trend") == "rising":
            advice.append("Températures en hausse, profitez-en pour les activités extérieures")
        
        # Conseil selon préférences utilisateur
        if user_preferences:
            if "nature" in user_preferences.get("activity_preferences", []):
                if next_hours.get("rain_likelihood", 0) > 70:
                    advice.append("Forte probabilité de pluie, reprogrammez les activités nature")
                else:
                    advice.append("Conditions favorables pour les activités nature")
        
        return advice or ["Conditions météo normales pour la saison"]
    
    def _get_interactive_activity_recommendations(
        self, 
        current: Dict, 
        user_preferences: Optional[Dict]
    ) -> Dict:
        """Recommandations d'activités selon météo et préférences"""
        condition = self._get_weather_condition_simple(current)
        
        recommendations = {
            "highly_recommended": [],
            "recommended": [],
            "not_recommended": []
        }
        
        if condition == "sunny":
            recommendations["highly_recommended"] = ["nature", "outdoor", "terrasse"]
            recommendations["recommended"] = ["culture", "visite"]
            recommendations["not_recommended"] = []
        elif condition == "rainy":
            recommendations["highly_recommended"] = ["culture", "museum", "restaurant"]
            recommendations["recommended"] = ["shopping", "indoor"]
            recommendations["not_recommended"] = ["nature", "outdoor"]
        else:  # cloudy
            recommendations["highly_recommended"] = ["culture", "visite", "balade"]
            recommendations["recommended"] = ["restaurant", "nature"]
            recommendations["not_recommended"] = []
        
        return recommendations
    
    def _analyze_daily_for_planning(self, daily_data: Dict) -> List[Dict]:
        """Analyse jour par jour pour planification"""
        daily_analysis = []
        
        dates = daily_data.get("time", [])
        temp_max = daily_data.get("temperature_2m_max", [])
        temp_min = daily_data.get("temperature_2m_min", [])
        precip_sum = daily_data.get("precipitation_sum", [])
        precip_prob = daily_data.get("precipitation_probability_max", [])
        weather_codes = daily_data.get("weather_code", [])
        
        for i in range(len(dates)):
            day_analysis = {
                "date": dates[i],
                "temperature": {
                    "min": temp_min[i] if i < len(temp_min) else 10,
                    "max": temp_max[i] if i < len(temp_max) else 20
                },
                "precipitation": {
                    "sum": precip_sum[i] if i < len(precip_sum) else 0,
                    "probability": precip_prob[i] if i < len(precip_prob) else 0
                },
                "condition": self._get_weather_condition_simple({"weather_code": weather_codes[i] if i < len(weather_codes) else 1}),
                "outdoor_score": self._calculate_daily_outdoor_score(
                    temp_max[i] if i < len(temp_max) else 20,
                    precip_sum[i] if i < len(precip_sum) else 0,
                    precip_prob[i] if i < len(precip_prob) else 0
                ),
                "activity_recommendations": self._get_daily_activity_recommendations(
                    temp_max[i] if i < len(temp_max) else 20,
                    precip_sum[i] if i < len(precip_sum) else 0
                )
            }
            daily_analysis.append(day_analysis)
        
        return daily_analysis
    
    def _calculate_daily_outdoor_score(self, temp_max: float, precip_sum: float, precip_prob: float) -> float:
        """Calcule un score de favorabilité pour activités extérieures"""
        score = 1.0
        
        # Pénalité température
        if temp_max < 5 or temp_max > 35:
            score *= 0.3
        elif temp_max < 10 or temp_max > 30:
            score *= 0.6
        elif temp_max >= 15 and temp_max <= 25:
            score *= 1.2  # Bonus température idéale
        
        # Pénalité précipitations
        if precip_sum > 10:
            score *= 0.2
        elif precip_sum > 5:
            score *= 0.5
        elif precip_sum > 1:
            score *= 0.8
        
        # Pénalité probabilité pluie
        if precip_prob > 80:
            score *= 0.4
        elif precip_prob > 50:
            score *= 0.7
        
        return min(max(score, 0.0), 1.0)
    
    def _get_daily_activity_recommendations(self, temp_max: float, precip_sum: float) -> Dict:
        """Recommandations d'activités pour une journée"""
        if precip_sum > 5:
            return {
                "morning": ["museum", "culture"],
                "afternoon": ["restaurant", "shopping"],
                "evening": ["culture", "indoor"]
            }
        elif temp_max > 25:
            return {
                "morning": ["nature", "outdoor"],
                "afternoon": ["restaurant", "indoor"],  # Éviter la chaleur
                "evening": ["culture", "balade"]
            }
        else:
            return {
                "morning": ["nature", "culture"],
                "afternoon": ["outdoor", "visite"],
                "evening": ["restaurant", "culture"]
            }
    
    def _identify_best_weather_days(self, daily_analysis: List[Dict]) -> List[Dict]:
        """Identifie les meilleures journées météo"""
        return sorted(
            daily_analysis, 
            key=lambda x: x["outdoor_score"], 
            reverse=True
        )[:3]  # Top 3
    
    def _generate_itinerary_weather_suggestions(self, daily_analysis: List[Dict]) -> List[str]:
        """Suggestions d'optimisation d'itinéraire selon météo"""
        suggestions = []
        
        best_days = self._identify_best_weather_days(daily_analysis)
        worst_days = [day for day in daily_analysis if day["outdoor_score"] < 0.4]
        
        if best_days:
            suggestions.append(f"Planifiez vos activités extérieures le {best_days[0]['date']} (conditions optimales)")
        
        if worst_days:
            for day in worst_days:
                suggestions.append(f"Le {day['date']}, privilégiez les activités intérieures (météo défavorable)")
        
        return suggestions
    
    def _identify_planning_weather_risks(self, daily_analysis: List[Dict]) -> List[Dict]:
        """Identifie les risques météo pour la planification"""
        risks = []
        
        for day in daily_analysis:
            if day["precipitation"]["sum"] > 10:
                risks.append({
                    "date": day["date"],
                    "type": "heavy_rain",
                    "message": "Fortes précipitations prévues",
                    "impact": "Activités extérieures compromises"
                })
            elif day["temperature"]["max"] > 35:
                risks.append({
                    "date": day["date"],
                    "type": "extreme_heat",
                    "message": "Températures très élevées",
                    "impact": "Éviter les activités en plein soleil l'après-midi"
                })
        
        return risks
    
    def _generate_weather_alternative_plans(self, daily_analysis: List[Dict]) -> Dict:
        """Génère des plans alternatifs selon météo"""
        return {
            "rainy_day_plan": {
                "activities": ["museum", "culture", "restaurant", "shopping"],
                "description": "Plan de secours pour jour de pluie"
            },
            "sunny_day_plan": {
                "activities": ["nature", "outdoor", "lac", "randonnée"],
                "description": "Plan optimisé pour beau temps"
            },
            "mixed_weather_plan": {
                "activities": ["culture", "visite", "restaurant"],
                "description": "Plan adaptatif pour météo changeante"
            }
        }
    
    # Méthodes mock pour développement
    def _get_mock_current_weather(self) -> Dict:
        """Mock pour météo actuelle"""
        return {
            "temperature": 18,
            "humidity": 65,
            "is_day": True,
            "is_raining": False,
            "cloud_cover": 30,
            "wind_speed": 5,
            "condition": "sunny",
            "suitable_for_outdoor": True,
            "recommendations": ["Parfait pour les activités extérieures"],
            "timestamp": datetime.now().isoformat()
        }
    
    def _get_mock_interactive_weather(self) -> Dict:
        """Mock pour contexte interactif"""
        return {
            "current_conditions": {
                "temperature": 18,
                "condition": "sunny",
                "is_favorable": True
            },
            "next_hours": {
                "hours_analyzed": 6,
                "temperature_trend": "stable",
                "rain_likelihood": 20
            },
            "personalized_advice": ["Conditions idéales pour vos activités"],
            "activity_recommendations": {
                "highly_recommended": ["nature", "outdoor"],
                "recommended": ["culture"],
                "not_recommended": []
            }
        }
    
    def _get_mock_planning_weather(self, duration_days: int) -> Dict:
        """Mock pour planification"""
        daily_forecasts = []
        for i in range(duration_days):
            daily_forecasts.append({
                "date": (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d"),
                "temperature": {"min": 12, "max": 22},
                "precipitation": {"sum": 0, "probability": 20},
                "condition": "sunny" if i % 2 == 0 else "cloudy",
                "outdoor_score": 0.8 if i % 2 == 0 else 0.6
            })
        
        return {
            "forecast_period": {
                "duration_days": duration_days,
                "forecast_available_days": duration_days
            },
            "daily_forecasts": daily_forecasts,
            "itinerary_suggestions": ["Conditions généralement favorables"],
            "best_days": daily_forecasts[:2],
            "weather_risks": []
        }
    
    def _find_best_weather_window(self, precip_prob: List[float]) -> Optional[int]:
        """Trouve la meilleure fenêtre météo"""
        if not precip_prob:
            return None
        min_prob = min(precip_prob)
        return precip_prob.index(min_prob)
    
    def _find_worst_weather_window(self, precip_prob: List[float]) -> Optional[int]:
        """Trouve la pire fenêtre météo"""
        if not precip_prob:
            return None
        max_prob = max(precip_prob)
        return precip_prob.index(max_prob) if max_prob > 70 else None
    
    def _generate_weather_context_text(self, current: Dict, next_hours: Dict) -> str:
        """Génère un texte de contexte météo pour le chat"""
        condition = self._get_weather_condition_simple(current)
        temp = current.get("temperature_2m", 15)
        
        if condition == "sunny":
            return f"Il fait {temp}°C avec un temps ensoleillé, parfait pour les activités extérieures."
        elif condition == "rainy":
            return f"Il pleut avec {temp}°C, privilégiez les activités couvertes."
        else:
            return f"Temps nuageux à {temp}°C, conditions correctes pour la plupart des activités."