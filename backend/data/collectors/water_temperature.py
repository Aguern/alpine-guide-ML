"""
Collecteur de température de l'eau avec configuration YAML territoriale
Lecture des données depuis les fichiers config/territories/*.yaml
"""
import yaml
import logging
import os
from typing import Dict, Optional, Any, List
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class WaterTemperatureCollector:
    """Collecteur pour estimer les températures de l'eau avec configuration territoriale"""
    
    def __init__(self, config_path: str = None):
        """
        Initialise le collecteur avec lecture des configurations YAML
        
        Args:
            config_path: Chemin vers le dossier config/territories (optionnel)
        """
        # Déterminer le chemin des configurations
        if config_path is None:
            current_dir = Path(__file__).parent
            config_path = current_dir.parent / "config" / "territories"
        else:
            config_path = Path(config_path)
            
        self.config_path = config_path
        self.territories_config = {}
        
        # Charger toutes les configurations territoriales
        self._load_territories_config()
        
        logger.info(f"✅ Collecteur température eau initialisé avec {len(self.territories_config)} territoires")
    
    def _load_territories_config(self):
        """Charge toutes les configurations de territoires"""
        try:
            if not self.config_path.exists():
                logger.warning(f"Dossier de configuration non trouvé: {self.config_path}")
                return
                
            for yaml_file in self.config_path.glob("*.yaml"):
                territory_slug = yaml_file.stem
                
                try:
                    with open(yaml_file, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f)
                    
                    # Vérifier que la configuration contient des données de plans d'eau
                    if 'territory' in config and 'waterBodies' in config['territory']:
                        self.territories_config[territory_slug] = config['territory']
                        logger.info(f"✅ Configuration chargée pour {territory_slug}")
                    else:
                        logger.debug(f"Pas de données waterBodies dans {yaml_file}")
                        
                except Exception as e:
                    logger.error(f"Erreur chargement {yaml_file}: {e}")
                    
        except Exception as e:
            logger.error(f"Erreur chargement configurations territoriales: {e}")
    
    async def get_water_temperature(self, location: str, territory: str = "annecy") -> Optional[Dict[str, Any]]:
        """
        Estime la température de l'eau pour une localisation
        
        Args:
            location: Nom du plan d'eau ou localisation
            territory: Territoire (slug)
            
        Returns:
            Dictionnaire avec les données de température estimées
        """
        try:
            logger.info(f"🌊 Estimation température eau pour '{location}' dans {territory}")
            
            # Récupérer la configuration du territoire
            territory_config = self.territories_config.get(territory)
            if not territory_config:
                logger.warning(f"Configuration non trouvée pour territoire {territory}")
                return self._get_fallback_temperature(location, territory)
            
            # Identifier le plan d'eau
            water_body = self._identify_water_body(location, territory_config)
            if not water_body:
                logger.warning(f"Plan d'eau non identifié pour '{location}' dans {territory}")
                return self._get_fallback_temperature(location, territory)
            
            # Obtenir la saison actuelle
            season = self._get_current_season()
            
            # Calculer la température estimée
            temperature_data = self._calculate_temperature(water_body, season)
            
            return {
                'temperature': temperature_data['temperature'],
                'temperature_min': temperature_data['min_temp'],
                'temperature_max': temperature_data['max_temp'],
                'confidence': temperature_data['confidence'],
                'season': season,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'location': location,
                'territory': territory,
                'water_body_info': water_body,
                'unit': '°C',
                'timestamp': datetime.now().isoformat(),
                'source': 'configuration_territoriale',
                'description': f"Température estimée pour {water_body.get('description', water_body['name'])}",
                'methodology': "Estimation basée sur configuration territoriale, données saisonnières et caractéristiques du plan d'eau"
            }
            
        except Exception as e:
            logger.error(f"Erreur estimation température eau: {e}")
            return self._get_fallback_temperature(location, territory)
    
    def _identify_water_body(self, location: str, territory_config: Dict) -> Optional[Dict[str, Any]]:
        """Identifie le plan d'eau depuis la localisation et la config territoriale"""
        location_lower = location.lower()
        water_bodies = territory_config.get('waterBodies', {})
        
        # Vérifier le plan d'eau principal
        primary = water_bodies.get('primary')
        if primary:
            primary_name = primary['name'].lower()
            # Correspondance directe ou par mots-clés
            if primary_name in location_lower or any(keyword in location_lower for keyword in primary_name.split()):
                return primary
        
        # Vérifier les plans d'eau secondaires
        secondary = water_bodies.get('secondary', [])
        for water_body in secondary:
            name = water_body['name'].lower()
            if name in location_lower or any(keyword in location_lower for keyword in name.split()):
                return water_body
        
        # Si pas de correspondance exacte, essayer une correspondance par type
        if 'lac' in location_lower:
            # Chercher un lac dans la configuration
            if primary and 'lac' in primary.get('type', ''):
                return primary
            for wb in secondary:
                if 'lac' in wb.get('type', ''):
                    return wb
                    
        elif 'rivière' in location_lower or 'riviere' in location_lower:
            # Chercher une rivière
            if primary and 'riviere' in primary.get('type', ''):
                return primary
            for wb in secondary:
                if 'riviere' in wb.get('type', ''):
                    return wb
        
        # Par défaut, retourner le plan d'eau principal s'il existe
        return primary
    
    def _get_current_season(self) -> str:
        """Détermine la saison actuelle"""
        month = datetime.now().month
        
        if month in [12, 1, 2]:
            return "hiver"
        elif month in [3, 4, 5]:
            return "printemps"
        elif month in [6, 7, 8]:
            return "ete"
        else:
            return "automne"
    
    def _calculate_temperature(self, water_body: Dict, season: str) -> Dict[str, Any]:
        """Calcule la température estimée avec facteurs d'ajustement"""
        temperatures = water_body.get('temperatures', {})
        temp_data = temperatures.get(season)
        
        if not temp_data:
            logger.warning(f"Données température manquantes pour saison {season}")
            # Fallback sur des valeurs moyennes
            temp_data = {"min": 10, "max": 20, "typical": 15}
        
        # Température de base
        base_temp = temp_data.get("typical", temp_data.get("max", 15))
        min_temp = temp_data.get("min", base_temp - 3)
        max_temp = temp_data.get("max", base_temp + 3)
        confidence = temp_data.get("confidence", "moyenne")
        
        # Petite variation aléatoire pour réalisme (basée sur le jour)
        import random
        random.seed(datetime.now().day)
        variation_range = 1.5
        temp_variation = random.uniform(-variation_range, variation_range)
        
        final_temp = round(base_temp + temp_variation)
        
        # S'assurer que la température reste dans les limites
        final_temp = max(min_temp, min(max_temp, final_temp))
        
        return {
            "temperature": final_temp,
            "min_temp": min_temp,
            "max_temp": max_temp,
            "confidence": confidence
        }
    
    def _get_fallback_temperature(self, location: str, territory: str) -> Dict[str, Any]:
        """Fallback générique si pas de configuration"""
        season = self._get_current_season()
        
        # Températures génériques selon la saison
        fallback_temps = {
            "hiver": 6,
            "printemps": 12,
            "ete": 20,
            "automne": 15
        }
        
        base_temp = fallback_temps[season]
        
        return {
            'temperature': base_temp,
            'temperature_min': base_temp - 3,
            'temperature_max': base_temp + 3,
            'confidence': "faible",
            'season': season,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'location': location,
            'territory': territory,
            'water_body_info': {
                'name': location,
                'type': 'générique',
                'description': 'Plan d\'eau générique'
            },
            'unit': '°C',
            'timestamp': datetime.now().isoformat(),
            'source': 'estimation_générique',
            'description': f"Température estimée générique pour {location}",
            'methodology': "Estimation générique basée sur la saison uniquement"
        }
    
    async def get_swimming_advice(self, location: str, territory: str = "annecy") -> Dict[str, Any]:
        """
        Donne des conseils pour la baignade basés sur la température estimée
        
        Args:
            location: Plan d'eau
            territory: Territoire
            
        Returns:
            Conseils de baignade avec recommandations équipement
        """
        temp_data = await self.get_water_temperature(location, territory)
        
        if not temp_data:
            return {
                "advice": "Impossible de déterminer la température de l'eau actuellement.",
                "recommended_gear": [],
                "swimming_conditions": "unknown"
            }
        
        temperature = temp_data.get('temperature', 15)
        water_body_info = temp_data.get('water_body_info', {})
        confidence = temp_data.get('confidence', 'moyenne')
        
        # Récupérer des infos spécifiques du territoire si disponibles
        territory_config = self.territories_config.get(territory, {})
        water_features = territory_config.get('features', {}).get('core', {}).get('water_temperature', {})
        warning_message = water_features.get('warning_message')
        speciality = water_features.get('speciality')
        
        # Conseils selon la température
        if temperature < 8:
            conditions = "très_froid"
            advice = f"L'eau est très froide ({temperature}°C). Baignade réservée aux experts en eau froide."
            gear = ["combinaison intégrale épaisse 5mm+", "chaussons néoprène", "gants néoprène", "bonnet néoprène", "surveillance obligatoire"]
        elif temperature < 12:
            conditions = "froid"
            advice = f"L'eau est froide ({temperature}°C). Combinaison intégrale fortement recommandée."
            gear = ["combinaison intégrale 3-5mm", "chaussons néoprène", "temps d'immersion limité"]
        elif temperature < 16:
            conditions = "frais"
            advice = f"L'eau est fraîche ({temperature}°C). Une combinaison shorty est recommandée."
            gear = ["combinaison shorty ou combinaison fine", "serviette chaude pour la sortie"]
        elif temperature < 20:
            conditions = "agréable"
            advice = f"L'eau est à température agréable ({temperature}°C). Parfait pour la baignade !"
            gear = ["maillot de bain standard", "serviette"]
        else:
            conditions = "chaude"
            advice = f"L'eau est chaude ({temperature}°C). Conditions idéales pour la baignade !"
            gear = ["maillot de bain", "crème solaire", "chapeau"]
        
        # Ajouts spécifiques selon le plan d'eau
        water_type = water_body_info.get('type', '')
        additional_info = []
        
        if 'riviere' in water_type or 'torrent' in water_type:
            advice += " ⚠️ Attention : présence de courant, restez vigilant."
            gear.append("chaussures aquatiques antidérapantes")
            additional_info.append("🏔️ Cours d'eau : vérifiez les conditions météo en amont")
            
        if 'glaciaire' in water_body_info.get('characteristics', {}).get('source', ''):
            additional_info.append("🧊 Source glaciaire : température peut chuter rapidement")
            
        # Ajouter les avertissements territoriaux
        if warning_message:
            additional_info.append(warning_message)
        
        response = {
            "temperature_data": temp_data,
            "advice": advice,
            "recommended_gear": gear,
            "swimming_conditions": conditions,
            "comfort_level": self._get_comfort_level(temperature),
            "confidence_note": f"Estimation {confidence} basée sur la configuration territoriale",
            "additional_info": additional_info
        }
        
        if speciality:
            response["territory_speciality"] = speciality
            
        return response
    
    def _get_comfort_level(self, temperature: float) -> str:
        """Détermine le niveau de confort pour la baignade"""
        if temperature < 5:
            return "Extrême - Réservé aux professionnels de l'eau froide"
        elif temperature < 10:
            return "Très inconfortable - Équipement spécialisé requis"
        elif temperature < 15:
            return "Froid - Combinaison obligatoire"
        elif temperature < 18:
            return "Frais - Combinaison recommandée"
        elif temperature < 22:
            return "Agréable - Conditions normales"
        else:
            return "Très agréable - Conditions optimales"
    
    def health_check(self) -> Dict[str, Any]:
        """Vérifie la santé du service de température"""
        territories = list(self.territories_config.keys())
        water_bodies_count = sum(
            len(config.get('waterBodies', {}).get('secondary', [])) + (1 if config.get('waterBodies', {}).get('primary') else 0)
            for config in self.territories_config.values()
        )
        
        return {
            'status': 'healthy',
            'message': 'Service de température basé configuration territoriale opérationnel',
            'features': ['water_temperature_estimation', 'swimming_advice', 'territorial_configuration'],
            'territories_count': len(territories),
            'territories': territories,
            'water_bodies_count': water_bodies_count,
            'config_path': str(self.config_path)
        }
    
    async def get_territory_water_info(self, territory: str) -> Dict[str, Any]:
        """Récupère un résumé des informations sur l'eau pour un territoire"""
        territory_config = self.territories_config.get(territory)
        
        if not territory_config:
            return {
                "territory": territory,
                "status": "not_configured",
                "message": f"Territoire {territory} non configuré"
            }
        
        water_bodies = territory_config.get('waterBodies', {})
        primary = water_bodies.get('primary')
        secondary = water_bodies.get('secondary', [])
        
        result = {
            "territory": territory,
            "status": "configured",
            "data_source": "Configuration YAML territoriale",
            "confidence": "élevée pour plans d'eau configurés"
        }
        
        if primary:
            result["primary_water_body"] = {
                "name": primary['name'],
                "type": primary['type'],
                "description": primary.get('description', '')
            }
        
        if secondary:
            result["secondary_water_bodies"] = [
                {"name": wb['name'], "type": wb['type']} 
                for wb in secondary
            ]
        
        result["total_water_bodies"] = len(secondary) + (1 if primary else 0)
        
        return result