#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TourismIQ - Analyse EDA
Exploration rapide des données collectées
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from collections import Counter

print("=" * 80)
print("📊 TOURISMIQ - ANALYSE EDA")
print("=" * 80)

# Chemins
DATA_DIR = Path("../data/raw")
pois_file = DATA_DIR / "datatourisme_pois_50k.parquet"
communes_file = DATA_DIR / "communes_population_all.parquet"
climate_file = DATA_DIR / "climate_regions.parquet"

# ============================================================================
# 1. CHARGEMENT DES DONNÉES
# ============================================================================
print("\n📂 1. CHARGEMENT DES DONNÉES")
print("-" * 80)

print("Chargement POIs...")
df_pois = pd.read_parquet(pois_file)
print(f"✅ {len(df_pois):,} POIs chargés")
print(f"   Colonnes: {len(df_pois.columns)}")
print(f"   Mémoire: {df_pois.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB")

print("\nChargement communes...")
df_communes = pd.read_parquet(communes_file)
print(f"✅ {len(df_communes):,} communes chargées")

print("\nChargement climat...")
df_climate = pd.read_parquet(climate_file)
print(f"✅ {len(df_climate)} régions chargées")

# ============================================================================
# 2. STRUCTURE DES POIS
# ============================================================================
print("\n\n📋 2. STRUCTURE DES POIS")
print("-" * 80)
print(f"Shape: {df_pois.shape}")
print(f"\nColonnes disponibles ({len(df_pois.columns)}):")
for i, col in enumerate(df_pois.columns[:20], 1):  # Premiers 20
    dtype = df_pois[col].dtype
    non_null = df_pois[col].notna().sum()
    pct = non_null / len(df_pois) * 100
    print(f"  {i:2d}. {col:30s} - {str(dtype):10s} - {pct:5.1f}% rempli")

if len(df_pois.columns) > 20:
    print(f"  ... et {len(df_pois.columns) - 20} colonnes supplémentaires")

# ============================================================================
# 3. ANALYSE DE COMPLÉTUDE
# ============================================================================
print("\n\n📊 3. ANALYSE DE COMPLÉTUDE")
print("-" * 80)

key_fields = [
    '@id', '@type', 'rdfs:label', 'hasDescription',
    'isLocatedAt', 'hasContact'
]

completeness = {}
for field in key_fields:
    if field in df_pois.columns:
        non_null = df_pois[field].notna().sum()
        pct = non_null / len(df_pois) * 100
        completeness[field] = pct
        status = "✅" if pct > 80 else "⚠️" if pct > 50 else "❌"
        print(f"{status} {field:25s}: {non_null:6,} / {len(df_pois):6,} ({pct:5.1f}%)")

# ============================================================================
# 4. EXTRACTION DES CHAMPS CLÉS
# ============================================================================
print("\n\n🔍 4. EXTRACTION DES CHAMPS CLÉS")
print("-" * 80)

# Helper: parser JSON
def parse_json(value):
    if pd.isna(value):
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except:
            return None
    return value

# Extraire types
def extract_main_type(type_val):
    type_val = parse_json(type_val)
    if not type_val or not isinstance(type_val, list):
        return None
    # Prendre le type le plus spécifique (dernier de la liste généralement)
    for t in reversed(type_val):
        if t not in ['schema:Thing', 'schema:Place', 'olo:OrderedList']:
            return t
    return type_val[0] if type_val else None

if 'type' in df_pois.columns:
    print("Extraction types de POIs...")
    df_pois['type_principal'] = df_pois['type'].apply(extract_main_type)
    print(f"✅ {df_pois['type_principal'].notna().sum():,} types extraits")
    print(f"\nTop 10 types de POIs:")
    for i, (type_name, count) in enumerate(df_pois['type_principal'].value_counts().head(10).items(), 1):
        print(f"  {i:2d}. {type_name:40s}: {count:6,} ({count/len(df_pois)*100:5.1f}%)")

# Extraire GPS
def extract_coordinates(located_at):
    located_at = parse_json(located_at)
    if not located_at or not isinstance(located_at, list):
        return None, None

    for location in located_at:
        if isinstance(location, dict) and 'geo' in location:
            geo = location['geo']
            if isinstance(geo, dict):
                lat = geo.get('latitude')
                lon = geo.get('longitude')
                if lat and lon:
                    try:
                        return float(lat), float(lon)
                    except:
                        pass
    return None, None

if 'isLocatedAt' in df_pois.columns:
    print("\nExtraction coordonnées GPS...")
    coords = df_pois['isLocatedAt'].apply(extract_coordinates)
    df_pois['latitude'] = coords.apply(lambda x: x[0])
    df_pois['longitude'] = coords.apply(lambda x: x[1])

    pois_with_coords = df_pois['latitude'].notna().sum()
    print(f"✅ {pois_with_coords:,} POIs avec GPS ({pois_with_coords/len(df_pois)*100:.1f}%)")

    if pois_with_coords > 0:
        df_geo = df_pois[df_pois['latitude'].notna()]
        print(f"\n📍 Zone géographique:")
        print(f"  Latitude:  {df_geo['latitude'].min():.4f} à {df_geo['latitude'].max():.4f}")
        print(f"  Longitude: {df_geo['longitude'].min():.4f} à {df_geo['longitude'].max():.4f}")

# Extraire descriptions
def extract_description_fr(desc_list):
    desc_list = parse_json(desc_list)
    if not desc_list or not isinstance(desc_list, list):
        return None

    for desc in desc_list:
        if isinstance(desc, dict) and 'shortDescription' in desc:
            short_desc = desc['shortDescription']
            if isinstance(short_desc, dict):
                return short_desc.get('@fr') or short_desc.get('fr')
            elif isinstance(short_desc, str):
                return short_desc
    return None

if 'hasDescription' in df_pois.columns:
    print("\nExtraction descriptions...")
    df_pois['description'] = df_pois['hasDescription'].apply(extract_description_fr)
    df_pois['description_length'] = df_pois['description'].fillna('').str.len()

    pois_with_desc = df_pois['description'].notna().sum()
    print(f"✅ {pois_with_desc:,} POIs avec description ({pois_with_desc/len(df_pois)*100:.1f}%)")

    if pois_with_desc > 0:
        print(f"\n📝 Statistiques descriptions:")
        desc_stats = df_pois[df_pois['description_length'] > 0]['description_length'].describe()
        print(f"  Longueur moyenne: {desc_stats['mean']:.0f} caractères")
        print(f"  Médiane: {desc_stats['50%']:.0f} caractères")
        print(f"  Min: {desc_stats['min']:.0f}, Max: {desc_stats['max']:.0f}")

# ============================================================================
# 5. FEATURES DE QUALITÉ (BASELINE)
# ============================================================================
print("\n\n⚙️ 5. FEATURES DE QUALITÉ")
print("-" * 80)

# Calculer features de base
features = {}

# Has name (colonne 'label')
if 'label' in df_pois.columns:
    features['has_name'] = df_pois['label'].notna().astype(int)

# Has description
if 'description' in df_pois.columns:
    features['has_description'] = df_pois['description'].notna().astype(int)
    features['description_length'] = df_pois['description_length']

# Has GPS
if 'latitude' in df_pois.columns:
    features['has_gps'] = df_pois['latitude'].notna().astype(int)

# Has type
if 'type_principal' in df_pois.columns:
    features['has_type'] = df_pois['type_principal'].notna().astype(int)

# Has contact
if 'hasContact' in df_pois.columns:
    features['has_contact'] = df_pois['hasContact'].notna().astype(int)

df_features = pd.DataFrame(features)

print("Features calculées:")
for feature_name, values in features.items():
    if feature_name != 'description_length':
        count = values.sum() if hasattr(values, 'sum') else 0
        print(f"  • {feature_name:25s}: {count:6,} / {len(df_pois):6,} ({count/len(df_pois)*100:5.1f}%)")

# Score de complétude simple
df_features['completeness_score'] = (
    df_features.get('has_name', 0) * 20 +
    df_features.get('has_description', 0) * 30 +
    df_features.get('has_gps', 0) * 20 +
    df_features.get('has_type', 0) * 15 +
    df_features.get('has_contact', 0) * 15
)

print(f"\n🎯 Score de Complétude (0-100):")
print(f"  Moyenne: {df_features['completeness_score'].mean():.1f}")
print(f"  Médiane: {df_features['completeness_score'].median():.1f}")
print(f"  Écart-type: {df_features['completeness_score'].std():.1f}")

# Distribution par catégories
low = (df_features['completeness_score'] < 40).sum()
medium = ((df_features['completeness_score'] >= 40) & (df_features['completeness_score'] < 60)).sum()
good = ((df_features['completeness_score'] >= 60) & (df_features['completeness_score'] < 80)).sum()
excellent = (df_features['completeness_score'] >= 80).sum()

print(f"\n📊 Distribution par qualité:")
print(f"  ❌ Low (<40):           {low:6,} ({low/len(df_features)*100:5.1f}%)")
print(f"  ⚠️  Medium (40-60):     {medium:6,} ({medium/len(df_features)*100:5.1f}%)")
print(f"  ✅ Good (60-80):        {good:6,} ({good/len(df_features)*100:5.1f}%)")
print(f"  🌟 Excellent (80-100):  {excellent:6,} ({excellent/len(df_features)*100:5.1f}%)")

# ============================================================================
# 6. DONNÉES CONTEXTUELLES
# ============================================================================
print("\n\n🏘️ 6. DONNÉES CONTEXTUELLES - COMMUNES")
print("-" * 80)
print(f"Total communes: {len(df_communes):,}")
print(f"Population totale: {df_communes['population'].sum():,.0f}")
print(f"Population moyenne: {df_communes['population'].mean():,.0f}")
print(f"\nTop 5 communes:")
for i, row in df_communes.nlargest(5, 'population').iterrows():
    print(f"  {i+1}. {row['nom_commune']:30s}: {row['population']:9,.0f} habitants")

print("\n\n🌤️ 7. DONNÉES CLIMATIQUES - RÉGIONS")
print("-" * 80)
print(f"{'Région':<35s} {'Temp (°C)':<12s} {'Précip (mm)':<15s} {'Type':<15s}")
print("-" * 80)
for _, row in df_climate.iterrows():
    print(f"{row['region']:<35s} {row['temp_avg_annual']:>8.1f}°C   {row['precipitation_annual_mm']:>10,.0f} mm   {row['climate_type']:<15s}")

# ============================================================================
# 8. SAUVEGARDE DONNÉES ENRICHIES
# ============================================================================
print("\n\n💾 8. SAUVEGARDE DONNÉES ENRICHIES")
print("-" * 80)

# Préparer données pour sauvegarde (colonnes simples uniquement)
df_pois_simple = pd.DataFrame({
    # IDs
    'uuid': df_pois.get('uuid'),
    'uri': df_pois.get('uri'),

    # Données extraites
    'type_principal': df_pois.get('type_principal'),
    'latitude': df_pois.get('latitude'),
    'longitude': df_pois.get('longitude'),
    'description': df_pois.get('description'),
    'description_length': df_pois.get('description_length'),

    # Features
    'has_name': df_features.get('has_name'),
    'has_description': df_features.get('has_description'),
    'has_gps': df_features.get('has_gps'),
    'has_type': df_features.get('has_type'),
    'has_contact': df_features.get('has_contact'),
    'completeness_score': df_features['completeness_score']
})

output_file = Path("../data/processed/pois_enriched_eda.parquet")
output_file.parent.mkdir(parents=True, exist_ok=True)
df_pois_simple.to_parquet(output_file, index=False, compression='snappy')

print(f"✅ Sauvegardé: {output_file}")
print(f"   Records: {len(df_pois_simple):,}")
print(f"   Colonnes: {len(df_pois_simple.columns)}")
print(f"   Taille: {output_file.stat().st_size / 1024 / 1024:.2f} MB")

# ============================================================================
# RÉSUMÉ FINAL
# ============================================================================
print("\n\n" + "=" * 80)
print("✅ ANALYSE EDA TERMINÉE")
print("=" * 80)
print("\n📈 Résumé:")
print(f"  • {len(df_pois):,} POIs analysés")
print(f"  • {len(df_pois.columns)} colonnes disponibles")
print(f"  • Score qualité moyen: {df_features['completeness_score'].mean():.1f}/100")
print(f"  • {(df_features['completeness_score'] >= 60).sum():,} POIs de qualité Good ou mieux")
print(f"  • Données enrichies sauvegardées pour feature engineering")

print("\n🎯 Prochaine étape:")
print("  → Notebook 02: Feature Engineering (20 features pour Quality Scorer)")
print("  → Target: Score synthétique 0-100 pour entraînement LightGBM")
print("\n" + "=" * 80)
