#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TourismIQ API - FastAPI Application

API REST pour le scoring de POIs touristiques et la détection d'opportunités business

Endpoints:
- POST /score-poi: Score un POI (0-100)
- GET /opportunities: Liste des opportunités business
- POST /analyze-zone: Analyse une zone géographique
- GET /benchmark: Statistiques nationales
- GET /health: Health check
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from datetime import datetime
from typing import Optional
import logging

from api.models import (
    POIScoreRequest, POIScoreResponse,
    ZoneAnalysisRequest, ZoneAnalysisResponse, ZoneStats,
    OpportunitiesResponse, Opportunity,
    BenchmarkResponse, HealthResponse
)

# ============================================================================
# CONFIGURATION
# ============================================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent
MODEL_PATH = BASE_DIR / "models/quality_scorer/scorer.pkl"
FEATURES_PATH = BASE_DIR / "models/quality_scorer/features.txt"
OPPORTUNITIES_PATH = BASE_DIR / "data/processed/opportunities.json"
POIS_PATH = BASE_DIR / "data/processed/features_ml.parquet"

# Global state
app_state = {
    "model": None,
    "features": None,
    "opportunities_df": None,
    "pois_df": None
}


# ============================================================================
# STARTUP / SHUTDOWN
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager - charge les modèles au démarrage"""
    logger.info("🚀 Starting TourismIQ API...")

    try:
        # Charger le modèle
        logger.info(f"Loading model from {MODEL_PATH}...")
        app_state["model"] = joblib.load(MODEL_PATH)
        logger.info("✅ Model loaded")

        # Charger les features
        logger.info(f"Loading features from {FEATURES_PATH}...")
        with open(FEATURES_PATH, 'r') as f:
            app_state["features"] = [line.strip() for line in f]
        logger.info(f"✅ {len(app_state['features'])} features loaded")

        # Charger les opportunités
        logger.info(f"Loading opportunities from {OPPORTUNITIES_PATH}...")
        app_state["opportunities_df"] = pd.read_json(OPPORTUNITIES_PATH)
        logger.info(f"✅ {len(app_state['opportunities_df'])} opportunities loaded")

        # Charger les POIs
        logger.info(f"Loading POIs from {POIS_PATH}...")
        app_state["pois_df"] = pd.read_parquet(POIS_PATH)
        logger.info(f"✅ {len(app_state['pois_df'])} POIs loaded")

        logger.info("✅ TourismIQ API ready!")

    except Exception as e:
        logger.error(f"❌ Error during startup: {e}")
        raise

    yield

    # Cleanup
    logger.info("👋 Shutting down TourismIQ API...")


# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="TourismIQ API",
    description="API de scoring de POIs touristiques et détection d'opportunités business",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def build_features_vector(poi_data: POIScoreRequest) -> pd.DataFrame:
    """Construit le vecteur de features pour un POI"""

    # Features de complétude
    feat_has_name = 1 if poi_data.name else 0
    feat_has_description = 1 if poi_data.description else 0
    feat_has_gps = 1 if poi_data.latitude and poi_data.longitude else 0
    feat_has_type = 1 if poi_data.type else 0

    # Contact features
    feat_has_email = 1 if poi_data.has_contact else 0
    feat_has_phone = 1 if poi_data.has_contact else 0
    feat_has_website = 1 if poi_data.has_contact else 0

    # Description length
    desc_length = len(poi_data.description) if poi_data.description else 0

    # Valeurs par défaut pour features contextuelles
    feat_latitude = poi_data.latitude if poi_data.latitude else 48.8566
    feat_longitude = poi_data.longitude if poi_data.longitude else 2.3522
    feat_nb_languages = 1  # Défaut
    feat_poi_density = 5.0  # Défaut

    # Score de complétude (0-100)
    completeness_score = (feat_has_name * 20 + feat_has_description * 30 +
                         feat_has_gps * 20 + feat_has_type * 15 +
                         feat_has_email * 5 + feat_has_phone * 5 + feat_has_website * 5)

    # Score de richesse (0-100)
    desc_quality = min(desc_length / 100, 10) if desc_length > 0 else 0
    richness_score = (desc_quality * 5 + (1 if poi_data.has_images else 0) * 10 +
                     (1 if poi_data.has_opening_hours else 0) * 10)

    # Score de contexte (0-100)
    context_score = feat_poi_density

    # Freshness score (0-100)
    freshness_score = 50.0  # Défaut

    # Créer le DataFrame avec les 16 features exactes attendues par le modèle
    features_dict = {
        'latitude': feat_latitude,
        'longitude': feat_longitude,
        'description_length': desc_length,
        'nb_languages': feat_nb_languages,
        'poi_density': feat_poi_density,
        'has_name': feat_has_name,
        'has_description': feat_has_description,
        'has_gps': feat_has_gps,
        'has_type': feat_has_type,
        'has_email': feat_has_email,
        'has_phone': feat_has_phone,
        'has_website': feat_has_website,
        'completeness_score': completeness_score,
        'richness_score': richness_score,
        'context_score': context_score,
        'freshness_score': freshness_score
    }

    return pd.DataFrame([features_dict])


def get_quality_level(score: float) -> str:
    """Détermine le niveau de qualité"""
    if score >= 80:
        return "EXCELLENT"
    elif score >= 60:
        return "GOOD"
    elif score >= 40:
        return "MEDIUM"
    else:
        return "LOW"


def get_recommendations(poi_data: POIScoreRequest, score: float) -> list:
    """Génère des recommandations d'amélioration"""
    recommendations = []

    if not poi_data.name:
        recommendations.append("Ajouter un nom au POI")

    if not poi_data.description:
        recommendations.append("Ajouter une description")
    elif len(poi_data.description) < 100:
        recommendations.append("Enrichir la description (minimum 100 caractères recommandé)")

    if not poi_data.latitude or not poi_data.longitude:
        recommendations.append("Ajouter les coordonnées GPS")

    if not poi_data.has_contact:
        recommendations.append("Ajouter des informations de contact")

    if not poi_data.has_images:
        recommendations.append("Ajouter des images")

    if not poi_data.has_opening_hours:
        recommendations.append("Ajouter les horaires d'ouverture")

    if score >= 80:
        recommendations.append("Excellent POI ! Maintenir la qualité")

    return recommendations


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcule la distance haversine entre deux points en km"""
    from math import radians, sin, cos, sqrt, atan2

    R = 6371  # Rayon de la Terre en km

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return R * c


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/", tags=["General"])
async def root():
    """Root endpoint"""
    return {
        "message": "TourismIQ API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "score_poi": "/score-poi",
            "opportunities": "/opportunities",
            "analyze_zone": "/analyze-zone",
            "benchmark": "/benchmark"
        }
    }


@app.get("/health", response_model=HealthResponse, tags=["General"])
async def health():
    """Health check de l'API"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        version="1.0.0",
        model_loaded=app_state["model"] is not None,
        data_loaded=app_state["pois_df"] is not None
    )


@app.post("/score-poi", response_model=POIScoreResponse, tags=["Scoring"])
async def score_poi(poi: POIScoreRequest):
    """
    Score un POI touristique (0-100)

    Utilise le modèle LightGBM entraîné pour prédire la qualité du POI
    en fonction de ses caractéristiques.
    """
    try:
        # Construire le vecteur de features
        features_df = build_features_vector(poi)

        # Aligner avec les features du modèle
        model_features = app_state["features"]
        X = features_df[model_features].fillna(0)

        # Prédiction
        score = float(app_state["model"].predict(X)[0])
        score = max(0, min(100, score))  # Clip 0-100

        # Niveau de qualité
        quality_level = get_quality_level(score)

        # Confidence (basé sur la qualité des features)
        n_features_present = sum([
            1 if poi.name else 0,
            1 if poi.description else 0,
            1 if poi.latitude and poi.longitude else 0,
            1 if poi.type else 0,
            1 if poi.has_contact else 0
        ])
        confidence = min(n_features_present / 5, 1.0)

        # Analyse des features
        features_analysis = {
            "completeness": float(features_df['completeness_score'].iloc[0]),
            "richness": float(features_df['richness_score'].iloc[0]),
            "context": float(features_df['context_score'].iloc[0])
        }

        # Recommandations
        recommendations = get_recommendations(poi, score)

        return POIScoreResponse(
            quality_score=round(score, 1),
            quality_level=quality_level,
            confidence=round(confidence, 2),
            features_analysis=features_analysis,
            recommendations=recommendations
        )

    except Exception as e:
        logger.error(f"Error scoring POI: {e}")
        raise HTTPException(status_code=500, detail=f"Error scoring POI: {str(e)}")


@app.get("/opportunities", response_model=OpportunitiesResponse, tags=["Opportunities"])
async def get_opportunities(
    limit: int = Query(20, description="Nombre max d'opportunités à retourner", ge=1, le=100),
    min_score: float = Query(0, description="Score minimum d'opportunité", ge=0, le=100),
    level: Optional[str] = Query(None, description="Niveau d'opportunité (LOW/MEDIUM/HIGH)")
):
    """
    Liste des opportunités business détectées

    Retourne les zones géographiques avec des gaps de marché identifiés
    par le Gap Detector.
    """
    try:
        df = app_state["opportunities_df"].copy()

        # Filtrer par score minimum
        if min_score > 0:
            df = df[df['opportunity_score'] >= min_score]

        # Filtrer par niveau
        if level:
            df = df[df['opportunity_level'] == level.upper()]

        # Limiter les résultats
        df = df.head(limit)

        # Convertir en liste d'Opportunity
        opportunities = [
            Opportunity(**row) for _, row in df.iterrows()
        ]

        return OpportunitiesResponse(
            total=len(opportunities),
            opportunities=opportunities
        )

    except Exception as e:
        logger.error(f"Error getting opportunities: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting opportunities: {str(e)}")


@app.post("/analyze-zone", response_model=ZoneAnalysisResponse, tags=["Analysis"])
async def analyze_zone(zone: ZoneAnalysisRequest):
    """
    Analyse une zone géographique

    Retourne les statistiques des POIs dans un rayon donné autour d'un point,
    ainsi que les opportunités business détectées dans cette zone.
    """
    try:
        df = app_state["pois_df"].copy()

        # Filtrer les POIs dans le rayon
        df = df[df['latitude'].notna() & df['longitude'].notna()].copy()
        df['distance_km'] = df.apply(
            lambda row: haversine_distance(
                zone.latitude, zone.longitude,
                row['latitude'], row['longitude']
            ),
            axis=1
        )
        df_zone = df[df['distance_km'] <= zone.radius_km]

        if len(df_zone) == 0:
            raise HTTPException(status_code=404, detail="Aucun POI trouvé dans cette zone")

        # Statistiques
        n_pois = len(df_zone)
        avg_quality = float(df_zone['quality_score'].mean())

        # Distribution des types
        types_dist = df_zone['type'].value_counts().head(10).to_dict()

        # Top 5 POIs
        top_pois_df = df_zone.nlargest(5, 'quality_score')
        top_pois = [
            {
                "name": row.get('name', 'N/A'),
                "type": row.get('type', 'N/A'),
                "quality_score": float(row['quality_score']),
                "latitude": float(row['latitude']),
                "longitude": float(row['longitude'])
            }
            for _, row in top_pois_df.iterrows()
        ]

        # Opportunités dans la zone
        opps_df = app_state["opportunities_df"].copy()
        opps_df['distance_km'] = opps_df.apply(
            lambda row: haversine_distance(
                zone.latitude, zone.longitude,
                row['lat'], row['lon']
            ),
            axis=1
        )
        opps_in_zone = opps_df[opps_df['distance_km'] <= zone.radius_km]

        opportunities = [
            Opportunity(**row) for _, row in opps_in_zone.iterrows()
        ]

        return ZoneAnalysisResponse(
            center={"lat": zone.latitude, "lon": zone.longitude},
            radius_km=zone.radius_km,
            stats=ZoneStats(
                n_pois=n_pois,
                avg_quality=round(avg_quality, 1),
                types_distribution=types_dist,
                top_pois=top_pois
            ),
            opportunities=opportunities
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing zone: {e}")
        raise HTTPException(status_code=500, detail=f"Error analyzing zone: {str(e)}")


@app.get("/benchmark", response_model=BenchmarkResponse, tags=["Statistics"])
async def get_benchmark():
    """
    Statistiques nationales de référence

    Retourne les statistiques agrégées sur l'ensemble des POIs
    pour servir de benchmark.
    """
    try:
        df = app_state["pois_df"].copy()

        # Stats globales
        total_pois = len(df)
        avg_quality = float(df['quality_score'].mean())

        # Distribution par qualité
        quality_dist = {
            "LOW": int((df['quality_score'] < 40).sum()),
            "MEDIUM": int(((df['quality_score'] >= 40) & (df['quality_score'] < 60)).sum()),
            "GOOD": int(((df['quality_score'] >= 60) & (df['quality_score'] < 80)).sum()),
            "EXCELLENT": int((df['quality_score'] >= 80).sum())
        }

        # Distribution des types (top 10)
        types_dist = (df['type'].value_counts(normalize=True) * 100).head(10).to_dict()
        types_dist = {k: round(v, 1) for k, v in types_dist.items()}

        # Top 10 zones (clusters)
        df_geo = df[df['latitude'].notna() & df['longitude'].notna()].copy()
        df_geo['lat_cluster'] = (df_geo['latitude'] / 0.2).round() * 0.2
        df_geo['lon_cluster'] = (df_geo['longitude'] / 0.2).round() * 0.2
        cluster_sizes = df_geo.groupby(['lat_cluster', 'lon_cluster']).size().sort_values(ascending=False).head(10)

        top_zones = [
            {
                "lat": float(lat),
                "lon": float(lon),
                "n_pois": int(count)
            }
            for (lat, lon), count in cluster_sizes.items()
        ]

        return BenchmarkResponse(
            total_pois=total_pois,
            avg_quality_score=round(avg_quality, 1),
            quality_distribution=quality_dist,
            types_distribution=types_dist,
            top_zones=top_zones
        )

    except Exception as e:
        logger.error(f"Error getting benchmark: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting benchmark: {str(e)}")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
