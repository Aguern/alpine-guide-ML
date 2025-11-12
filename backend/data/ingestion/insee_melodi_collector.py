#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TourismIQ - Collecteur API INSEE Melodi

Collecte les données économiques et démographiques depuis l'API Melodi (INSEE)
Sans jeton : 30 requêtes/minute (suffisant pour notre usage)

Documentation API : https://api.insee.fr/catalogue/site/themes/wso2/subthemes/insee/pages/item-info.jag?name=Sirene&version=V3&provider=insee
"""

import requests
import pandas as pd
import time
from pathlib import Path
from typing import Optional, Dict, List
import json

print("=" * 80)
print("📊 TOURISMIQ - COLLECTEUR INSEE MELODI")
print("=" * 80)

# Configuration
API_BASE_URL = "https://api.insee.fr/melodi/data"
BASE_DIR = Path(__file__).parent.parent.parent
OUTPUT_DIR = BASE_DIR / "data/raw"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Limite de requêtes : 30/minute en accès libre
REQUEST_DELAY = 2  # secondes entre chaque requête (30 req/min = 1 req/2s)


def download_melodi_dataset(dataset_id: str, filename: str) -> Path:
    """Télécharge un dataset depuis l'API Melodi"""
    url = f"https://api.insee.fr/melodi/file/{dataset_id}"
    output_path = OUTPUT_DIR / filename

    print(f"📥 Téléchargement {dataset_id}...")
    response = requests.get(url, timeout=60)
    response.raise_for_status()

    with open(output_path, 'wb') as f:
        f.write(response.content)

    print(f"✅ Téléchargé : {output_path} ({output_path.stat().st_size / 1024 / 1024:.1f} MB)")
    return output_path


def extract_zip(zip_path: Path, extract_dir: Path) -> List[Path]:
    """Extrait un fichier ZIP"""
    import zipfile

    print(f"📦 Extraction {zip_path.name}...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
        extracted = [extract_dir / name for name in zip_ref.namelist()]

    print(f"✅ Fichiers extraits : {len(extracted)}")
    return extracted


def get_communes_economie(limit: int = None) -> pd.DataFrame:
    """
    Récupère les données économiques par commune depuis Melodi

    Dataset utilisé :
    - DS_BTS_SAL_EQTP_SEX_AGE : Salaires dans le secteur privé au niveau communal

    Retourne un DataFrame avec:
    - code_insee: Code INSEE de la commune (5 chiffres)
    - nom_commune: Nom de la commune
    - salaire_net_moyen: Salaire net mensuel moyen (euros)
    """

    print("\n📥 Collecte données économiques communales depuis Melodi...")

    # Dataset des salaires communaux
    dataset_id = "DS_BTS_SAL_EQTP_SEX_AGE/DS_BTS_SAL_EQTP_SEX_AGE_2023_CSV_FR"
    zip_filename = "insee_salaires_communes.zip"

    # Télécharger le dataset
    zip_path = download_melodi_dataset(dataset_id, zip_filename)

    # Extraire
    extracted = extract_zip(zip_path, OUTPUT_DIR)

    # Trouver le fichier data.csv (PAS metadata.csv)
    data_file = OUTPUT_DIR / "DS_BTS_SAL_EQTP_SEX_AGE_2023_data.csv"

    if not data_file.exists():
        print(f"❌ Erreur : fichier {data_file.name} non trouvé. Fichiers extraits: {[f.name for f in extracted]}")
        return pd.DataFrame()

    print(f"\n📊 Traitement des données : {data_file.name}")

    # Charger uniquement les données au niveau communal
    print("   Chargement du fichier CSV (38 MB)...")
    df_raw = pd.read_csv(data_file, delimiter=';', dtype={'GEO': str})

    print(f"   Total lignes : {len(df_raw):,}")

    # Filtrer sur les communes uniquement
    df_communes = df_raw[df_raw['GEO_OBJECT'] == 'COM'].copy()
    print(f"   Lignes communales : {len(df_communes):,}")

    # Filtrer sur salaire moyen total (SEX='_T', AGE='_T')
    df_filtered = df_communes[
        (df_communes['SEX'] == '_T') &
        (df_communes['AGE'] == '_T') &
        (df_communes['CONF_STATUS'] == 'F')  # Uniquement données diffusables
    ].copy()

    print(f"   Lignes après filtres : {len(df_filtered):,}")

    # Nettoyer le code INSEE (padding avec 0 si besoin)
    df_filtered['code_insee'] = df_filtered['GEO'].str.zfill(5)

    # Garder uniquement les colonnes utiles
    df_result = df_filtered[['code_insee', 'OBS_VALUE', 'TIME_PERIOD']].copy()
    df_result.rename(columns={
        'OBS_VALUE': 'salaire_net_moyen',
        'TIME_PERIOD': 'annee'
    }, inplace=True)

    # Joindre avec noms de communes
    communes_file = OUTPUT_DIR / "communes_population_all.parquet"
    if communes_file.exists():
        df_communes_ref = pd.read_parquet(communes_file)
        df_result = df_result.merge(
            df_communes_ref[['code_insee', 'nom_commune']],
            on='code_insee',
            how='left'
        )
        print(f"✅ {df_result['nom_commune'].notna().sum():,} communes jointes avec noms")
    else:
        df_result['nom_commune'] = None
        print("⚠️  Fichier communes non trouvé, pas de noms disponibles")

    # Appliquer limite si demandée
    if limit:
        df_result = df_result.head(limit)
        print(f"   Limite appliquée : {limit} communes")

    # Nettoyer les données manquantes
    df_result = df_result.dropna(subset=['salaire_net_moyen'])

    print(f"\n✅ {len(df_result):,} communes avec données économiques valides")
    print(f"   Salaire moyen : {df_result['salaire_net_moyen'].mean():.2f}€/mois")
    print(f"   Min: {df_result['salaire_net_moyen'].min():.2f}€, Max: {df_result['salaire_net_moyen'].max():.2f}€")

    return df_result[['code_insee', 'nom_commune', 'salaire_net_moyen', 'annee']]


def save_data(df: pd.DataFrame, filename: str):
    """Sauvegarde les données en Parquet"""
    if df.empty:
        print("⚠️  Pas de données à sauvegarder")
        return

    output_file = OUTPUT_DIR / filename
    df.to_parquet(output_file, index=False, compression='snappy')

    file_size = output_file.stat().st_size / 1024 / 1024
    print(f"\n💾 Données sauvegardées : {output_file}")
    print(f"   Taille : {file_size:.2f} MB")
    print(f"   Colonnes : {len(df.columns)}")
    print(f"   Lignes : {len(df)}")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Collecteur INSEE Melodi")
    parser.add_argument("--limit", type=int, default=None, help="Nombre de communes à collecter (par défaut: toutes)")
    parser.add_argument("--output", type=str, default="insee_melodi_communes.parquet", help="Fichier de sortie")

    args = parser.parse_args()

    print("\n🎯 Configuration:")
    print(f"   Communes à collecter : {args.limit if args.limit else 'Toutes'}")
    print(f"   Fichier de sortie : {args.output}")
    print(f"   Quota API : 30 requêtes/minute (accès libre)")

    # Collecter les données
    df_economie = get_communes_economie(limit=args.limit)

    if not df_economie.empty:
        # Sauvegarder
        save_data(df_economie, args.output)

        # Statistiques
        print("\n" + "=" * 80)
        print("✅ COLLECTE TERMINÉE")
        print("=" * 80)
        print(f"\n📊 Résumé :")
        print(f"   • {len(df_economie)} communes avec données économiques")
        print(f"   • Colonnes disponibles : {', '.join(df_economie.columns.tolist())}")
        print(f"\n💡 Note :")
        print(f"   Ce collector utilise l'accès libre INSEE Melodi (30 req/min)")
        print(f"   Données réelles depuis l'API Melodi V2")
        print(f"   Source: DS_BTS_SAL_EQTP_SEX_AGE (salaires secteur privé 2022-2023)")
    else:
        print("\n⚠️  Aucune donnée collectée")

    print("\n" + "=" * 80)
