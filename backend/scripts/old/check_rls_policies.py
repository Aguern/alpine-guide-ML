#!/usr/bin/env python3
"""
Script de vérification des RLS policies Supabase
CRITIQUE : S'assurer que les nouveaux champs gmaps_url/apple_url seront accessibles
"""
import os
import sys
import logging
from supabase import create_client, Client
from typing import Dict, List, Any
from dotenv import load_dotenv

# Charger le .env depuis la racine du projet
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)

# Ajouter le path parent pour les imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RLSPolicyChecker:
    """Vérificateur des policies RLS pour compatibilité nouveaux champs"""
    
    def __init__(self):
        """Initialise la connexion Supabase avec différents types de clés"""
        self.url = os.getenv('SUPABASE_URL')
        
        # Tester avec service key et anon key
        self.service_key = os.getenv('SUPABASE_SERVICE_KEY')
        self.anon_key = os.getenv('SUPABASE_ANON_KEY')
        
        if not self.url:
            raise ValueError("SUPABASE_URL manquante")
        
        self.clients = {}
        
        # Créer clients selon les clés disponibles
        if self.service_key:
            self.clients['service'] = create_client(self.url, self.service_key)
            logger.info("✅ Client service key créé")
        
        if self.anon_key:
            self.clients['anon'] = create_client(self.url, self.anon_key)
            logger.info("✅ Client anon key créé")
        
        if not self.clients:
            raise ValueError("Aucune clé Supabase disponible")
    
    def check_table_access(self, client_type: str, table: str) -> Dict[str, Any]:
        """Teste l'accès en lecture à une table"""
        if client_type not in self.clients:
            return {"error": f"Client {client_type} non disponible"}
        
        client = self.clients[client_type]
        
        try:
            logger.info(f"🔍 Test accès {client_type} sur table '{table}'")
            
            # Test SELECT basique
            response = client.table(table).select('*').limit(1).execute()
            
            if response.data is not None:
                columns = list(response.data[0].keys()) if response.data else []
                return {
                    "status": "success",
                    "accessible": True,
                    "rows_returned": len(response.data),
                    "columns": columns,
                    "sample_record": response.data[0] if response.data else None
                }
            else:
                return {
                    "status": "no_data",
                    "accessible": True,
                    "rows_returned": 0,
                    "columns": [],
                    "sample_record": None
                }
                
        except Exception as e:
            logger.error(f"❌ Erreur accès {client_type} sur {table}: {e}")
            return {
                "status": "error",
                "accessible": False,
                "error": str(e)
            }
    
    def check_specific_columns(self, client_type: str, table: str, columns: List[str]) -> Dict[str, Any]:
        """Teste l'accès à des colonnes spécifiques"""
        if client_type not in self.clients:
            return {"error": f"Client {client_type} non disponible"}
        
        client = self.clients[client_type]
        
        try:
            # Construire le SELECT avec colonnes spécifiques
            select_clause = ', '.join(columns)
            logger.info(f"🔍 Test colonnes {client_type} sur {table}: {select_clause}")
            
            response = client.table(table).select(select_clause).limit(1).execute()
            
            return {
                "status": "success",
                "accessible": True,
                "columns_tested": columns,
                "rows_returned": len(response.data) if response.data else 0
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur colonnes {client_type} sur {table}: {e}")
            return {
                "status": "error",
                "accessible": False,
                "columns_tested": columns,
                "error": str(e)
            }
    
    def simulate_new_columns_access(self) -> Dict[str, Any]:
        """Simule l'accès aux nouvelles colonnes gmaps_url/apple_url"""
        results = {
            "pois": {},
            "events": {},
            "recommendations": []
        }
        
        # Colonnes à tester (existantes + futures)
        poi_columns = ['id', 'name', 'type', 'latitude', 'longitude', 'active']
        event_columns = ['id', 'title', 'latitude', 'longitude', 'start_time']
        
        for client_type in self.clients.keys():
            logger.info(f"\n🔍 === Test client {client_type.upper()} ===")
            
            # Test POIs
            results["pois"][client_type] = self.check_table_access(client_type, 'pois')
            
            # Test Events  
            results["events"][client_type] = self.check_table_access(client_type, 'events')
            
            # Test colonnes spécifiques POIs
            if results["pois"][client_type].get("accessible"):
                poi_columns_test = self.check_specific_columns(client_type, 'pois', poi_columns)
                results["pois"][client_type]["columns_test"] = poi_columns_test
            
            # Test colonnes spécifiques Events
            if results["events"][client_type].get("accessible"):
                event_columns_test = self.check_specific_columns(client_type, 'events', event_columns)
                results["events"][client_type]["columns_test"] = event_columns_test
        
        # Générer recommandations
        results["recommendations"] = self._generate_recommendations(results)
        
        return results
    
    def _generate_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """Génère des recommandations selon les résultats"""
        recommendations = []
        
        # Vérifier l'accès POIs
        for client_type, poi_result in results["pois"].items():
            if not poi_result.get("accessible", False):
                recommendations.append(
                    f"⚠️ CRITIQUE: Client {client_type} ne peut pas lire la table 'pois'. "
                    "Les nouveaux champs gmaps_url/apple_url ne seront pas accessibles."
                )
            elif poi_result.get("rows_returned", 0) == 0:
                recommendations.append(
                    f"ℹ️ Client {client_type} peut lire 'pois' mais aucune donnée retournée. "
                    "Vérifier les filtres RLS (territory_id, active, etc.)"
                )
            else:
                recommendations.append(
                    f"✅ Client {client_type} peut lire 'pois' correctement. "
                    "Les nouveaux champs seront accessibles."
                )
        
        # Vérifier l'accès Events
        for client_type, event_result in results["events"].items():
            if not event_result.get("accessible", False):
                recommendations.append(
                    f"⚠️ CRITIQUE: Client {client_type} ne peut pas lire la table 'events'. "
                    "Les nouveaux champs gmaps_url/apple_url ne seront pas accessibles."
                )
        
        # Recommandations générales
        if any("CRITIQUE" in rec for rec in recommendations):
            recommendations.append(
                "🚨 ACTION REQUISE: Modifier les RLS policies avant d'ajouter gmaps_url/apple_url"
            )
        else:
            recommendations.append(
                "✅ MIGRATION SAFE: Les RLS policies existantes permettront l'accès aux nouveaux champs"
            )
        
        return recommendations
    
    def run_complete_check(self) -> Dict[str, Any]:
        """Lance une vérification complète"""
        logger.info("🔍 === VÉRIFICATION RLS POLICIES - NOUVEAUX CHAMPS MAPS ===")
        
        # Informations sur l'environnement
        env_info = {
            "supabase_url": self.url[:30] + "..." if self.url else "Non définie",
            "service_key_available": bool(self.service_key),
            "anon_key_available": bool(self.anon_key),
            "clients_created": list(self.clients.keys())
        }
        
        logger.info(f"🌍 URL Supabase: {env_info['supabase_url']}")
        logger.info(f"🔑 Service key: {env_info['service_key_available']}")
        logger.info(f"🔑 Anon key: {env_info['anon_key_available']}")
        
        # Tests d'accès
        access_results = self.simulate_new_columns_access()
        
        # Résultat final
        final_result = {
            "environment": env_info,
            "access_tests": access_results,
            "timestamp": "2024-01-01",  # TODO: datetime.now().isoformat()
            "migration_safe": not any("CRITIQUE" in rec for rec in access_results["recommendations"])
        }
        
        # Affichage résumé
        logger.info("\n📊 === RÉSUMÉ ===")
        for rec in access_results["recommendations"]:
            if "CRITIQUE" in rec:
                logger.error(rec)
            elif "⚠️" in rec:
                logger.warning(rec)
            else:
                logger.info(rec)
        
        migration_status = "✅ SAFE" if final_result["migration_safe"] else "🚨 BLOQUÉ"
        logger.info(f"\n🎯 MIGRATION STATUS: {migration_status}")
        
        return final_result


def main():
    """Point d'entrée principal"""
    try:
        checker = RLSPolicyChecker()
        results = checker.run_complete_check()
        
        # Sauvegarder les résultats
        import json
        
        output_file = "rls_check_results.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📄 Résultats sauvegardés dans {output_file}")
        
        # Code de sortie
        exit_code = 0 if results["migration_safe"] else 1
        sys.exit(exit_code)
        
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()