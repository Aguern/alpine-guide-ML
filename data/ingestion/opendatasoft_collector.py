#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Opendatasoft Population Collector
Collecte les données de population par commune depuis Opendatasoft (API publique, sans clé)

Dataset: Population française par commune
URL: https://public.opendatasoft.com/explore/dataset/population-francaise-communes/

Usage:
    python opendatasoft_collector.py --output data/raw/communes_population.parquet
"""

import logging
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime

import requests
import pandas as pd
from tqdm import tqdm

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OpendatasoftCollector:
    """Collector pour les données de population via Opendatasoft"""

    BASE_URL = "https://public.opendatasoft.com/api/explore/v2.1/catalog/datasets"
    DATASET_ID = "population-francaise-communes"

    def __init__(self):
        self.communes = []
        self.stats = {
            "total_collected": 0,
            "api_calls": 0,
            "errors": 0,
            "start_time": datetime.now()
        }

    def _make_request(self, params: Dict) -> Optional[Dict]:
        """Fait une requête à l'API Opendatasoft"""
        url = f"{self.BASE_URL}/{self.DATASET_ID}/records"

        try:
            self.stats["api_calls"] += 1
            response = requests.get(url, params=params, timeout=30)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"HTTP {response.status_code}: {response.text[:200]}")
                self.stats["errors"] += 1
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            self.stats["errors"] += 1
            return None

    def collect_all_communes(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Collecte toutes les communes avec leur population

        Args:
            limit: Limite optionnelle du nombre de communes

        Returns:
            Liste de communes avec données démographiques
        """
        logger.info("🏘️  Starting Opendatasoft population collection")

        # Paramètres de base
        batch_size = 100  # Taille de page
        offset = 0
        total = None

        # Première requête pour connaître le total
        initial_params = {
            "limit": 1,
            "offset": 0
        }

        response = self._make_request(initial_params)
        if response:
            total = response.get("total_count", 0)
            logger.info(f"Total communes available: {total:,}")

            # Ajuster la limite si spécifiée
            if limit and limit < total:
                total = limit

        if not total:
            logger.error("Failed to get total count")
            return []

        # Barre de progression
        pbar = tqdm(total=total, desc="Collecting communes")

        # Collecter par batches
        while len(self.communes) < total:
            params = {
                "limit": batch_size,
                "offset": offset
            }

            response = self._make_request(params)

            if not response or "results" not in response:
                logger.error(f"Invalid response at offset {offset}")
                break

            batch = response["results"]

            if not batch:
                logger.info("No more communes")
                break

            # Ajouter à la collection
            self.communes.extend(batch)
            self.stats["total_collected"] = len(self.communes)

            pbar.update(len(batch))
            offset += batch_size

            # Respect de l'API (pas de rate limit strict, mais soyons gentils)
            # time.sleep(0.05)

        pbar.close()

        logger.info(f"✅ Collection complete: {len(self.communes):,} communes")
        return self.communes

    def save_to_parquet(self, output_path: str):
        """Sauvegarde les données en Parquet"""
        if not self.communes:
            logger.warning("No data to save")
            return

        # Convertir en DataFrame
        df = pd.DataFrame(self.communes)

        logger.info(f"Columns available: {list(df.columns)}")

        # Sélectionner et renommer les colonnes utiles
        columns_map = {
            "code_insee": "code_insee",
            "nom_de_la_commune": "nom_commune",
            "population_municipale": "population",
            "superficie": "superficie_km2",
            "code_region": "code_region",
            "nom_de_la_region": "nom_region",
            "code_departement": "code_departement",
            "annee_recensement": "annee_recensement"
        }

        # Garder seulement les colonnes qui existent
        available_cols = {k: v for k, v in columns_map.items() if k in df.columns}

        df_clean = df[list(available_cols.keys())].rename(columns=available_cols)

        # Convertir les types
        if "population" in df_clean.columns:
            df_clean["population"] = pd.to_numeric(df_clean["population"], errors="coerce")

        if "superficie_km2" in df_clean.columns:
            df_clean["superficie_km2"] = pd.to_numeric(df_clean["superficie_km2"], errors="coerce")

        # Calculer densité si population et superficie disponibles
        if "population" in df_clean.columns and "superficie_km2" in df_clean.columns:
            df_clean["densite_hab_km2"] = (
                df_clean["population"] / df_clean["superficie_km2"]
            ).round(2)

        # Créer le dossier de sortie
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Sauvegarder
        df_clean.to_parquet(output_file, index=False, compression="snappy")

        logger.info(f"✅ Saved {len(df_clean):,} communes to {output_path}")
        logger.info(f"   File size: {output_file.stat().st_size / 1024 / 1024:.2f} MB")
        logger.info(f"   Columns: {list(df_clean.columns)}")

        # Stats finales
        duration = (datetime.now() - self.stats["start_time"]).total_seconds()
        logger.info(f"\n📊 Collection Stats:")
        logger.info(f"   - Communes collected: {self.stats['total_collected']:,}")
        logger.info(f"   - API calls: {self.stats['api_calls']}")
        logger.info(f"   - Errors: {self.stats['errors']}")
        logger.info(f"   - Duration: {duration:.1f}s")

        # Stats démographiques
        logger.info(f"\n📈 Population Stats:")
        logger.info(f"   - Total population: {df_clean['population'].sum():,.0f}")
        logger.info(f"   - Avg population: {df_clean['population'].mean():.0f}")
        logger.info(f"   - Top 5 communes by population:")
        for idx, row in df_clean.nlargest(5, "population").iterrows():
            logger.info(f"     • {row['nom_commune']}: {row['population']:,.0f} habitants")


def main():
    """Point d'entrée principal"""
    import argparse

    parser = argparse.ArgumentParser(description="Collect population data from Opendatasoft")
    parser.add_argument("--output", type=str, default="data/raw/communes_population.parquet", help="Output file")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of communes (default: all)")

    args = parser.parse_args()

    # Créer le collector
    collector = OpendatasoftCollector()

    # Collecter les données
    collector.collect_all_communes(limit=args.limit)

    # Sauvegarder
    collector.save_to_parquet(args.output)


if __name__ == "__main__":
    main()
