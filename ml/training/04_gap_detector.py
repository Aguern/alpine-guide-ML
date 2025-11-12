#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TourismIQ - Gap Detector

Détecte les opportunités business et gaps de marché dans l'offre touristique

Approche:
1. Clustering géospatial (HDBSCAN ou KMeans)
2. Analyse distribution types de POIs par cluster
3. Détection gaps (types manquants vs benchmark national)
4. Scoring opportunités business

Output: Recommandations d'opportunités par zone
"""

import pandas as pd
import numpy as np
from pathlib import Path
from collections import Counter
import json

print("=" * 80)
print("🔍 TOURISMIQ - GAP DETECTOR")
print("=" * 80)

# ============================================================================
# 1. CHARGEMENT DES DONNÉES
# ============================================================================
print("\n📂 1. CHARGEMENT DES DONNÉES")
print("-" * 80)

features_file = Path("../data/processed/features_ml.parquet")
df = pd.read_parquet(features_file)

print(f"✅ {len(df):,} POIs chargés")
print(f"   Avec GPS: {df['latitude'].notna().sum():,}")
print(f"   Avec type: {df['type'].notna().sum():,}")

# Filtrer POIs avec GPS
df_geo = df[df['latitude'].notna() & df['longitude'].notna()].copy()
print(f"✅ {len(df_geo):,} POIs avec coordonnées pour clustering")

# ============================================================================
# 2. CLUSTERING GÉOSPATIAL (SIMPLE - GRILLE)
# ============================================================================
print("\n\n🗺️  2. CLUSTERING GÉOSPATIAL")
print("-" * 80)

# Pour simplifier, on utilise une grille régulière plutôt que HDBSCAN
# (HDBSCAN nécessite des dépendances supplémentaires)
# Grille de 0.2° x 0.2° (~22km x 22km)

print("Création de grille géographique (0.2° x 0.2°)...")

df_geo['lat_cluster'] = (df_geo['latitude'] / 0.2).round() * 0.2
df_geo['lon_cluster'] = (df_geo['longitude'] / 0.2).round() * 0.2
df_geo['cluster_id'] = df_geo['lat_cluster'].astype(str) + '_' + df_geo['lon_cluster'].astype(str)

n_clusters = df_geo['cluster_id'].nunique()
print(f"✅ {n_clusters} zones géographiques identifiées")

# Statistiques clusters
cluster_sizes = df_geo['cluster_id'].value_counts()
print(f"\n📊 Statistiques zones:")
print(f"   Taille médiane: {cluster_sizes.median():.0f} POIs")
print(f"   Taille moyenne: {cluster_sizes.mean():.0f} POIs")
print(f"   Plus grande zone: {cluster_sizes.max()} POIs")
print(f"   Plus petite zone: {cluster_sizes.min()} POIs")

# Top 10 zones
print(f"\n🏆 Top 10 zones les plus denses:")
for i, (cluster, count) in enumerate(cluster_sizes.head(10).items(), 1):
    lat, lon = cluster.split('_')
    print(f"  {i:2d}. Zone {lat[:5]},{lon[:5]}: {count:4d} POIs")

# ============================================================================
# 3. ANALYSE DISTRIBUTION TYPES PAR CLUSTER
# ============================================================================
print("\n\n📊 3. ANALYSE DISTRIBUTION TYPES")
print("-" * 80)

# Distribution nationale des types (benchmark)
national_type_dist = df_geo['type'].value_counts(normalize=True)
print(f"Distribution nationale (top 10):")
for i, (poi_type, pct) in enumerate(national_type_dist.head(10).items(), 1):
    print(f"  {i:2d}. {poi_type:40s}: {pct*100:5.1f}%")

# Analyser chaque cluster
print(f"\nAnalyse des zones (clusters avec > 50 POIs)...")

cluster_analysis = []

for cluster_id in cluster_sizes[cluster_sizes > 50].index[:20]:  # Top 20 clusters
    cluster_pois = df_geo[df_geo['cluster_id'] == cluster_id]

    # Distribution types dans ce cluster
    cluster_type_dist = cluster_pois['type'].value_counts(normalize=True)

    # Comparer avec distribution nationale
    gaps = []
    for poi_type, national_pct in national_type_dist.head(15).items():
        cluster_pct = cluster_type_dist.get(poi_type, 0)
        gap_score = national_pct - cluster_pct  # Écart (positif = manque)

        if gap_score > 0.05:  # Gap significatif (>5%)
            gaps.append({
                'type': poi_type,
                'national_pct': national_pct * 100,
                'cluster_pct': cluster_pct * 100,
                'gap_score': gap_score * 100
            })

    if gaps:
        # Calculer score d'opportunité du cluster
        cluster_quality = cluster_pois['quality_score'].mean()
        cluster_density = len(cluster_pois)
        cluster_population = cluster_pois['has_description'].sum()  # Proxy

        cluster_analysis.append({
            'cluster_id': cluster_id,
            'lat': float(cluster_id.split('_')[0]),
            'lon': float(cluster_id.split('_')[1]),
            'n_pois': len(cluster_pois),
            'avg_quality': cluster_quality,
            'gaps': gaps[:3]  # Top 3 gaps
        })

print(f"✅ {len(cluster_analysis)} zones avec opportunités identifiées")

# ============================================================================
# 4. SCORING OPPORTUNITÉS
# ============================================================================
print("\n\n🎯 4. SCORING OPPORTUNITÉS")
print("-" * 80)

# Scorer chaque opportunité (simple heuristique)
opportunities = []

for cluster in cluster_analysis:
    for gap in cluster['gaps']:
        # Score opportunité basé sur:
        # - Gap importance (poids 40%)
        # - Densité zone (poids 30%)
        # - Qualité existante (poids 30%)

        gap_importance = gap['gap_score'] / 10  # Normaliser 0-10
        density_score = min(cluster['n_pois'] / 100, 10)  # Max 10
        quality_score = cluster['avg_quality'] / 10  # Normaliser 0-10

        opportunity_score = (
            gap_importance * 0.4 +
            density_score * 0.3 +
            quality_score * 0.3
        ) * 10  # Score 0-100

        # Classification
        if opportunity_score >= 70:
            level = "HIGH"
        elif opportunity_score >= 50:
            level = "MEDIUM"
        else:
            level = "LOW"

        opportunities.append({
            'zone': f"Zone {cluster['lat']:.1f},{cluster['lon']:.1f}",
            'lat': cluster['lat'],
            'lon': cluster['lon'],
            'type_manquant': gap['type'],
            'gap_pct': gap['gap_score'],
            'n_pois_zone': cluster['n_pois'],
            'avg_quality_zone': cluster['avg_quality'],
            'opportunity_score': opportunity_score,
            'opportunity_level': level,
            'raison': f"Gap de {gap['gap_score']:.1f}% vs national ({gap['national_pct']:.1f}% attendu vs {gap['cluster_pct']:.1f}% réel)"
        })

# Trier par score
opportunities_df = pd.DataFrame(opportunities)
opportunities_df = opportunities_df.sort_values('opportunity_score', ascending=False)

print(f"✅ {len(opportunities_df)} opportunités identifiées")
print(f"\n📈 Répartition:")
print(f"   HIGH:   {(opportunities_df['opportunity_level'] == 'HIGH').sum()}")
print(f"   MEDIUM: {(opportunities_df['opportunity_level'] == 'MEDIUM').sum()}")
print(f"   LOW:    {(opportunities_df['opportunity_level'] == 'LOW').sum()}")

# ============================================================================
# 5. TOP OPPORTUNITÉS
# ============================================================================
print("\n\n🌟 5. TOP 15 OPPORTUNITÉS")
print("-" * 80)

print(f"\n{'Rang':<6} {'Zone':<25} {'Type manquant':<30} {'Score':<8} {'Niveau':<8}")
print("-" * 95)

for i, row in opportunities_df.head(15).iterrows():
    print(f"{i+1:<6} {row['zone']:<25} {row['type_manquant'][:28]:<30} {row['opportunity_score']:6.1f}  {row['opportunity_level']:<8}")

# Afficher détails top 5
print(f"\n\n📋 DÉTAILS TOP 5 OPPORTUNITÉS")
print("=" * 80)

for rank, (i, row) in enumerate(opportunities_df.head(5).iterrows(), 1):
    print(f"\n{rank}. {row['type_manquant']} - {row['zone']}")
    print(f"   Score d'opportunité: {row['opportunity_score']:.1f}/100 ({row['opportunity_level']})")
    print(f"   POIs dans la zone: {row['n_pois_zone']}")
    print(f"   Qualité moyenne zone: {row['avg_quality_zone']:.1f}/100")
    print(f"   Gap détecté: {row['gap_pct']:.1f}%")
    print(f"   Raison: {row['raison']}")

# ============================================================================
# 6. SAUVEGARDE
# ============================================================================
print("\n\n💾 6. SAUVEGARDE")
print("-" * 80)

# Sauvegarder opportunités
output_dir = Path("../data/processed")
output_dir.mkdir(parents=True, exist_ok=True)

opportunities_file = output_dir / "opportunities.csv"
opportunities_df.to_csv(opportunities_file, index=False)
print(f"✅ Opportunités sauvegardées: {opportunities_file}")

# Sauvegarder aussi en JSON pour API
opportunities_json = output_dir / "opportunities.json"
with open(opportunities_json, 'w', encoding='utf-8') as f:
    json.dump(opportunities_df.head(50).to_dict('records'), f, indent=2, ensure_ascii=False)
print(f"✅ Top 50 en JSON: {opportunities_json}")

# Statistiques par type
print(f"\n📊 Statistiques par type de POI manquant:")
type_stats = opportunities_df.groupby('type_manquant').agg({
    'opportunity_score': 'mean',
    'zone': 'count'
}).sort_values('zone', ascending=False).head(10)

print(f"\n{'Type':<40} {'N zones':<10} {'Score moyen':<12}")
print("-" * 65)
for poi_type, row in type_stats.iterrows():
    print(f"{poi_type[:38]:<40} {row['zone']:<10.0f} {row['opportunity_score']:<12.1f}")

# ============================================================================
# RÉSUMÉ FINAL
# ============================================================================
print("\n\n" + "=" * 80)
print("✅ GAP DETECTOR - ANALYSE TERMINÉE")
print("=" * 80)

print(f"\n📊 Résultats:")
print(f"  • {n_clusters} zones géographiques analysées")
print(f"  • {len(cluster_analysis)} zones avec opportunités identifiées")
print(f"  • {len(opportunities_df)} opportunités business détectées")
print(f"  • {(opportunities_df['opportunity_level'] == 'HIGH').sum()} opportunités HIGH priority")

print(f"\n🎯 Insights clés:")
# Top 3 types manquants
top_missing = opportunities_df['type_manquant'].value_counts().head(3)
for i, (poi_type, count) in enumerate(top_missing.items(), 1):
    print(f"  {i}. {poi_type}: manquant dans {count} zones")

print(f"\n📈 Prochaine étape:")
print(f"  → Jours 10-11: API FastAPI")
print(f"  → Endpoints: /score-poi, /opportunities, /analyze-zone")

print("\n" + "=" * 80)
