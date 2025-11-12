#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de génération des embeddings pour les POIs
Usage: python generate_embeddings.py [territoire]
"""
import sys
import os
import asyncio
import argparse
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.embeddings_service import EmbeddingsService
from app.config import settings
import logging
from datetime import datetime

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Fonction principale"""
    parser = argparse.ArgumentParser(description='Génération des embeddings pour les POIs')
    parser.add_argument(
        'territory',
        nargs='?',
        default='annecy',
        help='Slug du territoire à traiter (défaut: annecy)'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Traiter tous les territoires'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Régénérer même les embeddings existants'
    )
    parser.add_argument(
        '--stats-only',
        action='store_true',
        help='Afficher seulement les statistiques'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Mode verbeux'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Vérification de la configuration
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        logger.error("Configuration Supabase manquante. Vérifiez le fichier .env")
        sys.exit(1)
    
    logger.info("=== Générateur d'Embeddings AlpineGuide ===")
    logger.info(f"Démarré à: {datetime.now()}")
    
    try:
        # Initialiser le service
        embeddings_service = EmbeddingsService()
        
        # Mode statistiques seulement
        if args.stats_only:
            territory = None if args.all else args.territory
            stats = embeddings_service.get_stats(territory)
            
            logger.info(f"\n=Ê Statistiques des embeddings:")
            logger.info(f"   Total POIs: {stats['total_pois']}")
            logger.info(f"   Avec embeddings: {stats['with_embeddings']}")
            logger.info(f"   Sans embeddings: {stats['without_embeddings']}")
            logger.info(f"   Couverture: {stats['coverage_percent']}%")
            return
        
        # Générer les embeddings
        if args.all:
            logger.info("=€ Génération pour tous les territoires")
            territory_slug = None
        else:
            logger.info(f"=€ Génération pour le territoire: {args.territory}")
            territory_slug = args.territory
        
        if args.force:
            logger.warning("   Mode force activé - régénération des embeddings existants")
        
        # Afficher les stats avant
        stats_before = embeddings_service.get_stats(territory_slug)
        logger.info(f"\n=Ê État avant génération:")
        logger.info(f"   POIs sans embeddings: {stats_before['without_embeddings']}")
        logger.info(f"   Couverture actuelle: {stats_before['coverage_percent']}%")
        
        # Lancer la génération
        results = await embeddings_service.generate_all_embeddings(territory_slug)
        
        # Afficher les résultats
        logger.info(f"\n Génération terminée!")
        logger.info(f"   POIs traités: {results['processed']}")
        logger.info(f"   Succès: {results['success']}")
        logger.info(f"   Erreurs: {results['errors']}")
        
        if results['processed'] > 0:
            success_rate = (results['success'] / results['processed']) * 100
            logger.info(f"   Taux de succès: {success_rate:.1f}%")
        
        # Afficher les stats après
        stats_after = embeddings_service.get_stats(territory_slug)
        logger.info(f"\n=Ê État après génération:")
        logger.info(f"   Couverture finale: {stats_after['coverage_percent']}%")
        logger.info(f"   Amélioration: +{stats_after['coverage_percent'] - stats_before['coverage_percent']:.1f}%")
        
        # Test de recherche si des embeddings ont été générés
        if results['success'] > 0:
            logger.info(f"\n= Test de recherche sémantique...")
            test_results = await embeddings_service.search_semantic(
                query="restaurant traditionnel savoyard",
                territory_slug=territory_slug or "annecy",
                limit=3
            )
            
            if test_results:
                logger.info(f"    Trouvé {len(test_results)} résultats pertinents:")
                for result in test_results:
                    similarity = result.get('similarity', 0)
                    logger.info(f"     - {result['name']} ({result['type']}) - Similarité: {similarity:.3f}")
            else:
                logger.info("     Aucun résultat trouvé pour le test")
        
    except KeyboardInterrupt:
        logger.info("Génération interrompue par l'utilisateur")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Erreur lors de la génération: {e}")
        sys.exit(1)
    
    logger.info(f"\nTerminé à: {datetime.now()}")


if __name__ == "__main__":
    asyncio.run(main())