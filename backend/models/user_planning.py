"""
Modèles pour la planification utilisateur et notifications météo
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime, date, time
from enum import Enum


class ActivityStatus(str, Enum):
    """Status des activités planifiées"""
    PLANNED = "planned"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    WEATHER_MODIFIED = "weather_modified"


class WeatherRisk(str, Enum):
    """Niveaux de risque météo"""
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    SEVERE = "severe"


class NotificationLevel(str, Enum):
    """Niveaux de notification"""
    INFO = "info"
    WARNING = "warning"
    ALERT = "alert"
    EMERGENCY = "emergency"


class PlannedActivity(BaseModel):
    """Activité planifiée par un utilisateur"""
    id: str
    user_id: str
    poi_id: str
    poi_name: str
    
    # Planification temporelle
    planned_date: date
    planned_start_time: Optional[time] = None
    planned_end_time: Optional[time] = None
    estimated_duration_minutes: int = 120
    
    # Localisation
    location: Dict[str, float]  # lat, lng
    address: Optional[str] = None
    
    # Caractéristiques activité
    activity_type: str  # nature, cultural, food, sport, etc.
    is_outdoor: bool = True
    weather_sensitive: bool = True
    cancellable: bool = True
    
    # Status et modifications
    status: ActivityStatus = ActivityStatus.PLANNED
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_modified: datetime = Field(default_factory=datetime.utcnow)
    
    # Métadonnées
    notes: Optional[str] = None
    alternatives_accepted: bool = True
    notification_preferences: Dict[str, bool] = Field(default_factory=lambda: {
        "weather_changes": True,
        "alternatives": True,
        "reminders": True
    })
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "activity_001",
                "user_id": "user_123",
                "poi_id": "poi_456",
                "poi_name": "Randonnée Semnoz",
                "planned_date": "2024-07-15",
                "planned_start_time": "09:00",
                "planned_end_time": "16:00",
                "activity_type": "nature",
                "is_outdoor": True,
                "weather_sensitive": True
            }
        }


class UserProfile(BaseModel):
    """Profil utilisateur pour personnalisation météo"""
    user_id: str
    
    # Préférences météo
    weather_preferences: Dict[str, Any] = Field(default_factory=lambda: {
        "min_temperature": 5,  # °C
        "max_wind_speed": 30,  # km/h
        "rain_tolerance": "light",  # none, light, moderate, heavy
        "snow_activities": False,
        "storm_alerts": True
    })
    
    # Préférences notifications
    notification_preferences: Dict[str, Any] = Field(default_factory=lambda: {
        "push_enabled": True,
        "email_enabled": False,
        "advance_hours": [24, 6, 1],  # notifications 24h, 6h, 1h avant
        "quiet_hours": {"start": "22:00", "end": "07:00"},
        "weekend_only": False
    })
    
    # Zones d'intérêt
    favorite_territories: List[str] = []
    favorite_activity_types: List[str] = []
    
    # Configuration
    timezone: str = "Europe/Paris"
    language: str = "fr"
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_active: datetime = Field(default_factory=datetime.utcnow)


class WeatherAlert(BaseModel):
    """Alerte météo pour une activité"""
    id: str
    user_id: str
    activity_id: str
    
    # Détails de l'alerte
    alert_type: str  # rain, storm, wind, temperature, snow
    risk_level: WeatherRisk
    notification_level: NotificationLevel
    
    # Timing
    weather_start: datetime
    weather_end: datetime
    activity_impact_start: datetime
    activity_impact_end: datetime
    
    # Messages
    title: str
    message: str
    recommendations: List[str] = []
    alternatives: List[Dict[str, Any]] = []
    
    # Status
    sent_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    dismissed: bool = False
    
    # Données météo
    weather_data: Dict[str, Any] = {}
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "alert_001",
                "user_id": "user_123",
                "activity_id": "activity_001",
                "alert_type": "storm",
                "risk_level": "high",
                "notification_level": "alert",
                "title": "⛈️ Orage prévu sur votre randonnée",
                "message": "Orage violent prévu 14h-16h sur le Semnoz. Recommandation : reporter ou choisir alternative couverte.",
                "recommendations": [
                    "Reporter la randonnée à demain matin",
                    "Choisir le Musée d'Annecy comme alternative",
                    "Partir plus tôt (avant 13h) pour éviter l'orage"
                ]
            }
        }


class UserJourney(BaseModel):
    """Voyage/séjour complet d'un utilisateur"""
    id: str
    user_id: str
    
    # Détails du séjour
    territory_slug: str
    title: str
    start_date: date
    end_date: date
    
    # Planification
    activities: List[PlannedActivity] = []
    generated_journey_id: Optional[str] = None  # Lien vers le parcours IA généré
    
    # Préférences séjour
    group_size: int = 2
    group_type: str = "couple"  # family, friends, solo, business
    budget_range: Optional[str] = None
    
    # Monitoring météo
    weather_monitoring_enabled: bool = True
    last_weather_check: Optional[datetime] = None
    active_alerts: List[str] = []  # IDs des alertes actives
    
    # Métadonnées
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_modified: datetime = Field(default_factory=datetime.utcnow)
    
    def get_outdoor_activities(self) -> List[PlannedActivity]:
        """Retourne les activités extérieures sensibles à la météo"""
        return [a for a in self.activities if a.is_outdoor and a.weather_sensitive]
    
    def get_activities_for_date(self, target_date: date) -> List[PlannedActivity]:
        """Retourne les activités prévues pour une date donnée"""
        return [a for a in self.activities if a.planned_date == target_date]


class NotificationRule(BaseModel):
    """Règle de notification météo"""
    id: str
    
    # Conditions météo
    weather_conditions: Dict[str, Any]  # rain > 5mm, wind > 50km/h, etc.
    activity_types: List[str]  # types d'activités concernées
    
    # Timing
    advance_hours: List[int] = [24, 6, 1]  # heures avant l'activité
    
    # Notification
    notification_level: NotificationLevel
    message_template: str
    
    # Alternatives automatiques
    suggest_alternatives: bool = True
    alternative_types: List[str] = ["indoor", "covered", "same_area"]
    
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)