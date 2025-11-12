# -*- coding: utf-8 -*-
"""
Collecteur de donnees DATAtourisme v2 - Format JSON
"""
import requests
import json
import zipfile
import io
from typing import List, Dict, Optional
from datetime import datetime
import logging
from app.config import settings
from supabase import Client, create_client

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DATAtourismeCollector:
    """Collecteur pour recuperer et traiter les donnees DATAtourisme en JSON"""
    
    def __init__(self):
        self.supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        
        # URL DataTourisme avec votre clé API
        self.api_key = "f8e5080b-c925-470e-bca0-a78dd03db70b"
        self.base_url = f"https://diffuseur.datatourisme.fr/webservice/725ce38e229d91142d411a21d7b4db87/{self.api_key}"
        
        # Mapping des types DATAtourisme vers nos types
        self.type_mapping = {
            'HotelTrade': 'accommodation',
            'Accommodation': 'accommodation',
            'FoodEstablishment': 'restaurant',
            'Restaurant': 'restaurant',
            'PointOfInterest': 'activity',
            'PlaceOfInterest': 'culture',
            'CulturalSite': 'culture',
            'NaturalHeritage': 'nature',
            'SportsAndLeisurePlace': 'activity',
            'Store': 'shop',
            'LocalTouristOffice': 'service'
        }

    def fetch_data(self) -> Optional[List[Dict]]:
        """Recupere les donnees depuis le flux DATAtourisme (format ZIP)"""
        try:
            logger.info("Recuperation du flux DATAtourisme...")
            
            # Le flux est un ZIP contenant des fichiers JSON
            response = requests.get(self.base_url, timeout=60)
            response.raise_for_status()
            
            # Verifier le content-type
            content_type = response.headers.get('content-type', '')
            logger.info(f"Content-Type recu: {content_type}")
            
            if 'zip' not in content_type:
                logger.warning(f"Format inattendu: {content_type}, tentative de traitement comme ZIP")
            
            # Extraire les donnees du ZIP
            all_data = []
            
            try:
                with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                    logger.info(f"Nombre de fichiers dans le ZIP: {len(zip_file.namelist())}")
                    
                    # Parcourir tous les fichiers JSON dans le ZIP
                    for filename in zip_file.namelist():
                        if filename.endswith('.json'):
                            try:
                                with zip_file.open(filename) as json_file:
                                    data = json.load(json_file)
                                    # Chaque fichier contient un objet POI
                                    all_data.append(data)
                            except json.JSONDecodeError as e:
                                logger.debug(f"Erreur decodage JSON pour {filename}: {e}")
                                continue
                            except Exception as e:
                                logger.debug(f"Erreur lecture {filename}: {e}")
                                continue
                    
                    logger.info(f"Nombre total d'objets JSON extraits: {len(all_data)}")
                    
            except zipfile.BadZipFile:
                logger.error("Le fichier recu n'est pas un ZIP valide")
                return None
                
            return all_data
            
        except requests.RequestException as e:
            logger.error(f"Erreur lors de la recuperation des donnees: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Code statut: {e.response.status_code}")
            return None

    def parse_json_data(self, json_data_list: List[Dict]) -> List[Dict]:
        """Parse les donnees JSON de DATAtourisme"""
        pois = []
        
        if not json_data_list:
            return pois
            
        for item in json_data_list:
            try:
                # Ignorer si ce n'est pas un dictionnaire
                if not isinstance(item, dict):
                    continue
                    
                # Extraction des coordonnees
                located_at = item.get('isLocatedAt', [])
                if not located_at or len(located_at) == 0:
                    continue
                    
                geo = located_at[0].get('schema:geo', {})
                if not geo:
                    continue
                    
                lat = float(geo.get('schema:latitude', 0))
                lon = float(geo.get('schema:longitude', 0))
                
                if not lat or not lon:
                    continue
                
                # Extraction des informations principales
                name = self._get_localized_value(item.get('rdfs:label', {}))
                if not name:
                    continue
                    
                description = self._get_localized_value(item.get('rdfs:comment', {}))
                
                # Adresse
                address_data = located_at[0].get('schema:address', [])
                if address_data and len(address_data) > 0:
                    address_info = address_data[0]
                    street_address = address_info.get('schema:streetAddress', [])
                    address = street_address[0] if street_address else ''
                    city = address_info.get('schema:addressLocality', '')
                    postal_code = address_info.get('schema:postalCode', '')
                else:
                    address = ''
                    city = ''
                    postal_code = ''
                
                # Contact
                contact_data = item.get('hasContact', [])
                if contact_data and len(contact_data) > 0:
                    contact_info = contact_data[0]
                    phone_list = contact_info.get('schema:telephone', [])
                    phone = phone_list[0] if phone_list else ''
                    email_list = contact_info.get('schema:email', [])
                    email = email_list[0] if email_list else ''
                    website_list = contact_info.get('foaf:homepage', [])
                    website = website_list[0] if website_list else ''
                else:
                    phone = ''
                    email = ''
                    website = ''
                
                # Type
                poi_types = item.get('@type', [])
                poi_type = self._determine_type(poi_types)
                
                poi = {
                    'name': name,
                    'description': description[:500] if description else '',
                    'type': poi_type,
                    'location': f"POINT({lon} {lat})",
                    'address': {
                        'street': address,
                        'city': city,
                        'postal_code': postal_code,
                        'country': 'France'
                    },
                    'contact': {
                        'phone': phone if phone else None,
                        'email': email if email else None,
                        'website': website if website else None
                    },
                    'tags': [t for t in poi_types if t != 'schema:Thing'],
                    'datatourisme_id': item.get('@id', ''),
                    'metadata': {
                        'source': 'datatourisme',
                        'imported_at': datetime.now().isoformat()
                    }
                }
                
                # Informations supplementaires si disponibles
                if item.get('hasTheme'):
                    poi['tags'].extend([theme.get('@id', '').split('/')[-1] for theme in item.get('hasTheme', [])])
                
                pois.append(poi)
                
            except (ValueError, KeyError, TypeError) as e:
                logger.debug(f"Erreur parsing item: {e}")
                continue
                
        return pois

    def _get_localized_value(self, data: Dict, lang: str = 'fr') -> str:
        """Extrait la valeur localisee d'un champ multilingue"""
        if isinstance(data, str):
            return data
        if isinstance(data, dict):
            # Les valeurs sont souvent dans des listes
            val = data.get(lang, data.get('en', []))
            if isinstance(val, list):
                return val[0] if val else ''
            return val if val else ''
        return ''

    def _determine_type(self, types: List[str]) -> str:
        """Determine le type de POI base sur les types DATAtourisme"""
        for dt_type in types:
            type_name = dt_type.split(':')[-1] if ':' in dt_type else dt_type
            if type_name in self.type_mapping:
                return self.type_mapping[type_name]
        return 'activity'  # Type par defaut

    def save_pois_to_db(self, pois: List[Dict], territory_id: str) -> int:
        """Sauvegarde les POIs en base de donnees"""
        saved_count = 0
        
        for poi in pois:
            try:
                # Ajouter l'ID du territoire
                poi['territory_id'] = territory_id
                
                # Verifier si le POI existe deja
                existing = self.supabase.table('pois').select('id').eq('datatourisme_id', poi['datatourisme_id']).execute()
                
                if existing.data:
                    # Mise a jour
                    self.supabase.table('pois').update(poi).eq('datatourisme_id', poi['datatourisme_id']).execute()
                    logger.debug(f"POI mis a jour: {poi['name']}")
                else:
                    # Insertion
                    self.supabase.table('pois').insert(poi).execute()
                    logger.debug(f"POI cree: {poi['name']}")
                    
                saved_count += 1
                
            except Exception as e:
                logger.error(f"Erreur sauvegarde POI {poi.get('name', 'Unknown')}: {e}")
                continue
                
        return saved_count

    def collect_for_territory(self, territory_slug: str) -> Dict[str, int]:
        """Collecte les POIs pour un territoire donne"""
        logger.info(f"Debut de la collecte pour le territoire: {territory_slug}")
        
        # Recuperer les infos du territoire
        try:
            territory_response = self.supabase.table('territories').select('*').eq('slug', territory_slug).single().execute()
            territory = territory_response.data
            
            if not territory:
                raise ValueError(f"Territoire {territory_slug} non trouve")
                
        except Exception as e:
            logger.error(f"Erreur recuperation territoire: {e}")
            return {'error': str(e)}
        
        results = {
            'territory': territory_slug,
            'total': 0
        }
        
        # Recuperer le flux complet (ZIP contenant des JSONs)
        json_data_list = self.fetch_data()
        if not json_data_list:
            logger.error("Impossible de recuperer le flux DATAtourisme")
            return results
            
        # Parser toutes les donnees
        all_pois = self.parse_json_data(json_data_list)
        total_pois = len(all_pois)
        
        # Filtrer par territoire (bbox)
        filtered_pois = []
        bounds = territory.get('bounds', {})
        
        for poi in all_pois:
            # Extraire lat/lon du format POINT
            if 'location' in poi:
                import re
                match = re.match(r'POINT\(([^ ]+) ([^ ]+)\)', poi['location'])
                if match:
                    lon, lat = float(match.group(1)), float(match.group(2))
                    # Verifier si dans les limites du territoire
                    if (bounds.get('south', -90) <= lat <= bounds.get('north', 90) and
                        bounds.get('west', -180) <= lon <= bounds.get('east', 180)):
                        filtered_pois.append(poi)
        
        logger.info(f"Filtrage: {len(filtered_pois)} POIs dans le territoire sur {total_pois} au total")
        all_pois = filtered_pois
            
        # Sauvegarder en base
        if all_pois:
            saved_count = self.save_pois_to_db(all_pois, territory['id'])
            results['total'] = saved_count
            logger.info(f"Collecte terminee: {saved_count} POIs sauvegardes")
        else:
            logger.info("Aucun POI trouve pour ce territoire")
            
        return results