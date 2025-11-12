"""
Service Supabase pour récupérer les vraies données POI d'Annecy
SANS données mock - test authentique uniquement
"""
import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from supabase import create_client, Client

logger = logging.getLogger(__name__)

class SupabaseService:
    """Service pour interagir avec Supabase et récupérer les VRAIES données POI"""
    
    def __init__(self):
        """Initialise la connexion Supabase"""
        self.url = os.getenv('SUPABASE_URL')
        self.key = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_ANON_KEY')
        
        if not self.url or not self.key:
            logger.error("❌ SUPABASE_URL ou SUPABASE_SERVICE_KEY manquantes dans .env")
            raise ValueError("Configuration Supabase requise pour les tests authentiques")
        
        try:
            self.client: Client = create_client(self.url, self.key)
            logger.info("✅ Connexion Supabase établie")
            
            # Test de connexion immédiat
            test_response = self.client.table('territories').select('count', count='exact').execute()
            logger.info(f"✅ Test connexion réussi - {test_response.count} territoires en base")
            
        except Exception as e:
            logger.error(f"❌ Erreur connexion Supabase: {e}")
            raise ConnectionError(f"Impossible de se connecter à Supabase: {e}")
    
    def get_territory_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """Récupère un territoire par son slug depuis la vraie base"""
        try:
            logger.info(f"🔍 Recherche territoire: {slug}")
            
            # Utilise 'active' pour territories (pas 'is_active')
            response = self.client.table('territories').select('*').eq('slug', slug).eq('active', True).execute()
            
            if response.data and len(response.data) > 0:
                territory = response.data[0]
                logger.info(f"✅ Territoire trouvé: {territory.get('name', slug)} (ID: {territory.get('id')})")
                return territory
            else:
                logger.error(f"❌ Territoire {slug} non trouvé ou inactif")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erreur récupération territoire {slug}: {e}")
            raise
    
    def get_pois_by_territory(self, territory_id: str, poi_type: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Récupère les POIs d'un territoire depuis la vraie base"""
        try:
            logger.info(f"🔍 Recherche POIs pour territoire {territory_id}, type={poi_type}, limit={limit}")
            
            query = self.client.table('pois').select('*, gmaps_url, apple_url').eq('territory_id', territory_id).eq('active', True)
            
            if poi_type:
                query = query.eq('type', poi_type)
            
            response = query.limit(limit).execute()
            
            if response.data:
                logger.info(f"✅ {len(response.data)} POIs trouvés")
                # Log des premiers POIs pour debug
                for poi in response.data[:3]:
                    logger.info(f"   • {poi.get('name')} ({poi.get('type')})")
                return self._enrich_pois_with_maps_links(response.data)
            else:
                logger.warning(f"⚠️ Aucun POI trouvé pour territoire {territory_id}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Erreur récupération POIs: {e}")
            raise
    
    def search_pois_by_text(self, territory_id: str, search_text: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Recherche POIs par texte libre dans la vraie base"""
        try:
            logger.info(f"🔍 Recherche textuelle: '{search_text}' dans territoire {territory_id}")
            
            # Recherche dans le nom, description et tags
            response = self.client.table('pois').select('*, gmaps_url, apple_url').eq('territory_id', territory_id).eq('active', True).or_(
                f'name.ilike.%{search_text}%,description.ilike.%{search_text}%,tags.cs.{{{search_text}}}'
            ).limit(limit).execute()
            
            if response.data:
                logger.info(f"✅ {len(response.data)} POIs trouvés pour recherche '{search_text}'")
                return self._enrich_pois_with_maps_links(response.data)
            else:
                logger.info(f"ℹ️ Aucun POI trouvé pour '{search_text}'")
                return []
                
        except Exception as e:
            logger.error(f"❌ Erreur recherche POIs: {e}")
            raise
    
    def get_restaurants(self, territory_id: str, limit: int = 8, cuisine_preference: str = None) -> List[Dict[str, Any]]:
        """Récupère spécifiquement les restaurants depuis la vraie base avec préférence cuisine"""
        logger.info(f"🍽️ Recherche restaurants pour territoire {territory_id}, préférence: {cuisine_preference}")
        
        if cuisine_preference:
            return self.get_restaurants_by_cuisine(territory_id, cuisine_preference, limit)
        else:
            return self.get_pois_by_territory(territory_id, 'restaurant', limit)
    
    def get_restaurants_by_cuisine(self, territory_id: str, cuisine_preference: str, limit: int = 8) -> List[Dict[str, Any]]:
        """Récupère les restaurants en priorisant une préférence de cuisine"""
        try:
            logger.info(f"🔍 Recherche restaurants avec cuisine '{cuisine_preference}' pour territoire {territory_id}")
            
            # Définir les mots-clés pour différents types de cuisine
            cuisine_keywords = {
                'local': ['savoyard', 'savoyarde', 'fondue', 'raclette', 'tartiflette', 'regional', 'traditionnel', 'française'],
                'traditionnel': ['savoyard', 'savoyarde', 'fondue', 'raclette', 'tartiflette', 'regional', 'traditionnel', 'française'],
                'français': ['français', 'française', 'gastronomique', 'bistrot', 'brasserie'],
                'savoyard': ['savoyard', 'savoyarde', 'fondue', 'raclette', 'tartiflette', 'montagne'],
                'gastronomique': ['gastronomique', 'étoilé', 'chef', 'créative', 'fine'],
            }
            
            # Obtenir les mots-clés pour la cuisine demandée
            keywords = cuisine_keywords.get(cuisine_preference.lower(), [cuisine_preference.lower()])
            logger.info(f"Mots-clés recherche: {keywords}")
            
            # Créer une requête OR optimisée avec tous les mots-clés en une seule fois
            or_conditions = []
            for keyword in keywords[:3]:  # Limiter à 3 mots-clés pour éviter les requêtes trop complexes
                or_conditions.extend([
                    f'name.ilike.%{keyword}%',
                    f'description.ilike.%{keyword}%'
                ])
            
            or_query = ','.join(or_conditions)
            logger.info(f"Requête OR optimisée: {len(or_conditions)} conditions")
            
            response = self.client.table('pois').select('*, gmaps_url, apple_url').eq('territory_id', territory_id).eq('active', True).eq('type', 'restaurant').or_(or_query).limit(limit).execute()
            
            unique_restaurants = response.data
            
            # Si on a trouvé des restaurants correspondants, les retourner
            if unique_restaurants:
                logger.info(f"🎯 {len(unique_restaurants)} restaurants prioritaires trouvés pour '{cuisine_preference}'")
                return self._enrich_pois_with_maps_links(unique_restaurants[:limit])
            
            # Sinon fallback sur recherche générale
            logger.info(f"ℹ️ Aucun restaurant spécifique trouvé, fallback recherche générale")
            return self.get_pois_by_territory(territory_id, 'restaurant', limit)
            
        except Exception as e:
            logger.error(f"❌ Erreur recherche restaurants par cuisine: {e}")
            # Fallback sur recherche générale
            return self.get_pois_by_territory(territory_id, 'restaurant', limit)
    
    def get_activities(self, territory_id: str, outdoor: bool = None, limit: int = 8) -> List[Dict[str, Any]]:
        """Récupère les activités depuis la vraie base"""
        try:
            logger.info(f"🏃 Recherche activités pour territoire {territory_id}, outdoor={outdoor}")
            
            query = self.client.table('pois').select('*, gmaps_url, apple_url').eq('territory_id', territory_id).eq('active', True).in_('type', ['activity', 'sport', 'nature'])
            
            if outdoor is not None:
                query = query.eq('outdoor', outdoor)
            
            response = query.limit(limit).execute()
            
            if response.data:
                logger.info(f"✅ {len(response.data)} activités trouvées")
                return self._enrich_pois_with_maps_links(response.data)
            else:
                logger.info(f"ℹ️ Aucune activité trouvée")
                return []
                
        except Exception as e:
            logger.error(f"❌ Erreur récupération activités: {e}")
            raise
    
    def get_poi_details(self, poi_id: str) -> Optional[Dict[str, Any]]:
        """Récupère les détails complets d'un POI"""
        try:
            logger.info(f"🔍 Détails POI: {poi_id}")
            
            response = self.client.table('pois').select('*, gmaps_url, apple_url').eq('id', poi_id).eq('active', True).execute()
            
            if response.data and len(response.data) > 0:
                poi = response.data[0]
                logger.info(f"✅ POI trouvé: {poi.get('name')}")
                enriched_poi = self._enrich_pois_with_maps_links([poi])
                return enriched_poi[0] if enriched_poi else poi
            else:
                logger.warning(f"⚠️ POI {poi_id} non trouvé")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erreur récupération POI {poi_id}: {e}")
            raise
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques de la base de données"""
        try:
            logger.info("📊 Récupération statistiques base de données")
            
            # Compter les territoires
            territories_response = self.client.table('territories').select('id', count='exact').eq('active', True).execute()
            territories_count = territories_response.count
            
            # Compter les POIs
            pois_response = self.client.table('pois').select('id', count='exact').eq('active', True).execute()
            pois_count = pois_response.count
            
            # Compter les POIs par type
            pois_by_type = {}
            types_response = self.client.table('pois').select('type', count='exact').eq('active', True).execute()
            
            stats = {
                'territories_count': territories_count,
                'pois_count': pois_count,
                'last_updated': str(datetime.now()),
                'connection_status': 'healthy'
            }
            
            logger.info(f"✅ Stats: {territories_count} territoires, {pois_count} POIs")
            return stats
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération stats: {e}")
            raise
    
    def verify_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Vérifie une clé API dans la table widget_configs"""
        try:
            logger.info(f"🔑 Vérification API key: {api_key[:16]}...")
            
            # Utilise 'is_active' pour widget_configs (avec préfixe)
            response = self.client.table('widget_configs').select('*, territories(slug, name)').eq('api_key', api_key).eq('is_active', True).execute()
            
            if response.data and len(response.data) > 0:
                config = response.data[0]
                territory = config.get('territories', {})
                logger.info(f"✅ API key valide pour territoire: {territory.get('slug', 'unknown')}")
                return config
            else:
                logger.warning(f"⚠️ API key invalide ou inactive")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erreur vérification API key: {e}")
            raise
    
    def _enrich_pois_with_maps_links(self, pois: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Enrichit les POIs avec les liens cartographiques dans un format standardisé
        
        Args:
            pois: Liste des POIs récupérés de la base
            
        Returns:
            Liste des POIs enrichis avec maps_links
        """
        enriched_pois = []
        
        for poi in pois:
            # Copier le POI original
            enriched_poi = poi.copy()
            
            # Extraire les URLs cartographiques
            gmaps_url = poi.get('gmaps_url')
            apple_url = poi.get('apple_url')
            
            # Ajouter les liens cartographiques dans un format standardisé
            enriched_poi['maps_links'] = {
                'google_maps': gmaps_url,
                'apple_maps': apple_url,
                'has_links': bool(gmaps_url or apple_url)
            }
            
            enriched_pois.append(enriched_poi)
        
        # Log statistiques enrichissement
        with_links = sum(1 for poi in enriched_pois if poi['maps_links']['has_links'])
        if with_links > 0:
            logger.debug(f"📍 {with_links}/{len(enriched_pois)} POIs enrichis avec liens cartographiques")
        
        return enriched_pois

    def health_check(self) -> Dict[str, Any]:
        """Vérifie la santé de la connexion Supabase"""
        try:
            # Test de connexion avec requête simple
            response = self.client.table('territories').select('count', count='exact').execute()
            territories_count = response.count
            
            # Test sur les POIs actifs
            pois_response = self.client.table('pois').select('count', count='exact').eq('active', True).execute()
            pois_count = pois_response.count
            
            return {
                'status': 'healthy',
                'message': 'Connexion Supabase opérationnelle',
                'territories_count': territories_count,
                'pois_count': pois_count,
                'mock_mode': False,
                'real_data': True
            }
            
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            return {
                'status': 'error',
                'message': f'Erreur Supabase: {str(e)}',
                'mock_mode': False,
                'real_data': False
            }