#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TourismIQ - Entraînement Quality Scorer

Entraîne un modèle LightGBM pour prédire le quality_score (0-100)

Objectifs:
- R² > 0.75
- MAE < 10 points
- RMSE < 12 points
"""

import pandas as pd
import numpy as np
from pathlib import Path
import joblib
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.ensemble import GradientBoostingRegressor

print("=" * 80)
print("🤖 TOURISMIQ - ENTRAÎNEMENT QUALITY SCORER")
print("=" * 80)

# ============================================================================
# 1. CHARGEMENT DES DONNÉES
# ============================================================================
print("\n📂 1. CHARGEMENT DES DONNÉES")
print("-" * 80)

data_file = Path("../data/processed/features_ml.parquet")
df = pd.read_parquet(data_file)

print(f"✅ {len(df):,} POIs chargés")
print(f"   Features: {len(df.columns) - 1}")
print(f"   Target: quality_score")

# Statistiques target
print(f"\n📊 Statistiques target (quality_score):")
print(f"   Moyenne: {df['quality_score'].mean():.1f}")
print(f"   Médiane: {df['quality_score'].median():.1f}")
print(f"   Écart-type: {df['quality_score'].std():.1f}")
print(f"   Min: {df['quality_score'].min():.1f}, Max: {df['quality_score'].max():.1f}")

# ============================================================================
# 2. PRÉPARATION DONNÉES ML
# ============================================================================
print("\n\n⚙️  2. PRÉPARATION DONNÉES ML")
print("-" * 80)

# Features à utiliser (exclure IDs et target)
feature_cols = [col for col in df.columns if col not in [
    'uuid', 'name', 'type', 'quality_score'
]]

print(f"Features sélectionnées ({len(feature_cols)}):")
for i, col in enumerate(feature_cols, 1):
    print(f"  {i:2d}. {col}")

# Préparer X et y
X = df[feature_cols].copy()
y = df['quality_score'].copy()

# Gérer valeurs manquantes (remplacer par 0)
X = X.fillna(0)

print(f"\n✅ X shape: {X.shape}")
print(f"✅ y shape: {y.shape}")

# Split train/test (80/20)
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

print(f"\n📊 Split:")
print(f"   Train: {len(X_train):,} POIs ({len(X_train)/len(X)*100:.1f}%)")
print(f"   Test:  {len(X_test):,} POIs ({len(X_test)/len(X)*100:.1f}%)")

# ============================================================================
# 3. ENTRAÎNEMENT GRADIENT BOOSTING (scikit-learn)
# ============================================================================
print("\n\n🚀 3. ENTRAÎNEMENT GRADIENT BOOSTING")
print("-" * 80)

# Paramètres Gradient Boosting
params = {
    'n_estimators': 200,
    'learning_rate': 0.1,
    'max_depth': 5,
    'min_samples_split': 20,
    'min_samples_leaf': 15,
    'subsample': 0.8,
    'random_state': 42,
    'verbose': 1
}

print("Paramètres:")
for key, val in params.items():
    print(f"  • {key}: {val}")

print("\n🔄 Entraînement en cours...")

# Créer et entraîner le modèle
model = GradientBoostingRegressor(**params)
model.fit(X_train, y_train)

print(f"\n✅ Entraînement terminé")
print(f"   N estimators: {model.n_estimators}")
print(f"   Train score: {model.score(X_train, y_train):.4f}")

# ============================================================================
# 4. ÉVALUATION
# ============================================================================
print("\n\n📊 4. ÉVALUATION DU MODÈLE")
print("-" * 80)

# Prédictions
y_train_pred = model.predict(X_train)
y_test_pred = model.predict(X_test)

# Métriques train
train_mae = mean_absolute_error(y_train, y_train_pred)
train_rmse = np.sqrt(mean_squared_error(y_train, y_train_pred))
train_r2 = r2_score(y_train, y_train_pred)

# Métriques test
test_mae = mean_absolute_error(y_test, y_test_pred)
test_rmse = np.sqrt(mean_squared_error(y_test, y_test_pred))
test_r2 = r2_score(y_test, y_test_pred)

print("Performances Train:")
print(f"  • MAE:  {train_mae:.2f} points")
print(f"  • RMSE: {train_rmse:.2f} points")
print(f"  • R²:   {train_r2:.4f}")

print("\nPerformances Test:")
print(f"  • MAE:  {test_mae:.2f} points")
print(f"  • RMSE: {test_rmse:.2f} points")
print(f"  • R²:   {test_r2:.4f}")

# Vérifier objectifs
print("\n🎯 Objectifs:")
status_r2 = "✅" if test_r2 > 0.75 else "❌"
status_mae = "✅" if test_mae < 10 else "❌"
status_rmse = "✅" if test_rmse < 12 else "❌"

print(f"  {status_r2} R² > 0.75:      {test_r2:.4f}")
print(f"  {status_mae} MAE < 10:       {test_mae:.2f}")
print(f"  {status_rmse} RMSE < 12:      {test_rmse:.2f}")

# Distribution erreurs
errors = np.abs(y_test - y_test_pred)
print(f"\n📈 Distribution erreurs absolues (test):")
print(f"  • < 5 points:  {(errors < 5).sum():,} ({(errors < 5).sum() / len(errors) * 100:.1f}%)")
print(f"  • < 10 points: {(errors < 10).sum():,} ({(errors < 10).sum() / len(errors) * 100:.1f}%)")
print(f"  • < 15 points: {(errors < 15).sum():,} ({(errors < 15).sum() / len(errors) * 100:.1f}%)")
print(f"  • Max error:   {errors.max():.1f} points")

# ============================================================================
# 5. FEATURE IMPORTANCE
# ============================================================================
print("\n\n🔍 5. FEATURE IMPORTANCE")
print("-" * 80)

# Feature importance
feature_importance = pd.DataFrame({
    'feature': feature_cols,
    'importance': model.feature_importances_
}).sort_values('importance', ascending=False)

print("Top 10 features les plus importantes:")
for i, row in feature_importance.head(10).iterrows():
    print(f"  {row['feature']:30s}: {row['importance']:8.1f}")

# ============================================================================
# 6. SAUVEGARDE MODÈLE
# ============================================================================
print("\n\n💾 6. SAUVEGARDE MODÈLE")
print("-" * 80)

# Créer dossier models
models_dir = Path("../models/quality_scorer")
models_dir.mkdir(parents=True, exist_ok=True)

# Sauvegarder modèle avec joblib
model_pkl = models_dir / "scorer.pkl"
joblib.dump(model, model_pkl)
print(f"✅ Modèle sauvegardé: {model_pkl}")

# Sauvegarder liste features
features_file = models_dir / "features.txt"
with open(features_file, 'w') as f:
    for feat in feature_cols:
        f.write(f"{feat}\n")
print(f"✅ Features sauvegardées: {features_file}")

# Sauvegarder feature importance
importance_file = models_dir / "feature_importance.csv"
feature_importance.to_csv(importance_file, index=False)
print(f"✅ Feature importance sauvegardée: {importance_file}")

# Sauvegarder métriques
metrics = {
    'train_mae': train_mae,
    'train_rmse': train_rmse,
    'train_r2': train_r2,
    'test_mae': test_mae,
    'test_rmse': test_rmse,
    'test_r2': test_r2,
    'n_estimators': model.n_estimators
}

metrics_file = models_dir / "metrics.json"
import json
with open(metrics_file, 'w') as f:
    json.dump(metrics, f, indent=2)
print(f"✅ Métriques sauvegardées: {metrics_file}")

# ============================================================================
# 7. TEST PRÉDICTION
# ============================================================================
print("\n\n🧪 7. TEST PRÉDICTION")
print("-" * 80)

# Prendre quelques exemples
print("Exemples de prédictions (test set):\n")
print(f"{'POI':40s} {'Réel':>8s} {'Prédit':>8s} {'Erreur':>8s}")
print("-" * 70)

# Sélectionner exemples variés
sample_indices = [
    y_test.idxmax(),  # Best
    y_test.idxmin(),  # Worst
    y_test.sample(5, random_state=42).index.tolist()  # Random
]
sample_indices = [sample_indices[0], sample_indices[1]] + sample_indices[2]

for idx in sample_indices[:7]:
    poi_name = df.loc[idx, 'name'] if pd.notna(df.loc[idx, 'name']) else 'N/A'
    real_score = y_test.loc[idx]
    pred_score = y_test_pred[list(y_test.index).index(idx)]
    error = abs(real_score - pred_score)

    poi_name_short = poi_name[:37] + '...' if len(poi_name) > 40 else poi_name
    print(f"{poi_name_short:40s} {real_score:8.1f} {pred_score:8.1f} {error:8.1f}")

# ============================================================================
# RÉSUMÉ FINAL
# ============================================================================
print("\n\n" + "=" * 80)
print("✅ QUALITY SCORER - ENTRAÎNEMENT TERMINÉ")
print("=" * 80)

print(f"\n🎯 Performances finales (test set):")
print(f"  • R²:   {test_r2:.4f} {'✅' if test_r2 > 0.75 else '❌'}")
print(f"  • MAE:  {test_mae:.2f} points {'✅' if test_mae < 10 else '❌'}")
print(f"  • RMSE: {test_rmse:.2f} points {'✅' if test_rmse < 12 else '❌'}")

print(f"\n📦 Modèle sauvegardé dans: {models_dir}/")
print(f"  • scorer.pkl (modèle)")
print(f"  • features.txt (liste features)")
print(f"  • feature_importance.csv")
print(f"  • metrics.json")

print(f"\n📈 Prochaine étape:")
print(f"  → Jours 7-9: Gap Detector (HDBSCAN + Random Forest)")
print(f"  → Objectif: Détecter opportunités business par zone")

print("\n" + "=" * 80)
