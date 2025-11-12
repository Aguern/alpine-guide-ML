#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script d'import des données DataTourisme pour un territoire
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.collectors.datatourisme_v2 import DATAtourismeCollector
import argparse
import logging
from datetime import datetime

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Fonction principale"""
    parser = argparse.ArgumentParser(description="Import des données DataTourisme pour un territoire")
    parser.add_argument('territory', help="Slug du territoire (ex: annecy)")
    parser.add_argument('--dry-run', action='store_true', help="Mode test sans sauvegarde en base")
    
    args = parser.parse_args()
    
    logger.info(f"=== Import DataTourisme pour {args.territory} ===")
    logger.info(f"Démarré à: {datetime.now()}")
    
    if args.dry_run:
        logger.info("MODE DRY-RUN: Les données ne seront pas sauvegardées en base")
    
    # Créer le collecteur
    collector = DATAtourismeCollector()
    
    # Si mode dry-run, on teste juste la récupération et le parsing
    if args.dry_run:
        logger.info("Récupération des données...")
        data = collector.fetch_data()
        
        if data:
            logger.info(f"✓ {len(data)} objets récupérés depuis DataTourisme")
            
            # Parser les données
            all_pois = collector.parse_json_data(data)
            logger.info(f"✓ {len(all_pois)} POIs parsés avec succès")
            
            # Afficher quelques statistiques
            types_count = {}
            cities = {}
            
            for poi in all_pois:
                # Types
                poi_type = poi['type']
                types_count[poi_type] = types_count.get(poi_type, 0) + 1
                
                # Villes
                city = poi['address']['city']
                if city:
                    cities[city] = cities.get(city, 0) + 1
            
            logger.info("\nRépartition par type:")
            for poi_type, count in sorted(types_count.items(), key=lambda x: x[1], reverse=True)[:10]:
                logger.info(f"  {poi_type}: {count}")
                
            logger.info("\nTop 10 villes:")
            for city, count in sorted(cities.items(), key=lambda x: x[1], reverse=True)[:10]:
                logger.info(f"  {city}: {count}")
                
            # Simuler le filtrage pour le territoire
            logger.info(f"\nSimulation du filtrage pour {args.territory}...")
            # Exemple pour Annecy (à adapter selon les bounds du territoire)
            if args.territory == 'annecy':
                filtered = []
                for poi in all_pois:
                    import re
                    match = re.match(r'POINT\(([^ ]+) ([^ ]+)\)', poi['location'])
                    if match:
                        lon, lat = float(match.group(1)), float(match.group(2))
                        # Zone approximative d'Annecy
                        if 45.7 <= lat <= 46.1 and 5.9 <= lon <= 6.3:
                            filtered.append(poi)
                logger.info(f"→ {len(filtered)} POIs seraient importés pour {args.territory}")
                
        else:
            logger.error("Échec de récupération des données")
            return 1
            
    else:
        # Mode réel: import en base
        try:
            results = collector.collect_for_territory(args.territory)
            
            if 'error' in results:
                logger.error(f"Erreur: {results['error']}")
                return 1
            else:
                logger.info(f"\n✓ Import terminé avec succès!")
                logger.info(f"  Total POIs importés: {results['total']}")
                
        except Exception as e:
            logger.error(f"Erreur lors de l'import: {e}")
            return 1
    
    logger.info(f"\nTerminé à: {datetime.now()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())