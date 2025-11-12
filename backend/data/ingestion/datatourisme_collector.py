#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DATAtourisme Data Collector
Collecte les POIs depuis l'API REST DATAtourisme

Usage:
    python datatourisme_collector.py --limit 50000 --output data/raw/datatourisme_pois.parquet
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

import requests
import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class DATAtourismeCollector:
    """Collector pour l'API DATAtourisme"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("DATATOURISME_API_KEY")
        self.base_url = os.getenv("DATATOURISME_BASE_URL", "https://api.datatourisme.fr/v1")

        if not self.api_key:
            raise ValueError("DATATOURISME_API_KEY not found in environment variables")

        self.headers = {
            "X-API-Key": self.api_key,
            "Accept": "application/json"
        }

        self.pois = []
        self.stats = {
            "total_collected": 0,
            "api_calls": 0,
            "errors": 0,
            "start_time": datetime.now()
        }

    def _make_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Fait une requête à l'API avec gestion d'erreurs"""
        url = f"{self.base_url}/{endpoint}"

        try:
            self.stats["api_calls"] += 1
            response = requests.get(url, headers=self.headers, params=params, timeout=30)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                # Rate limit: attendre avant de réessayer
                logger.warning("Rate limit hit, waiting 60s...")
                time.sleep(60)
                return self._make_request(endpoint, params)
            else:
                logger.error(f"HTTP {response.status_code}: {response.text[:200]}")
                self.stats["errors"] += 1
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            self.stats["errors"] += 1
            return None

    def collect_pois(
        self,
        limit: int = 50000,
        page_size: int = 250,
        filters: Optional[Dict] = None,
        save_interval: int = 5000
    ) -> List[Dict]:
        """
        Collecte les POIs avec pagination

        Args:
            limit: Nombre max de POIs à collecter
            page_size: Taille de page API (max 250)
            filters: Filtres optionnels (ex: type, zone géo)
            save_interval: Sauvegarder tous les N POIs

        Returns:
            Liste de POIs
        """
        logger.info(f"Starting collection: target={limit}, page_size={page_size}")

        params = {"page_size": min(page_size, 250)}
        if filters:
            params.update(filters)

        pbar = tqdm(total=limit, desc="Collecting POIs")

        while len(self.pois) < limit:
            # Requête API
            response = self._make_request("catalog", params)

            if not response or "objects" not in response:
                logger.error("Invalid response, stopping collection")
                break

            # Extraire POIs
            pois_batch = response["objects"]

            if not pois_batch:
                logger.info("No more POIs available")
                break

            # Ajouter à la collection
            self.pois.extend(pois_batch)
            self.stats["total_collected"] = len(self.pois)

            pbar.update(len(pois_batch))

            # Sauvegarde incrémentale
            if len(self.pois) % save_interval == 0:
                self._save_checkpoint()

            # Pagination: utiliser le lien "next" fourni par l'API
            meta = response.get("meta", {})
            next_url = meta.get("next")

            if not next_url:
                logger.info("No next page, collection complete")
                break

            # Extraire les paramètres du next URL
            # Format: https://api.datatourisme.fr/v1/catalog?page_size=250&crs=...
            # On garde juste le cursor (crs)
            if "crs=" in next_url:
                crs = next_url.split("crs=")[1].split("&")[0]
                params["crs"] = crs

            # Rate limiting soft (respecter l'API)
            time.sleep(0.1)

        pbar.close()

        # Trim si on a dépassé la limite
        self.pois = self.pois[:limit]
        self.stats["total_collected"] = len(self.pois)

        logger.info(f"Collection complete: {self.stats['total_collected']} POIs")
        return self.pois

    def _save_checkpoint(self):
        """Sauvegarde checkpoint intermédiaire"""
        checkpoint_file = Path("data/raw/datatourisme_checkpoint.json")
        checkpoint_file.parent.mkdir(parents=True, exist_ok=True)

        with open(checkpoint_file, "w", encoding="utf-8") as f:
            # Convertir datetime en string pour JSON
            stats_serializable = {**self.stats}
            stats_serializable["start_time"] = self.stats["start_time"].isoformat()
            stats_serializable["checkpoint_time"] = datetime.now().isoformat()

            json.dump({
                "pois": self.pois,
                "stats": stats_serializable
            }, f, ensure_ascii=False, indent=2)

        logger.info(f"Checkpoint saved: {len(self.pois)} POIs")

    def save_to_parquet(self, output_path: str):
        """Sauvegarde les POIs en format Parquet"""
        if not self.pois:
            logger.warning("No POIs to save")
            return

        # Convertir en DataFrame
        df = pd.DataFrame(self.pois)

        # Convertir les colonnes complexes (objets/listes) en JSON strings
        # pour compatibilité Parquet
        complex_columns = []
        for col in df.columns:
            # Détecter les colonnes avec des types complexes
            sample = df[col].dropna().iloc[0] if not df[col].dropna().empty else None
            if sample is not None and (isinstance(sample, (dict, list))):
                complex_columns.append(col)

        logger.info(f"Converting {len(complex_columns)} complex columns to JSON strings")
        for col in complex_columns:
            df[col] = df[col].apply(lambda x: json.dumps(x, ensure_ascii=False) if x is not None else None)

        # Créer le dossier de sortie si nécessaire
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Sauvegarder en Parquet
        df.to_parquet(output_file, index=False, compression="snappy")

        logger.info(f"✅ Saved {len(df)} POIs to {output_path}")
        logger.info(f"   File size: {output_file.stat().st_size / 1024 / 1024:.2f} MB")

        # Stats finales
        duration = (datetime.now() - self.stats["start_time"]).total_seconds()
        logger.info(f"📊 Collection Stats:")
        logger.info(f"   - POIs collected: {self.stats['total_collected']}")
        logger.info(f"   - API calls: {self.stats['api_calls']}")
        logger.info(f"   - Errors: {self.stats['errors']}")
        logger.info(f"   - Duration: {duration:.1f}s")
        logger.info(f"   - Avg speed: {self.stats['total_collected'] / duration:.1f} POIs/s")

    def get_poi_types_distribution(self) -> Dict[str, int]:
        """Analyse la distribution des types de POIs"""
        if not self.pois:
            return {}

        df = pd.DataFrame(self.pois)

        # Explode les types (car c'est une liste)
        if "type" in df.columns:
            types_series = df["type"].explode()
            return types_series.value_counts().to_dict()

        return {}

    def print_sample(self, n: int = 3):
        """Affiche un échantillon de POIs"""
        if not self.pois:
            logger.warning("No POIs collected yet")
            return

        logger.info(f"\n📋 Sample of {min(n, len(self.pois))} POIs:")

        for i, poi in enumerate(self.pois[:n], 1):
            print(f"\n--- POI {i} ---")
            print(f"UUID: {poi.get('uuid', 'N/A')}")
            print(f"Label: {poi.get('label', 'N/A')}")
            print(f"Type: {poi.get('type', 'N/A')}")

            # Géolocalisation
            if "isLocatedAt" in poi and poi["isLocatedAt"]:
                geo = poi["isLocatedAt"][0].get("geo", {})
                print(f"Location: {geo.get('latitude', 'N/A')}, {geo.get('longitude', 'N/A')}")

            # Description
            if "hasDescription" in poi and poi["hasDescription"]:
                desc = poi["hasDescription"][0].get("shortDescription", {})
                fr_desc = desc.get("@fr", "N/A")
                if isinstance(fr_desc, str):
                    print(f"Description (FR): {fr_desc[:100]}...")


def main():
    """Point d'entrée principal"""
    import argparse

    parser = argparse.ArgumentParser(description="Collect POIs from DATAtourisme API")
    parser.add_argument("--limit", type=int, default=50000, help="Max POIs to collect")
    parser.add_argument("--page-size", type=int, default=250, help="API page size")
    parser.add_argument("--output", type=str, default="data/raw/datatourisme_pois.parquet", help="Output file")
    parser.add_argument("--sample", action="store_true", help="Show sample after collection")

    args = parser.parse_args()

    # Créer le collector
    collector = DATAtourismeCollector()

    # Collecter les POIs
    collector.collect_pois(limit=args.limit, page_size=args.page_size)

    # Afficher échantillon si demandé
    if args.sample:
        collector.print_sample(n=3)

    # Afficher distribution des types
    types_dist = collector.get_poi_types_distribution()
    if types_dist:
        logger.info("\n📊 Top 10 POI Types:")
        for poi_type, count in sorted(types_dist.items(), key=lambda x: x[1], reverse=True)[:10]:
            logger.info(f"   {poi_type}: {count}")

    # Sauvegarder en Parquet
    collector.save_to_parquet(args.output)


if __name__ == "__main__":
    main()
