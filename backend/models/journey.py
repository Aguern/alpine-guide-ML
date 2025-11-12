"""
Modeles pour la generation de parcours touristiques
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, time
from enum import Enum


class DifficultyLevel(str, Enum):
    """Niveau de difficulte des activites"""
    EASY = "easy"
    MODERATE = "moderate"
    HARD = "hard"


class JourneyType(str, Enum):
    """Type de parcours"""
    CULTURAL = "cultural"
    NATURE = "nature"
    GASTRONOMIC = "gastronomic"
    FAMILY = "family"
    ROMANTIC = "romantic"
    ADVENTURE = "adventure"
    RELAXATION = "relaxation"
    MIXED = "mixed"


class TimeSlot(str, Enum):
    """Creneaux horaires"""
    MORNING = "morning"      # 08:00-12:00
    AFTERNOON = "afternoon"  # 12:00-18:00
    EVENING = "evening"      # 18:00-22:00


class TransportMode(str, Enum):
    """Modes de transport"""
    WALKING = "walking"
    CYCLING = "cycling"
    CAR = "car"
    PUBLIC_TRANSPORT = "public_transport"


class JourneyPreferences(BaseModel):
    """Preferences utilisateur pour la generation de parcours"""
    duration_days: int = Field(..., ge=1, le=14, description="Duree du sejour en jours")
    journey_types: List[JourneyType] = Field(default=[JourneyType.MIXED], description="Types de parcours souhaites")
    difficulty_level: DifficultyLevel = Field(default=DifficultyLevel.MODERATE, description="Niveau de difficulte")
    transport_modes: List[TransportMode] = Field(default=[TransportMode.WALKING], description="Modes de transport preferes")
    budget_range: Optional[str] = Field(default=None, description="Fourchette de budget (low/medium/high)")
    accessibility_needs: bool = Field(default=False, description="Besoins d'accessibilite")
    family_friendly: bool = Field(default=False, description="Adapte aux familles")
    outdoor_preference: float = Field(default=0.5, ge=0, le=1, description="Preference exterieur (0=interieur, 1=exterieur)")
    group_size: int = Field(default=2, ge=1, le=20, description="Taille du groupe")


class POIRecommendation(BaseModel):
    """POI recommande avec contexte"""
    poi_id: str
    name: str
    type: str
    description: str
    estimated_duration: int = Field(..., description="Duree estimee en minutes")
    difficulty: DifficultyLevel
    best_time_slots: List[TimeSlot]
    coordinates: List[float] = Field(..., description="[longitude, latitude]")
    tags: List[str] = Field(default_factory=list)
    address: Optional[Dict[str, Any]] = None
    contact: Optional[Dict[str, Any]] = None
    booking_required: bool = Field(default=False)
    seasonal: bool = Field(default=False)
    weather_dependent: bool = Field(default=False)
    urgency_score: Optional[float] = Field(default=None, description="Score d'urgence pour recommandations d'urgence")


class JourneyDay(BaseModel):
    """Journee de parcours"""
    day_number: int = Field(..., ge=1)
    date: Optional[datetime] = None
    theme: Optional[str] = Field(default=None, description="Theme de la journee")
    morning_activities: List[POIRecommendation] = Field(default_factory=list)
    afternoon_activities: List[POIRecommendation] = Field(default_factory=list)
    evening_activities: List[POIRecommendation] = Field(default_factory=list)
    total_distance: float = Field(default=0.0, description="Distance totale en km")
    estimated_duration: int = Field(default=0, description="Duree totale en minutes")
    transport_suggestions: List[TransportMode] = Field(default_factory=list)
    weather_alternatives: Optional[List[POIRecommendation]] = Field(default=None)
    budget_estimate: Optional[float] = Field(default=None, description="Estimation budget en euros")


class Journey(BaseModel):
    """Parcours touristique complet"""
    id: Optional[str] = None
    territory_slug: str
    territory_name: str
    title: str
    description: str
    preferences: JourneyPreferences
    days: List[JourneyDay]
    total_duration: int = Field(..., description="Duree totale en jours")
    total_distance: float = Field(default=0.0, description="Distance totale en km")
    total_budget_estimate: Optional[float] = Field(default=None, description="Budget total estime")
    difficulty_level: DifficultyLevel
    best_seasons: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_public: bool = Field(default=False)
    rating: Optional[float] = Field(default=None, ge=0, le=5)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class JourneyRequest(BaseModel):
    """Requete de generation de parcours"""
    territory_slug: str
    preferences: JourneyPreferences
    weather_conditions: Optional[Dict[str, Any]] = Field(default=None)
    special_requirements: Optional[str] = Field(default=None)


class JourneyResponse(BaseModel):
    """Reponse avec parcours genere"""
    journey: Journey
    alternatives: Optional[List[POIRecommendation]] = Field(default=None)
    warnings: List[str] = Field(default_factory=list)
    tips: List[str] = Field(default_factory=list)


class SavedJourney(BaseModel):
    """Parcours sauvegarde"""
    id: str
    user_id: Optional[str] = None
    journey: Journey
    is_favorite: bool = Field(default=False)
    notes: Optional[str] = None
    visited_pois: List[str] = Field(default_factory=list, description="POIs deja visites")
    progress: float = Field(default=0.0, ge=0, le=1, description="Progression du parcours")
    shared_url: Optional[str] = None