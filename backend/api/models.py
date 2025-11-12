#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TourismIQ API - Pydantic Models
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ============================================================================
# REQUEST MODELS
# ============================================================================

class POIScoreRequest(BaseModel):
    """Request pour scorer un POI"""
    name: Optional[str] = Field(None, description="Nom du POI")
    type: Optional[str] = Field(None, description="Type de POI")
    description: Optional[str] = Field(None, description="Description du POI")
    latitude: Optional[float] = Field(None, description="Latitude")
    longitude: Optional[float] = Field(None, description="Longitude")
    has_contact: Optional[bool] = Field(False, description="A des informations de contact")
    has_images: Optional[bool] = Field(False, description="A des images")
    has_opening_hours: Optional[bool] = Field(False, description="A des horaires d'ouverture")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Tour Eiffel",
                "type": "Monument",
                "description": "Monument emblématique de Paris, construit en 1889 pour l'Exposition universelle",
                "latitude": 48.8584,
                "longitude": 2.2945,
                "has_contact": True,
                "has_images": True,
                "has_opening_hours": True
            }
        }


class ZoneAnalysisRequest(BaseModel):
    """Request pour analyser une zone géographique"""
    latitude: float = Field(..., description="Latitude du centre de la zone")
    longitude: float = Field(..., description="Longitude du centre de la zone")
    radius_km: float = Field(5.0, description="Rayon d'analyse en km", ge=0.1, le=50.0)

    class Config:
        json_schema_extra = {
            "example": {
                "latitude": 48.8566,
                "longitude": 2.3522,
                "radius_km": 10.0
            }
        }


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class POIScoreResponse(BaseModel):
    """Réponse du scoring d'un POI"""
    quality_score: float = Field(..., description="Score de qualité (0-100)")
    quality_level: str = Field(..., description="Niveau de qualité (LOW/MEDIUM/GOOD/EXCELLENT)")
    confidence: float = Field(..., description="Niveau de confiance de la prédiction (0-1)")
    features_analysis: dict = Field(..., description="Analyse des features du POI")
    recommendations: List[str] = Field(..., description="Recommandations d'amélioration")

    class Config:
        json_schema_extra = {
            "example": {
                "quality_score": 85.3,
                "quality_level": "EXCELLENT",
                "confidence": 0.95,
                "features_analysis": {
                    "completeness": 90,
                    "richness": 85,
                    "context": 80
                },
                "recommendations": [
                    "Ajouter plus d'images",
                    "Enrichir la description"
                ]
            }
        }


class Opportunity(BaseModel):
    """Opportunité business détectée"""
    zone: str = Field(..., description="Identifiant de la zone")
    lat: float = Field(..., description="Latitude")
    lon: float = Field(..., description="Longitude")
    type_manquant: str = Field(..., description="Type de POI manquant")
    gap_pct: float = Field(..., description="Pourcentage de gap vs national")
    n_pois_zone: int = Field(..., description="Nombre de POIs dans la zone")
    avg_quality_zone: float = Field(..., description="Qualité moyenne de la zone")
    opportunity_score: float = Field(..., description="Score d'opportunité (0-100)")
    opportunity_level: str = Field(..., description="Niveau d'opportunité (LOW/MEDIUM/HIGH)")
    raison: str = Field(..., description="Raison du gap")


class OpportunitiesResponse(BaseModel):
    """Liste des opportunités business"""
    total: int = Field(..., description="Nombre total d'opportunités")
    opportunities: List[Opportunity] = Field(..., description="Liste des opportunités")

    class Config:
        json_schema_extra = {
            "example": {
                "total": 5,
                "opportunities": [
                    {
                        "zone": "Zone 48.9,2.3",
                        "lat": 48.9,
                        "lon": 2.3,
                        "type_manquant": "Restaurant",
                        "gap_pct": 15.2,
                        "n_pois_zone": 150,
                        "avg_quality_zone": 72.5,
                        "opportunity_score": 78.3,
                        "opportunity_level": "HIGH",
                        "raison": "Gap de 15.2% vs national"
                    }
                ]
            }
        }


class ZoneStats(BaseModel):
    """Statistiques d'une zone"""
    n_pois: int = Field(..., description="Nombre de POIs dans la zone")
    avg_quality: float = Field(..., description="Qualité moyenne des POIs")
    types_distribution: dict = Field(..., description="Distribution des types de POIs")
    top_pois: List[dict] = Field(..., description="Top 5 POIs de la zone")


class ZoneAnalysisResponse(BaseModel):
    """Réponse de l'analyse d'une zone"""
    center: dict = Field(..., description="Centre de la zone")
    radius_km: float = Field(..., description="Rayon analysé")
    stats: ZoneStats = Field(..., description="Statistiques de la zone")
    opportunities: List[Opportunity] = Field(..., description="Opportunités détectées dans la zone")

    class Config:
        json_schema_extra = {
            "example": {
                "center": {"lat": 48.8566, "lon": 2.3522},
                "radius_km": 10.0,
                "stats": {
                    "n_pois": 450,
                    "avg_quality": 68.5,
                    "types_distribution": {
                        "Restaurant": 120,
                        "Hotel": 80,
                        "Monument": 50
                    },
                    "top_pois": []
                },
                "opportunities": []
            }
        }


class BenchmarkResponse(BaseModel):
    """Statistiques nationales de référence"""
    total_pois: int = Field(..., description="Nombre total de POIs")
    avg_quality_score: float = Field(..., description="Score qualité moyen national")
    quality_distribution: dict = Field(..., description="Distribution par niveau de qualité")
    types_distribution: dict = Field(..., description="Distribution nationale des types")
    top_zones: List[dict] = Field(..., description="Top 10 zones les plus denses")

    class Config:
        json_schema_extra = {
            "example": {
                "total_pois": 50000,
                "avg_quality_score": 69.3,
                "quality_distribution": {
                    "LOW": 12500,
                    "MEDIUM": 18750,
                    "GOOD": 15000,
                    "EXCELLENT": 3750
                },
                "types_distribution": {
                    "PointOfInterest": 23.7,
                    "PlaceOfInterest": 18.5
                },
                "top_zones": []
            }
        }


class HealthResponse(BaseModel):
    """Health check de l'API"""
    status: str = Field(..., description="Status de l'API")
    timestamp: str = Field(..., description="Timestamp de la réponse")
    version: str = Field(..., description="Version de l'API")
    model_loaded: bool = Field(..., description="Modèle ML chargé")
    data_loaded: bool = Field(..., description="Données chargées")
