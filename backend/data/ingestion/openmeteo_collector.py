#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Open-Meteo Collector
Collecte les données météo historiques pour enrichissement ML

Open-Meteo est GRATUIT et sans clé API
URL: https://open-meteo.com/

Pour TourismIQ, on collecte:
- Moyennes climatiques par région (température, précipitations)
- Utilisation: feature engineering pour classifier POIs saisonniers

Usage:
    python openmeteo_collector.py --output data/raw/climate_regions.parquet
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta

import requests
import pandas as pd
from tqdm import tqdm

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OpenMeteoCollector:
    """
    Collector pour Open-Meteo (gratuit, pas de clé)

    Pour TourismIQ, on collecte des statistiques climatiques par région
    pour enrichir le ML (ex: identifier stations de ski vs plages)
    """

    BASE_URL = "https://archive-api.open-meteo.com/v1/archive"

    # Capitales régionales françaises pour sampling climatique
    REGIONAL_CITIES = {
        "Auvergne-Rhône-Alpes": {"name": "Lyon", "lat": 45.75, "lon": 4.85},
        "Bourgogne-Franche-Comté": {"name": "Dijon", "lat": 47.32, "lon": 5.04},
        "Bretagne": {"name": "Rennes", "lat": 48.11, "lon": -1.68},
        "Centre-Val de Loire": {"name": "Orléans", "lat": 47.90, "lon": 1.90},
        "Corse": {"name": "Ajaccio", "lat": 41.93, "lon": 8.74},
        "Grand Est": {"name": "Strasbourg", "lat": 48.58, "lon": 7.75},
        "Hauts-de-France": {"name": "Lille", "lat": 50.63, "lon": 3.06},
        "Île-de-France": {"name": "Paris", "lat": 48.85, "lon": 2.35},
        "Normandie": {"name": "Rouen", "lat": 49.44, "lon": 1.09},
        "Nouvelle-Aquitaine": {"name": "Bordeaux", "lat": 44.84, "lon": -0.58},
        "Occitanie": {"name": "Toulouse", "lat": 43.60, "lon": 1.44},
        "Pays de la Loire": {"name": "Nantes", "lat": 47.22, "lon": -1.55},
        "Provence-Alpes-Côte d'Azur": {"name": "Marseille", "lat": 43.30, "lon": 5.37},
    }

    def __init__(self):
        self.climate_data = []
        self.stats = {
            "regions_collected": 0,
            "api_calls": 0,
            "errors": 0
        }

    def _make_request(self, lat: float, lon: float, start_date: str, end_date: str) -> Optional[Dict]:
        """
        Fait une requête à Open-Meteo Archive API

        Args:
            lat, lon: Coordonnées GPS
            start_date, end_date: Format YYYY-MM-DD

        Returns:
            Données météo historiques ou None
        """
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date,
            "end_date": end_date,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,sunshine_duration",
            "timezone": "Europe/Paris"
        }

        try:
            self.stats["api_calls"] += 1
            response = requests.get(self.BASE_URL, params=params, timeout=30)

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

    def collect_regional_climate(self, year: int = 2024) -> List[Dict]:
        """
        Collecte les statistiques climatiques annuelles par région

        Args:
            year: Année de référence (défaut: 2024)

        Returns:
            Liste de données climatiques par région
        """
        logger.info(f"🌤️  Collecting climate data for {year}")

        # Dates de l'année complète
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"

        pbar = tqdm(self.REGIONAL_CITIES.items(), desc="Collecting regions")

        for region_name, city_info in pbar:
            pbar.set_description(f"Collecting {city_info['name']}")

            # Récupérer données météo annuelles
            data = self._make_request(
                city_info["lat"],
                city_info["lon"],
                start_date,
                end_date
            )

            if not data or "daily" not in data:
                logger.warning(f"Failed to get data for {region_name}")
                continue

            daily = data["daily"]

            # Calculer statistiques annuelles
            temps_max = daily["temperature_2m_max"]
            temps_min = daily["temperature_2m_min"]
            precip = daily["precipitation_sum"]
            sunshine = daily["sunshine_duration"]

            climate_stats = {
                "region": region_name,
                "city": city_info["name"],
                "latitude": city_info["lat"],
                "longitude": city_info["lon"],
                "year": year,
                # Températures
                "temp_avg_annual": round((sum(temps_max) + sum(temps_min)) / (2 * len(temps_max)), 1),
                "temp_max_summer": round(max(temps_max[151:243]), 1),  # Juin-Août
                "temp_min_winter": round(min(temps_min[0:90] + temps_min[335:]), 1),  # Déc-Fév
                # Précipitations
                "precipitation_annual_mm": round(sum(precip), 1),
                "precipitation_winter_mm": round(sum(precip[0:90] + precip[335:]), 1),
                # Ensoleillement
                "sunshine_annual_hours": round(sum(sunshine) / 3600, 0),  # Convertir secondes en heures
                # Classification climatique simple
                "climate_type": self._classify_climate(
                    sum(temps_max) / len(temps_max),
                    sum(precip),
                    sum(sunshine) / 3600
                )
            }

            self.climate_data.append(climate_stats)
            self.stats["regions_collected"] += 1

        pbar.close()

        logger.info(f"✅ Collected climate data for {len(self.climate_data)} regions")
        return self.climate_data

    def _classify_climate(self, temp_avg: float, precip_total: float, sunshine_hours: float) -> str:
        """
        Classification climatique simplifiée pour ML

        Returns:
            Type: "mediterranean", "oceanic", "continental", "mountain"
        """
        if temp_avg > 14 and precip_total < 700:
            return "mediterranean"  # Méditerranéen (chaud, sec)
        elif precip_total > 1000 and temp_avg < 13:
            return "oceanic"  # Océanique (doux, humide)
        elif temp_avg < 11:
            return "mountain"  # Montagnard (froid)
        else:
            return "continental"  # Continental (intermédiaire)

    def save_to_parquet(self, output_path: str):
        """Sauvegarde les données climatiques en Parquet"""
        if not self.climate_data:
            logger.warning("No climate data to save")
            return

        df = pd.DataFrame(self.climate_data)

        # Créer le dossier
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Sauvegarder
        df.to_parquet(output_file, index=False, compression="snappy")

        logger.info(f"✅ Saved climate data to {output_path}")
        logger.info(f"   Regions: {len(df)}")
        logger.info(f"   File size: {output_file.stat().st_size / 1024:.2f} KB")

        # Stats
        logger.info(f"\n📊 Collection Stats:")
        logger.info(f"   - Regions collected: {self.stats['regions_collected']}")
        logger.info(f"   - API calls: {self.stats['api_calls']}")
        logger.info(f"   - Errors: {self.stats['errors']}")

        # Aperçu des données
        logger.info(f"\n🌡️  Climate Summary:")
        logger.info(f"   - Warmest: {df.loc[df['temp_avg_annual'].idxmax(), 'region']} ({df['temp_avg_annual'].max()}°C)")
        logger.info(f"   - Coldest: {df.loc[df['temp_avg_annual'].idxmin(), 'region']} ({df['temp_avg_annual'].min()}°C)")
        logger.info(f"   - Wettest: {df.loc[df['precipitation_annual_mm'].idxmax(), 'region']} ({df['precipitation_annual_mm'].max()}mm)")
        logger.info(f"   - Sunniest: {df.loc[df['sunshine_annual_hours'].idxmax(), 'region']} ({df['sunshine_annual_hours'].max()}h)")


def main():
    """Point d'entrée principal"""
    import argparse

    parser = argparse.ArgumentParser(description="Collect climate data from Open-Meteo")
    parser.add_argument("--output", type=str, default="data/raw/climate_regions.parquet", help="Output file")
    parser.add_argument("--year", type=int, default=2024, help="Reference year")

    args = parser.parse_args()

    # Créer le collector
    collector = OpenMeteoCollector()

    # Collecter les données
    collector.collect_regional_climate(year=args.year)

    # Sauvegarder
    collector.save_to_parquet(args.output)


if __name__ == "__main__":
    main()
