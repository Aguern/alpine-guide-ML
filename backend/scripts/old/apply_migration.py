#!/usr/bin/env python3
"""
Script d'application de migration Supabase
Applique le fichier add_maps_urls.sql
"""
import os
import sys
import logging
from supabase import create_client
from dotenv import load_dotenv

# Charger le .env
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def apply_migration():
    """Applique la migration des URLs cartographiques"""
    
    # Connexion Supabase avec service key (requis pour DDL)
    url = os.getenv('SUPABASE_URL')
    service_key = os.getenv('SUPABASE_SERVICE_KEY')
    
    if not url or not service_key:
        logger.error("❌ SUPABASE_URL ou SUPABASE_SERVICE_KEY manquantes")
        return False
    
    try:
        client = create_client(url, service_key)
        logger.info("✅ Connexion Supabase établie")
        
        # Lire le fichier de migration
        migration_file = os.path.join(
            project_root, 
            'database', 
            'migrations', 
            'add_maps_urls.sql'
        )
        
        if not os.path.exists(migration_file):
            logger.error(f"❌ Fichier migration introuvable: {migration_file}")
            return False
        
        with open(migration_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        logger.info(f"📄 Migration chargée depuis {migration_file}")
        
        # Exécuter la migration via RPC (plus sûr pour DDL)
        # Note: Supabase Python client ne supporte pas directement les DDL
        # On utilise une approche alternative avec la REST API
        
        # Vérifier d'abord les colonnes existantes
        response = client.table('pois').select('*').limit(1).execute()
        
        if response.data:
            existing_columns = list(response.data[0].keys())
            logger.info(f"📋 Colonnes actuelles: {len(existing_columns)} détectées")
            
            if 'gmaps_url' in existing_columns:
                logger.warning("⚠️ Colonne gmaps_url déjà présente")
            else:
                logger.info("🆕 Colonne gmaps_url à ajouter")
                
            if 'apple_url' in existing_columns:
                logger.warning("⚠️ Colonne apple_url déjà présente")
            else:
                logger.info("🆕 Colonne apple_url à ajouter")
        
        # Pour l'instant, on valide que la structure est prête
        # L'application DDL nécessite un accès direct PostgreSQL ou Dashboard Supabase
        logger.info("✅ Migration validée - Application manuelle requise")
        logger.info("🔧 Action: Exécuter add_maps_urls.sql dans le Dashboard Supabase")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur migration: {e}")
        return False

def verify_migration():
    """Vérifie que la migration a été appliquée"""
    url = os.getenv('SUPABASE_URL')
    service_key = os.getenv('SUPABASE_SERVICE_KEY')
    
    try:
        client = create_client(url, service_key)
        response = client.table('pois').select('*').limit(1).execute()
        
        if response.data:
            columns = list(response.data[0].keys())
            
            has_gmaps = 'gmaps_url' in columns
            has_apple = 'apple_url' in columns
            
            logger.info(f"🔍 Vérification migration:")
            logger.info(f"   • gmaps_url: {'✅' if has_gmaps else '❌'}")
            logger.info(f"   • apple_url: {'✅' if has_apple else '❌'}")
            
            if has_gmaps and has_apple:
                logger.info("✅ Migration appliquée avec succès")
                return True
            else:
                logger.warning("⚠️ Migration incomplète")
                return False
        else:
            logger.warning("⚠️ Aucune donnée pour vérification")
            return False
            
    except Exception as e:
        logger.error(f"❌ Erreur vérification: {e}")
        return False

def main():
    """Point d'entrée principal"""
    logger.info("🚀 === APPLICATION MIGRATION MAPS URLs ===")
    
    # Étape 1: Valider et préparer la migration
    if apply_migration():
        logger.info("📋 Migration préparée avec succès")
        
        # Étape 2: Instructions pour application manuelle
        logger.info("\n📖 === INSTRUCTIONS D'APPLICATION ===")
        logger.info("1. Ouvrir le Dashboard Supabase")
        logger.info("2. Aller dans SQL Editor")
        logger.info("3. Copier/coller le contenu de database/migrations/add_maps_urls.sql")
        logger.info("4. Exécuter la migration")
        logger.info("5. Relancer ce script avec --verify")
        
        # Si argument --verify, vérifier
        if len(sys.argv) > 1 and sys.argv[1] == '--verify':
            logger.info("\n🔍 === VÉRIFICATION POST-MIGRATION ===")
            success = verify_migration()
            sys.exit(0 if success else 1)
        
        sys.exit(0)
    else:
        logger.error("❌ Échec préparation migration")
        sys.exit(1)

if __name__ == "__main__":
    main()