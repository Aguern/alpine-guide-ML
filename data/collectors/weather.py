"""
Collecteur météo simplifié pour Alpine Guide Widget
Utilise OpenWeatherMap API (gratuite jusqu'à 1000 appels/jour)
"""
import requests
import logging
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import os

logger = logging.getLogger(__name__)

class WeatherCollector:
    """Collecteur météo simple et performant"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialise le collecteur météo
        
        Args:
            api_key: Clé API OpenWeatherMap (optionnelle, peut être dans ENV)
        """
        self.api_key = api_key or os.getenv('OPENWEATHERMAP_API_KEY')
        self.base_url = "https://api.openweathermap.org/data/2.5"
        
        if not self.api_key:
            logger.warning("⚠️ Clé API OpenWeatherMap manquante, fonctionnalités météo limitées")
    
    async def get_current_weather(self, location: str) -> Optional[Dict[str, Any]]:
        """
        Récupère la météo actuelle pour une localisation
        
        Args:
            location: Nom de la ville ou coordonnées "lat,lon"
            
        Returns:
            Dictionnaire avec données météo ou None si erreur
        """
        if not self.api_key:
            return self._get_mock_weather(location)
        
        try:
            params = {
                'q': location,
                'appid': self.api_key,
                'units': 'metric',
                'lang': 'fr'
            }
            
            response = requests.get(f"{self.base_url}/weather", params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            return {
                'location': data['name'],
                'country': data['sys']['country'],
                'temperature': round(data['main']['temp']),
                'feels_like': round(data['main']['feels_like']),
                'humidity': data['main']['humidity'],
                'pressure': data['main']['pressure'],
                'description': data['weather'][0]['description'].capitalize(),
                'icon': data['weather'][0]['icon'],
                'wind_speed': data.get('wind', {}).get('speed', 0),
                'wind_direction': data.get('wind', {}).get('deg', 0),
                'visibility': data.get('visibility', 0) / 1000,  # Convertir en km
                'sunrise': datetime.fromtimestamp(data['sys']['sunrise']).strftime('%H:%M'),
                'sunset': datetime.fromtimestamp(data['sys']['sunset']).strftime('%H:%M'),
                'timestamp': datetime.now().isoformat()
            }
            
        except requests.RequestException as e:
            logger.error(f"Erreur API météo: {e}")
            return self._get_mock_weather(location)
        except Exception as e:
            logger.error(f"Erreur traitement météo: {e}")
            return None
    
    async def get_forecast(self, location: str, days: int = 5) -> Optional[Dict[str, Any]]:
        """
        Récupère les prévisions météo
        
        Args:
            location: Nom de la ville
            days: Nombre de jours (max 5 pour l'API gratuite)
            
        Returns:
            Dictionnaire avec prévisions ou None si erreur
        """
        if not self.api_key:
            return self._get_mock_forecast(location, days)
        
        try:
            params = {
                'q': location,
                'appid': self.api_key,
                'units': 'metric',
                'lang': 'fr',
                'cnt': min(days * 8, 40)  # 8 prévisions par jour, max 40
            }
            
            response = requests.get(f"{self.base_url}/forecast", params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Grouper par jour
            daily_forecasts = {}
            for item in data['list']:
                date = datetime.fromtimestamp(item['dt']).date()
                if date not in daily_forecasts:
                    daily_forecasts[date] = []
                daily_forecasts[date].append(item)
            
            # Agrégation par jour
            forecasts = []
            for date, items in list(daily_forecasts.items())[:days]:
                day_temps = [item['main']['temp'] for item in items]
                forecasts.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'day_name': self._get_day_name(date),
                    'temp_min': round(min(day_temps)),
                    'temp_max': round(max(day_temps)),
                    'description': items[0]['weather'][0]['description'].capitalize(),
                    'icon': items[0]['weather'][0]['icon'],
                    'humidity': items[0]['main']['humidity'],
                    'wind_speed': items[0].get('wind', {}).get('speed', 0),
                    'rain_probability': items[0].get('pop', 0) * 100  # Probabilité de pluie
                })
            
            return {
                'location': data['city']['name'],
                'country': data['city']['country'],
                'forecasts': forecasts,
                'timestamp': datetime.now().isoformat()
            }
            
        except requests.RequestException as e:
            logger.error(f"Erreur API prévisions: {e}")
            return self._get_mock_forecast(location, days)
        except Exception as e:
            logger.error(f"Erreur traitement prévisions: {e}")
            return None
    
    def _get_day_name(self, date) -> str:
        """Retourne le nom du jour en français"""
        days = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
        return days[date.weekday()]
    
    def _get_mock_weather(self, location: str) -> Dict[str, Any]:
        """Données météo factices pour les tests"""
        return {
            'location': location,
            'country': 'FR',
            'temperature': 15,
            'feels_like': 13,
            'humidity': 65,
            'pressure': 1013,
            'description': 'Partiellement nuageux',
            'icon': '02d',
            'wind_speed': 2.5,
            'wind_direction': 180,
            'visibility': 10,
            'sunrise': '07:30',
            'sunset': '19:45',
            'timestamp': datetime.now().isoformat(),
            'source': 'mock'
        }
    
    def _get_mock_forecast(self, location: str, days: int) -> Dict[str, Any]:
        """Prévisions factices pour les tests"""
        forecasts = []
        base_date = datetime.now().date()
        
        for i in range(days):
            date = base_date + timedelta(days=i)
            forecasts.append({
                'date': date.strftime('%Y-%m-%d'),
                'day_name': self._get_day_name(date),
                'temp_min': 10 + i,
                'temp_max': 20 + i,
                'description': 'Ensoleillé' if i % 2 == 0 else 'Nuageux',
                'icon': '01d' if i % 2 == 0 else '03d',
                'humidity': 60 + (i * 5),
                'wind_speed': 1.5 + i,
                'rain_probability': i * 10
            })
        
        return {
            'location': location,
            'country': 'FR',
            'forecasts': forecasts,
            'timestamp': datetime.now().isoformat(),
            'source': 'mock'
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Vérifie la santé du service météo"""
        if not self.api_key:
            return {
                'status': 'warning',
                'message': 'API key manquante, mode dégradé actif',
                'features': ['mock_data']
            }
        
        try:
            # Test simple avec Paris
            response = requests.get(
                f"{self.base_url}/weather",
                params={'q': 'Paris', 'appid': self.api_key},
                timeout=5
            )
            response.raise_for_status()
            
            return {
                'status': 'healthy',
                'message': 'Service météo opérationnel',
                'features': ['current_weather', 'forecasts']
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Erreur service météo: {str(e)}',
                'features': ['mock_data']
            }