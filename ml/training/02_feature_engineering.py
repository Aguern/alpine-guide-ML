#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TourismIQ - Feature Engineering pour Quality Scorer

Crée les 20 features ML + target synthétique (score 0-100)

Features (pondération finale):
- Complétude (40%): has_name, has_description, has_gps, has_type, has_contact
- Richesse (30%): description_length, description_richness, multilingual
- Contexte (20%): poi_density, commune_population, climate_type
- Freshness (10%): days_since_update
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from datetime import datetime
from collections import Counter
import re

print("=" * 80)
print("⚙️  TOURISMIQ - FEATURE ENGINEERING")
print("=" * 80)

# ============================================================================
# 1. CHARGEMENT DES DONNÉES
# ============================================================================
print("\n📂 1. CHARGEMENT DES DONNÉES")
print("-" * 80)

DATA_DIR = Path("../data/raw")
pois_file = DATA_DIR / "datatourisme_pois_50k.parquet"
communes_file = DATA_DIR / "communes_population_all.parquet"
climate_file = DATA_DIR / "climate_regions.parquet"
insee_file = DATA_DIR / "insee_melodi_salaires_complet.parquet"

df_pois = pd.read_parquet(pois_file)
df_communes = pd.read_parquet(communes_file)
df_climate = pd.read_parquet(climate_file)

# Charger données INSEE (optionnel)
if insee_file.exists():
    df_insee = pd.read_parquet(insee_file)
    print(f"✅ {len(df_pois):,} POIs chargés")
    print(f"✅ {len(df_communes):,} communes chargées")
    print(f"✅ {len(df_climate)} régions climatiques chargées")
    print(f"✅ {len(df_insee):,} communes avec salaires INSEE chargées")
else:
    df_insee = None
    print(f"✅ {len(df_pois):,} POIs chargés")
    print(f"✅ {len(df_communes):,} communes chargées")
    print(f"✅ {len(df_climate)} régions climatiques chargées")
    print(f"⚠️  Données INSEE non trouvées (optionnel)")

# ============================================================================
# 2. EXTRACTION DONNÉES DE BASE
# ============================================================================
print("\n\n🔍 2. EXTRACTION DONNÉES DE BASE")
print("-" * 80)

def parse_json(value):
    """Parse JSON string"""
    if pd.isna(value):
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except:
            return None
    return value

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

# Extraire description FR
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

# Extraire nom FR
def extract_name_fr(label):
    label = parse_json(label)
    if isinstance(label, dict):
        return label.get('@fr') or label.get('fr')
    elif isinstance(label, str):
        return label
    return None

# Extraire type principal
def extract_main_type(type_val):
    type_val = parse_json(type_val)
    if not type_val or not isinstance(type_val, list):
        return None
    for t in reversed(type_val):
        if t not in ['schema:Thing', 'schema:Place', 'olo:OrderedList']:
            return t
    return type_val[0] if type_val else None

# Extraire email/phone/website
def extract_contact_info(contact_list):
    contact_list = parse_json(contact_list)
    has_email = False
    has_phone = False
    has_website = False

    if contact_list and isinstance(contact_list, list):
        for contact in contact_list:
            if isinstance(contact, dict):
                if contact.get('email'):
                    has_email = True
                if contact.get('telephone'):
                    has_phone = True
                if contact.get('homepage'):
                    has_website = True

    return has_email, has_phone, has_website

# Extraire nombre de langues (multilinguisme)
def count_languages(label):
    label = parse_json(label)
    if isinstance(label, dict):
        return len([k for k in label.keys() if k.startswith('@')])
    return 1  # Au moins 1 langue

print("Extraction des données de base...")

# GPS
coords = df_pois['isLocatedAt'].apply(extract_coordinates)
df_pois['latitude'] = coords.apply(lambda x: x[0])
df_pois['longitude'] = coords.apply(lambda x: x[1])
print(f"  ✅ GPS: {df_pois['latitude'].notna().sum():,} POIs")

# Description
df_pois['description'] = df_pois['hasDescription'].apply(extract_description_fr)
print(f"  ✅ Descriptions: {df_pois['description'].notna().sum():,} POIs")

# Nom
df_pois['name'] = df_pois['label'].apply(extract_name_fr)
print(f"  ✅ Noms: {df_pois['name'].notna().sum():,} POIs")

# Type
df_pois['type_principal'] = df_pois['type'].apply(extract_main_type)
print(f"  ✅ Types: {df_pois['type_principal'].notna().sum():,} POIs")

# Contact
contact_info = df_pois['hasContact'].apply(extract_contact_info)
df_pois['has_email'] = contact_info.apply(lambda x: x[0])
df_pois['has_phone'] = contact_info.apply(lambda x: x[1])
df_pois['has_website'] = contact_info.apply(lambda x: x[2])
print(f"  ✅ Emails: {df_pois['has_email'].sum():,} POIs")
print(f"  ✅ Phones: {df_pois['has_phone'].sum():,} POIs")
print(f"  ✅ Websites: {df_pois['has_website'].sum():,} POIs")

# Langues
df_pois['nb_languages'] = df_pois['label'].apply(count_languages)
print(f"  ✅ Langues (moyenne): {df_pois['nb_languages'].mean():.1f}")

# ============================================================================
# 3. FEATURES DE COMPLÉTUDE (40 points)
# ============================================================================
print("\n\n📊 3. FEATURES DE COMPLÉTUDE (40 points)")
print("-" * 80)

# Feature 1: has_name (10 pts)
feat_has_name = df_pois['name'].notna().astype(int) * 10
print(f"  1. has_name: {feat_has_name.sum() / len(df_pois) / 10 * 100:.1f}% → {feat_has_name.mean():.1f}/10 pts")

# Feature 2: has_description (10 pts)
feat_has_description = df_pois['description'].notna().astype(int) * 10
print(f"  2. has_description: {feat_has_description.sum() / len(df_pois) / 10 * 100:.1f}% → {feat_has_description.mean():.1f}/10 pts")

# Feature 3: has_gps (10 pts)
feat_has_gps = df_pois['latitude'].notna().astype(int) * 10
print(f"  3. has_gps: {feat_has_gps.sum() / len(df_pois) / 10 * 100:.1f}% → {feat_has_gps.mean():.1f}/10 pts")

# Feature 4: has_type (5 pts)
feat_has_type = df_pois['type_principal'].notna().astype(int) * 5
print(f"  4. has_type: {feat_has_type.sum() / len(df_pois) / 5 * 100:.1f}% → {feat_has_type.mean():.1f}/5 pts")

# Feature 5: has_contact (5 pts) - au moins 1 moyen
feat_has_contact = (df_pois['has_email'] | df_pois['has_phone'] | df_pois['has_website']).astype(int) * 5
print(f"  5. has_contact: {feat_has_contact.sum() / len(df_pois) / 5 * 100:.1f}% → {feat_has_contact.mean():.1f}/5 pts")

# Score complétude total
completeness_score = feat_has_name + feat_has_description + feat_has_gps + feat_has_type + feat_has_contact
print(f"\n  📊 Score Complétude: {completeness_score.mean():.1f}/40 pts")

# ============================================================================
# 4. FEATURES DE RICHESSE (30 points)
# ============================================================================
print("\n\n📝 4. FEATURES DE RICHESSE (30 points)")
print("-" * 80)

# Feature 6: description_length (0-10 pts)
# 200+ chars = 10 pts, linéaire
df_pois['description_length'] = df_pois['description'].fillna('').str.len()
feat_desc_length = np.clip(df_pois['description_length'] / 20, 0, 10)
print(f"  6. description_length: moyenne {df_pois['description_length'].mean():.0f} chars → {feat_desc_length.mean():.1f}/10 pts")

# Feature 7: description_richness (0-10 pts)
# Basé sur diversité lexicale (nb mots uniques / nb mots total)
def calc_richness(text):
    try:
        if pd.isna(text) or text is None or text == '':
            return 0
        if not isinstance(text, str):
            return 0
        words = text.lower().split()
        if len(words) < 5:
            return 0
        unique_ratio = len(set(words)) / len(words)
        # Score: ratio * nb_words / 10, max 10
        return min(unique_ratio * len(words) / 10, 10)
    except:
        return 0

feat_desc_richness = df_pois['description'].apply(calc_richness)
print(f"  7. description_richness: {feat_desc_richness.mean():.1f}/10 pts")

# Feature 8: nb_languages (0-5 pts)
# 1 langue = 1 pt, 2 = 3 pts, 3+ = 5 pts
feat_multilingual = df_pois['nb_languages'].apply(lambda x: min(1 if x == 1 else 3 if x == 2 else 5, 5))
print(f"  8. multilingual: moyenne {df_pois['nb_languages'].mean():.1f} langues → {feat_multilingual.mean():.1f}/5 pts")

# Feature 9: has_detailed_contact (0-5 pts)
# Email + phone + website = 5 pts, 2 = 3 pts, 1 = 1 pt
contact_count = df_pois['has_email'].astype(int) + df_pois['has_phone'].astype(int) + df_pois['has_website'].astype(int)
feat_detailed_contact = contact_count.apply(lambda x: 5 if x == 3 else 3 if x == 2 else 1 if x == 1 else 0)
print(f"  9. detailed_contact: {feat_detailed_contact.mean():.1f}/5 pts")

# Score richesse total
richness_score = feat_desc_length + feat_desc_richness + feat_multilingual + feat_detailed_contact
print(f"\n  📊 Score Richesse: {richness_score.mean():.1f}/30 pts")

# ============================================================================
# 5. FEATURES DE CONTEXTE GÉO (20 points)
# ============================================================================
print("\n\n🗺️  5. FEATURES DE CONTEXTE GÉO (20 points)")
print("-" * 80)

# Feature 10: POI density dans rayon 10km (0-5 pts)
# Calculer densité approximative (coûteux, on va faire simple)
# Pour chaque POI, compter nb POIs dans grille 0.1° x 0.1° (~11km)
print("  Calcul densité POIs (grille 0.1°)...")
df_with_coords = df_pois[df_pois['latitude'].notna()].copy()
df_with_coords['lat_grid'] = (df_with_coords['latitude'] * 10).round() / 10
df_with_coords['lon_grid'] = (df_with_coords['longitude'] * 10).round() / 10

grid_counts = df_with_coords.groupby(['lat_grid', 'lon_grid']).size().to_dict()
df_with_coords['poi_density'] = df_with_coords.apply(
    lambda row: grid_counts.get((row['lat_grid'], row['lon_grid']), 0),
    axis=1
)

# Merge back
df_pois['poi_density'] = 0
df_pois.loc[df_with_coords.index, 'poi_density'] = df_with_coords['poi_density']

# Score: densité normalisée 0-5
feat_poi_density = np.clip(df_pois['poi_density'] / 100, 0, 5)
print(f"  10. poi_density: moyenne {df_pois['poi_density'].mean():.0f} POIs/grille → {feat_poi_density.mean():.1f}/5 pts")

# Feature 11: Enrichissement salaire communal INSEE (0-5 pts)
print("  Enrichissement salaire communal (INSEE)...")

if df_insee is not None:
    # Approche simplifiée: utiliser salaire moyen national comme contexte économique général
    # Chaque POI reçoit le salaire moyen national (feature pour le ML)
    salaire_national_moyen = df_insee['salaire_net_moyen'].mean()
    df_pois['salaire_commune'] = salaire_national_moyen

    # Score: salaire moyen national normalisé (fixe pour tous)
    # 1500-3500€ → 0-5 pts
    feat_salaire_commune = df_pois['latitude'].notna().astype(float) * np.clip((salaire_national_moyen - 1500) / 400, 0, 5)

    print(f"  11. salaire_commune: contexte national {salaire_national_moyen:.0f}€/mois → {feat_salaire_commune.mean():.1f}/5 pts")
else:
    # Pas de données INSEE: score baseline
    df_pois['salaire_commune'] = np.nan
    feat_salaire_commune = df_pois['latitude'].notna().astype(int) * 2.5
    print(f"  11. salaire_commune: données INSEE non disponibles → baseline {feat_salaire_commune.mean():.1f}/5 pts")

# Feature 12: Contexte géographique général (0-5 pts)
feat_has_context_geo = df_pois['latitude'].notna().astype(int) * 5
print(f"  12. context_geo: {feat_has_context_geo.mean():.1f}/5 pts")

# Feature 13: Type de climat (0-5 pts)
# Pour l'instant, score baseline
feat_has_climate = df_pois['latitude'].notna().astype(int) * 5
print(f"  13. climate_context: {feat_has_climate.mean():.1f}/5 pts")

# Score contexte total
context_score = feat_poi_density + feat_has_context_geo + feat_has_climate
print(f"\n  📊 Score Contexte: {context_score.mean():.1f}/20 pts")

# ============================================================================
# 6. FEATURES DE FRESHNESS (10 points)
# ============================================================================
print("\n\n📅 6. FEATURES DE FRESHNESS (10 points)")
print("-" * 80)

# Feature 14: days_since_update (0-10 pts)
# Récent (< 30j) = 10, < 180j = 7, < 365j = 5, > 365j = 3
def calc_freshness(last_update):
    try:
        if pd.isna(last_update):
            return 5  # Baseline si inconnu

        # Parser date
        if isinstance(last_update, str):
            update_date = pd.to_datetime(last_update)
        else:
            update_date = last_update

        days_ago = (datetime.now() - update_date).days

        if days_ago < 30:
            return 10
        elif days_ago < 180:
            return 7
        elif days_ago < 365:
            return 5
        else:
            return 3
    except:
        return 5  # Baseline

feat_freshness = df_pois['lastUpdate'].apply(calc_freshness)
print(f"  14. freshness: {feat_freshness.mean():.1f}/10 pts")

# ============================================================================
# 7. SCORE QUALITY FINAL (0-100)
# ============================================================================
print("\n\n🎯 7. SCORE QUALITY FINAL")
print("-" * 80)

# Score synthétique final
quality_score = completeness_score + richness_score + context_score + feat_freshness

print(f"  Complétude (40%): {completeness_score.mean():.1f}/40")
print(f"  Richesse (30%):   {richness_score.mean():.1f}/30")
print(f"  Contexte (20%):   {context_score.mean():.1f}/20")
print(f"  Freshness (10%):  {feat_freshness.mean():.1f}/10")
print(f"  " + "-" * 40)
print(f"  📊 TOTAL:          {quality_score.mean():.1f}/100")

# Distribution
print(f"\n📈 Distribution:")
print(f"  Excellent (80-100): {(quality_score >= 80).sum():,} ({(quality_score >= 80).sum() / len(df_pois) * 100:.1f}%)")
print(f"  Good (60-80):       {((quality_score >= 60) & (quality_score < 80)).sum():,} ({((quality_score >= 60) & (quality_score < 80)).sum() / len(df_pois) * 100:.1f}%)")
print(f"  Medium (40-60):     {((quality_score >= 40) & (quality_score < 60)).sum():,} ({((quality_score >= 40) & (quality_score < 60)).sum() / len(df_pois) * 100:.1f}%)")
print(f"  Low (<40):          {(quality_score < 40).sum():,} ({(quality_score < 40).sum() / len(df_pois) * 100:.1f}%)")

# ============================================================================
# 8. CRÉATION DATASET ML-READY
# ============================================================================
print("\n\n💾 8. CRÉATION DATASET ML-READY")
print("-" * 80)

# Créer DataFrame avec features + target
df_ml = pd.DataFrame({
    # IDs
    'uuid': df_pois['uuid'],
    'name': df_pois['name'],
    'type': df_pois['type_principal'],

    # Features de base
    'latitude': df_pois['latitude'],
    'longitude': df_pois['longitude'],
    'description_length': df_pois['description_length'],
    'nb_languages': df_pois['nb_languages'],
    'poi_density': df_pois['poi_density'],
    'salaire_commune': df_pois['salaire_commune'],

    # Features binaires
    'has_name': df_pois['name'].notna().astype(int),
    'has_description': df_pois['description'].notna().astype(int),
    'has_gps': df_pois['latitude'].notna().astype(int),
    'has_type': df_pois['type_principal'].notna().astype(int),
    'has_email': df_pois['has_email'].astype(int),
    'has_phone': df_pois['has_phone'].astype(int),
    'has_website': df_pois['has_website'].astype(int),

    # Scores intermédiaires
    'completeness_score': completeness_score,
    'richness_score': richness_score,
    'context_score': context_score,
    'freshness_score': feat_freshness,

    # TARGET
    'quality_score': quality_score
})

# Sauvegarder
output_file = Path("../data/processed/features_ml.parquet")
output_file.parent.mkdir(parents=True, exist_ok=True)
df_ml.to_parquet(output_file, index=False, compression='snappy')

print(f"✅ Dataset ML sauvegardé: {output_file}")
print(f"   Records: {len(df_ml):,}")
print(f"   Features: {len(df_ml.columns) - 1} (+ 1 target)")
print(f"   Taille: {output_file.stat().st_size / 1024 / 1024:.2f} MB")

# ============================================================================
# 9. STATISTIQUES FINALES
# ============================================================================
print("\n\n" + "=" * 80)
print("✅ FEATURE ENGINEERING TERMINÉ")
print("=" * 80)

print("\n📊 Features créées:")
print(f"  • Complétude: 5 features (has_name, has_description, has_gps, has_type, has_contact)")
print(f"  • Richesse: 4 features (desc_length, desc_richness, multilingual, detailed_contact)")
print(f"  • Contexte: 3 features (poi_density, geo_context, climate)")
print(f"  • Freshness: 1 feature (days_since_update)")
print(f"  • Total: 13 features de base + 4 scores intermédiaires = 17 colonnes")

print(f"\n🎯 Target (quality_score):")
print(f"  • Moyenne: {quality_score.mean():.1f}/100")
print(f"  • Médiane: {quality_score.median():.1f}/100")
print(f"  • Écart-type: {quality_score.std():.1f}")
print(f"  • Min: {quality_score.min():.1f}, Max: {quality_score.max():.1f}")

print(f"\n📈 Prochaine étape:")
print(f"  → Notebook 03: Entraînement Quality Scorer (LightGBM/XGBoost)")
print(f"  → Objectif: R² > 0.75, MAE < 10 points")

print("\n" + "=" * 80)
