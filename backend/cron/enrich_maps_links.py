#!/usr/bin/env python3
"""
Service d'enrichissement automatique des liens cartographiques
Génère les URLs Google Maps et Apple Plans pour tous les POIs
"""
import os
import sys
import json
import logging
import asyncio
import struct
from urllib.parse import quote_plus
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from dotenv import load_dotenv

# Charger variables d'environnement
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)

# Ajouter le path backend pour les imports
backend_path = os.path.join(project_root, 'backend')
sys.path.append(backend_path)

from supabase import create_client, Client

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class POIRecord:
    """Structure d'un POI pour traitement"""
    id: str
    name: str
    geolocation: Optional[Dict[str, float]]
    address: Optional[Dict[str, str]]
    territory_id: str
    current_gmaps_url: Optional[str] = None
    current_apple_url: Optional[str] = None

@dataclass
class EnrichmentResult:
    """Résultat d'enrichissement d'un POI"""
    poi_id: str
    gmaps_url: str
    apple_url: str
    source: str  # 'coordinates' ou 'address'
    success: bool = True
    error: Optional[str] = None

class MapsLinksEnricher:
    """Service d'enrichissement des liens cartographiques"""
    
    def __init__(self, dry_run: bool = False):
        """
        Initialise le service d'enrichissement
        
        Args:
            dry_run: Si True, n'écrit pas en base (mode test)
        """
        self.dry_run = dry_run
        self.stats = {
            'total_processed': 0,
            'success_count': 0,
            'error_count': 0,
            'skipped_count': 0,
            'coordinates_used': 0,
            'address_fallback': 0
        }
        
        # Connexion Supabase
        self._init_supabase()
        
        logger.info(f"🚀 MapsLinksEnricher initialisé (dry_run={dry_run})")
    
    def _decode_postgis_geometry(self, geom_hex: str) -> Optional[Tuple[float, float]]:
        """
        Décode une géométrie PostGIS POINT depuis son format hexadécimal
        
        Args:
            geom_hex: Géométrie PostGIS au format hex (ex: "0101000020E6100000...")
            
        Returns:
            Tuple (longitude, latitude) ou None si erreur
        """
        try:
            if not geom_hex or len(geom_hex) < 46:  # Taille minimum pour un POINT
                return None
            
            # Convertir hex en bytes
            geom_bytes = bytes.fromhex(geom_hex)
            
            # Format WKB PostGIS : 
            # - Endianness (1 byte)
            # - Geometry type (4 bytes) 
            # - SRID (4 bytes) pour PostGIS
            # - X coordinate (8 bytes - longitude)
            # - Y coordinate (8 bytes - latitude)
            
            if len(geom_bytes) < 25:  # 1+4+4+8+8
                return None
            
            # Lire l'endianness
            endian = geom_bytes[0]
            fmt = '<' if endian == 1 else '>'  # Little ou Big endian
            
            # Lire type géométrie (doit être 1 pour POINT)
            geom_type = struct.unpack(fmt + 'I', geom_bytes[1:5])[0]
            if geom_type != 0x20000001:  # POINT avec SRID
                return None
            
            # Lire SRID (on s'attend à 4326 pour WGS84)
            srid = struct.unpack(fmt + 'I', geom_bytes[5:9])[0]
            
            # Lire coordonnées (longitude, latitude)
            longitude = struct.unpack(fmt + 'd', geom_bytes[9:17])[0]
            latitude = struct.unpack(fmt + 'd', geom_bytes[17:25])[0]
            
            # Validation des coordonnées
            if -180 <= longitude <= 180 and -90 <= latitude <= 90:
                return (longitude, latitude)
            else:
                logger.warning(f"Coordonnées invalides: lng={longitude}, lat={latitude}")
                return None
                
        except Exception as e:
            logger.debug(f"Erreur décodage géométrie PostGIS: {e}")
            return None
    
    def _extract_coordinates_from_poi(self, poi: POIRecord) -> Optional[Tuple[float, float]]:
        """
        Extrait les coordonnées (lng, lat) d'un POI selon son format de géolocalisation
        
        Returns:
            Tuple (longitude, latitude) ou None
        """
        if not poi.geolocation:
            return None
        
        # Cas 1: Géolocalisation est un dict avec lat/lng
        if isinstance(poi.geolocation, dict):
            lat = poi.geolocation.get('lat') or poi.geolocation.get('latitude')
            lng = poi.geolocation.get('lng') or poi.geolocation.get('longitude')
            
            if lat is not None and lng is not None:
                try:
                    return (float(lng), float(lat))
                except (ValueError, TypeError):
                    pass
        
        # Cas 2: Géolocalisation est une string hexadécimale PostGIS
        if isinstance(poi.geolocation, str) and len(poi.geolocation) > 20:
            coords = self._decode_postgis_geometry(poi.geolocation)
            if coords:
                return coords
        
        logger.debug(f"Format géolocalisation non reconnu: {type(poi.geolocation)}")
        return None
    
    def _init_supabase(self):
        """Initialise la connexion Supabase"""
        url = os.getenv('SUPABASE_URL')
        service_key = os.getenv('SUPABASE_SERVICE_KEY')
        
        if not url or not service_key:
            raise ValueError("SUPABASE_URL ou SUPABASE_SERVICE_KEY manquantes")
        
        try:
            self.client: Client = create_client(url, service_key)
            logger.info("✅ Connexion Supabase établie")
        except Exception as e:
            logger.error(f"❌ Erreur connexion Supabase: {e}")
            raise
    
    def generate_google_maps_url(self, poi: POIRecord) -> str:
        """
        Génère l'URL Google Maps pour un POI
        
        Format avec nom + ville (préféré pour fiche établissement):
        https://www.google.com/maps/search/?api=1&query=Restaurant+Le+Contresens+Annecy
        
        Format avec coordonnées (fallback):
        https://www.google.com/maps/search/?api=1&query=45.9237,6.8694
        """
        try:
            # Priorité 1: Nom + ville pour obtenir la fiche d'établissement
            # (au lieu des coordonnées qui n'affichent qu'un point)
            query_parts = [poi.name]
            
            if poi.address:
                city = poi.address.get('city') or poi.address.get('commune')
                if city:
                    query_parts.append(city)
            
            # Si on a au moins le nom + ville, utiliser cette combinaison  
            if len(query_parts) >= 2 or (len(query_parts) == 1 and len(poi.name) > 3):
                query = ' '.join(query_parts)
                encoded_query = quote_plus(query)
                return f"https://www.google.com/maps/search/?api=1&query={encoded_query}"
            
            # Priorité 2: Coordonnées géographiques (fallback si pas de nom/ville)
            coordinates = self._extract_coordinates_from_poi(poi)
            if coordinates:
                lng, lat = coordinates
                return f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
            
            # Dernier recours: juste le nom
            encoded_name = quote_plus(poi.name)
            return f"https://www.google.com/maps/search/?api=1&query={encoded_name}"
            
        except Exception as e:
            logger.error(f"Erreur génération Google Maps URL pour POI {poi.id}: {e}")
            # URL de fallback basique
            encoded_name = quote_plus(poi.name)
            return f"https://www.google.com/maps/search/?api=1&query={encoded_name}"
    
    def generate_apple_maps_url(self, poi: POIRecord) -> str:
        """
        Génère l'URL Apple Maps pour un POI
        
        Format avec coordonnées (préféré):
        https://maps.apple.com/?q=Restaurant&ll=45.9237,6.8694
        
        Format avec nom (fallback):
        https://maps.apple.com/?q=Restaurant+La+Maison+Annecy
        """
        try:
            # Priorité 1: Coordonnées + nom
            coordinates = self._extract_coordinates_from_poi(poi)
            if coordinates:
                lng, lat = coordinates
                encoded_name = quote_plus(poi.name)
                return f"https://maps.apple.com/?q={encoded_name}&ll={lat},{lng}"
            
            # Priorité 2: Nom + ville
            query_parts = [poi.name]
            
            if poi.address:
                city = poi.address.get('city') or poi.address.get('commune')
                if city:
                    query_parts.append(city)
            
            query = ' '.join(query_parts)
            encoded_query = quote_plus(query)
            
            return f"https://maps.apple.com/?q={encoded_query}"
            
        except Exception as e:
            logger.error(f"Erreur génération Apple Maps URL pour POI {poi.id}: {e}")
            encoded_name = quote_plus(poi.name)
            return f"https://maps.apple.com/?q={encoded_name}"
    
    def should_update_poi(self, poi: POIRecord, force_refresh: bool = False) -> bool:
        """
        Détermine si un POI doit être mis à jour
        
        Args:
            poi: POI à vérifier
            force_refresh: Force la mise à jour même si URLs existantes
        """
        if force_refresh:
            return True
        
        # Mettre à jour si URLs manquantes
        if not poi.current_gmaps_url or not poi.current_apple_url:
            return True
        
        # Mettre à jour si URLs invalides/obsolètes
        if not poi.current_gmaps_url.startswith('https://'):
            return True
        
        if not poi.current_apple_url.startswith('https://'):
            return True
        
        return False
    
    async def fetch_pois_to_process(self, 
                                  limit: int = 100, 
                                  territory_filter: Optional[str] = None,
                                  force_refresh: bool = False) -> List[POIRecord]:
        """
        Récupère les POIs à traiter depuis Supabase
        
        Args:
            limit: Nombre maximum de POIs à traiter
            territory_filter: Filtrer par territoire (slug)
            force_refresh: Traiter tous les POIs même avec URLs existantes
        """
        try:
            logger.info(f"🔍 Récupération POIs (limit={limit}, territory={territory_filter})")
            
            # Vérifier d'abord si les colonnes maps existent
            columns_exist = await self._check_maps_columns_exist()
            
            # Construction requête adaptée selon l'état des colonnes
            if columns_exist:
                select_clause = 'id, name, geolocation, address, territory_id, gmaps_url, apple_url'
            else:
                select_clause = 'id, name, geolocation, address, territory_id'
                logger.warning("⚠️ Colonnes gmaps_url/apple_url non détectées - traitement de tous les POIs")
            
            query = self.client.table('pois').select(select_clause).eq('active', True)
            
            if territory_filter:
                query = query.eq('territory_id', territory_filter)
            
            if not force_refresh and columns_exist:
                # Prioriser les POIs sans URLs seulement si colonnes existent
                query = query.or_('gmaps_url.is.null,apple_url.is.null')
            
            query = query.limit(limit)
            
            response = query.execute()
            
            if not response.data:
                logger.info("ℹ️ Aucun POI à traiter")
                return []
            
            # Convertir en POIRecord
            pois = []
            for row in response.data:
                poi = POIRecord(
                    id=row['id'],
                    name=row['name'],
                    geolocation=row.get('geolocation'),
                    address=row.get('address'),
                    territory_id=row['territory_id'],
                    current_gmaps_url=row.get('gmaps_url') if columns_exist else None,
                    current_apple_url=row.get('apple_url') if columns_exist else None
                )
                
                if self.should_update_poi(poi, force_refresh):
                    pois.append(poi)
            
            logger.info(f"✅ {len(pois)} POIs sélectionnés pour traitement")
            return pois
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération POIs: {e}")
            return []
    
    async def _check_maps_columns_exist(self) -> bool:
        """Vérifie si les colonnes gmaps_url/apple_url existent"""
        try:
            # Test simple : essayer de sélectionner les colonnes
            response = self.client.table('pois').select('gmaps_url, apple_url').limit(1).execute()
            return True
        except Exception as e:
            if 'does not exist' in str(e):
                return False
            else:
                # Autre erreur, on assume que les colonnes existent
                logger.warning(f"⚠️ Erreur vérification colonnes (assumées existantes): {e}")
                return True
    
    def enrich_single_poi(self, poi: POIRecord) -> EnrichmentResult:
        """Enrichit un seul POI avec ses URLs cartographiques"""
        try:
            logger.debug(f"🔄 Traitement POI {poi.id}: {poi.name}")
            
            # Générer les URLs
            gmaps_url = self.generate_google_maps_url(poi)
            apple_url = self.generate_apple_maps_url(poi)
            
            # Déterminer la source utilisée
            coordinates = self._extract_coordinates_from_poi(poi)
            source = 'coordinates' if coordinates else 'address'
            
            result = EnrichmentResult(
                poi_id=poi.id,
                gmaps_url=gmaps_url,
                apple_url=apple_url,
                source=source,
                success=True
            )
            
            # Mettre à jour statistiques
            self.stats['total_processed'] += 1
            self.stats['success_count'] += 1
            
            if source == 'coordinates':
                self.stats['coordinates_used'] += 1
            else:
                self.stats['address_fallback'] += 1
            
            logger.debug(f"✅ POI {poi.id} enrichi (source: {source})")
            return result
            
        except Exception as e:
            logger.error(f"❌ Erreur enrichissement POI {poi.id}: {e}")
            
            self.stats['total_processed'] += 1
            self.stats['error_count'] += 1
            
            return EnrichmentResult(
                poi_id=poi.id,
                gmaps_url="",
                apple_url="",
                source="error",
                success=False,
                error=str(e)
            )
    
    async def update_poi_in_database(self, result: EnrichmentResult) -> bool:
        """Met à jour un POI dans la base de données"""
        if self.dry_run:
            logger.info(f"[DRY-RUN] Mise à jour POI {result.poi_id}")
            return True
        
        if not result.success:
            logger.warning(f"⚠️ Skip mise à jour POI {result.poi_id} (erreur)")
            return False
        
        try:
            update_data = {
                'gmaps_url': result.gmaps_url,
                'apple_url': result.apple_url,
                'updated_at': datetime.utcnow().isoformat()
            }
            
            response = self.client.table('pois').update(update_data).eq('id', result.poi_id).execute()
            
            if response.data:
                logger.debug(f"✅ POI {result.poi_id} mis à jour en base")
                return True
            else:
                logger.error(f"❌ Échec mise à jour POI {result.poi_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour POI {result.poi_id}: {e}")
            return False
    
    async def enrich_pois_batch(self, 
                               limit: int = 100,
                               territory_filter: Optional[str] = None,
                               force_refresh: bool = False) -> Dict[str, Any]:
        """
        Enrichit un lot de POIs avec les URLs cartographiques
        
        Returns:
            Rapport d'exécution avec statistiques
        """
        start_time = datetime.now()
        logger.info(f"🚀 === DÉBUT ENRICHISSEMENT BATCH ===")
        logger.info(f"Mode: {'DRY-RUN' if self.dry_run else 'PRODUCTION'}")
        
        # Étape 1: Récupérer les POIs
        pois = await self.fetch_pois_to_process(limit, territory_filter, force_refresh)
        
        if not pois:
            logger.info("ℹ️ Aucun POI à traiter")
            return self._generate_report(start_time)
        
        # Étape 2: Enrichir chaque POI
        enrichment_results = []
        
        for poi in pois:
            result = self.enrich_single_poi(poi)
            enrichment_results.append(result)
            
            # Mise à jour en base
            if result.success:
                await self.update_poi_in_database(result)
        
        # Étape 3: Rapport final
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info(f"✅ === ENRICHISSEMENT TERMINÉ ===")
        logger.info(f"Durée: {duration:.2f}s")
        logger.info(f"POIs traités: {self.stats['total_processed']}")
        logger.info(f"Succès: {self.stats['success_count']}")
        logger.info(f"Erreurs: {self.stats['error_count']}")
        
        return self._generate_report(start_time, enrichment_results)
    
    def _generate_report(self, 
                        start_time: datetime,
                        results: List[EnrichmentResult] = None) -> Dict[str, Any]:
        """Génère un rapport d'exécution"""
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        report = {
            'execution': {
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'duration_seconds': duration,
                'dry_run': self.dry_run
            },
            'statistics': self.stats.copy(),
            'success': self.stats['error_count'] == 0
        }
        
        if results:
            report['details'] = {
                'total_urls_generated': len([r for r in results if r.success]) * 2,
                'coordinates_based': self.stats['coordinates_used'],
                'address_based': self.stats['address_fallback'],
                'error_rate': (self.stats['error_count'] / max(1, self.stats['total_processed'])) * 100
            }
        
        return report

# === INTERFACE CLI ===

def main():
    """Point d'entrée principal CLI"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Enrichissement URLs cartographiques POIs')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Mode test (pas de modification base)')
    parser.add_argument('--limit', type=int, default=100,
                       help='Nombre max de POIs à traiter (défaut: 100)')
    parser.add_argument('--territory', type=str,
                       help='Filtrer par territoire (slug)')
    parser.add_argument('--force-refresh', action='store_true',
                       help='Forcer la mise à jour même si URLs existantes')
    parser.add_argument('--output', type=str,
                       help='Fichier de rapport JSON (optionnel)')
    
    args = parser.parse_args()
    
    # Créer et exécuter le service
    enricher = MapsLinksEnricher(dry_run=args.dry_run)
    
    async def run():
        report = await enricher.enrich_pois_batch(
            limit=args.limit,
            territory_filter=args.territory,
            force_refresh=args.force_refresh
        )
        
        # Sauvegarder rapport si demandé
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info(f"📄 Rapport sauvegardé: {args.output}")
        
        # Code de sortie
        return 0 if report['success'] else 1
    
    # Exécuter
    try:
        exit_code = asyncio.run(run())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("⚠️ Interruption utilisateur")
        sys.exit(130)
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()