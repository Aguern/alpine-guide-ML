"""
Modèles pour la gestion des partenaires et intégrations externes
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from enum import Enum
from pydantic import BaseModel, Field
# Removed SQLAlchemy imports as we use Supabase
# from sqlalchemy import Column, String, Integer, DateTime, Boolean, JSON, Text
# from sqlalchemy.ext.declarative import declarative_base
# Base = declarative_base()

class PartnerTier(str, Enum):
    """Paliers d'abonnement partenaire"""
    STARTER = "starter"
    PROFESSIONAL = "professional" 
    ENTERPRISE = "enterprise"

class PartnerStatus(str, Enum):
    """Statut du partenaire"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    TRIAL = "trial"

class PartnerEndpoint(str, Enum):
    """Endpoints disponibles par palier"""
    CHAT = "chat"
    WEATHER_ALERTS = "weather_alerts"
    NOTIFICATIONS = "notifications"
    SEMANTIC_SEARCH = "semantic_search"
    ANALYTICS = "analytics"
    JOURNEY_PLANNING = "journey_planning"

# Configuration des accès par palier
TIER_PERMISSIONS = {
    PartnerTier.STARTER: [
        PartnerEndpoint.CHAT
    ],
    PartnerTier.PROFESSIONAL: [
        PartnerEndpoint.CHAT,
        PartnerEndpoint.WEATHER_ALERTS,
        PartnerEndpoint.NOTIFICATIONS
    ],
    PartnerTier.ENTERPRISE: [
        PartnerEndpoint.CHAT,
        PartnerEndpoint.WEATHER_ALERTS,
        PartnerEndpoint.NOTIFICATIONS,
        PartnerEndpoint.SEMANTIC_SEARCH,
        PartnerEndpoint.ANALYTICS,
        PartnerEndpoint.JOURNEY_PLANNING
    ]
}

# Limites par palier (requêtes par heure)
TIER_RATE_LIMITS = {
    PartnerTier.STARTER: 100,
    PartnerTier.PROFESSIONAL: 1000,
    PartnerTier.ENTERPRISE: 10000
}

# Modèles SQLAlchemy remplacés par des modèles Pydantic pour Supabase
# Les tables sont créées via les migrations SQL

# class Partner(Base): -- Removed as we use Supabase directly
# class PartnerUsage(Base): -- Removed as we use Supabase directly

# Modèles Pydantic pour l'API

class PartnerCreate(BaseModel):
    """Modèle pour créer un nouveau partenaire"""
    name: str = Field(..., min_length=1, max_length=255)
    company: Optional[str] = Field(None, max_length=255)
    email: str = Field(..., pattern=r'^[^@]+@[^@]+\.[^@]+$')
    allowed_tenants: List[str] = Field(..., description="Liste des tenants autorisés pour ce partenaire")
    tier: PartnerTier = PartnerTier.STARTER
    allowed_territories: List[str] = []
    webhook_url: Optional[str] = None

class PartnerUpdate(BaseModel):
    """Modèle pour mettre à jour un partenaire"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    company: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, pattern=r'^[^@]+@[^@]+\.[^@]+$')
    tier: Optional[PartnerTier] = None
    status: Optional[PartnerStatus] = None
    allowed_territories: Optional[List[str]] = None
    allowed_tenants: Optional[List[str]] = None
    custom_config: Optional[Dict[str, Any]] = None
    webhook_url: Optional[str] = None

class PartnerResponse(BaseModel):
    """Modèle de réponse pour un partenaire"""
    id: str
    name: str
    company: Optional[str] = None
    email: str
    tier: PartnerTier
    status: PartnerStatus
    allowed_territories: List[str]
    allowed_tenants: List[str]
    
    # Informations d'accès
    api_key: str
    permissions: List[PartnerEndpoint]
    rate_limit_per_hour: int
    
    # Statistiques
    total_requests: int
    last_request_at: Optional[datetime] = None
    
    # Dates
    created_at: datetime
    trial_ends_at: Optional[datetime] = None
    subscription_ends_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class PartnerStats(BaseModel):
    """Statistiques d'utilisation d'un partenaire"""
    partner_id: str
    period_start: datetime
    period_end: datetime
    
    total_requests: int
    requests_by_endpoint: Dict[str, int]
    requests_by_territory: Dict[str, int]
    average_response_time_ms: float
    error_rate_percent: float
    
    daily_breakdown: List[Dict[str, Any]]

class APIUsageRequest(BaseModel):
    """Modèle pour enregistrer l'utilisation d'API"""
    partner_id: str
    endpoint: str
    territory_slug: Optional[str] = None
    response_time_ms: int
    status_code: int
    error_message: Optional[str] = None

# Fonctions utilitaires

def get_partner_permissions(tier: PartnerTier) -> List[PartnerEndpoint]:
    """Retourne les permissions pour un palier donné"""
    return TIER_PERMISSIONS.get(tier, [])

def get_partner_rate_limit(tier: PartnerTier) -> int:
    """Retourne la limite de requêtes pour un palier donné"""
    return TIER_RATE_LIMITS.get(tier, 100)

def is_partner_in_trial(partner_data: Dict[str, Any]) -> bool:
    """Vérifie si un partenaire est encore en période d'essai"""
    trial_ends_at = partner_data.get('trial_ends_at')
    if not trial_ends_at:
        return False
    trial_date = datetime.fromisoformat(trial_ends_at.replace('Z', '+00:00'))
    return datetime.utcnow() < trial_date

def is_partner_subscription_active(partner_data: Dict[str, Any]) -> bool:
    """Vérifie si l'abonnement du partenaire est actif"""
    if partner_data.get('status') != PartnerStatus.ACTIVE.value:
        return False
    
    subscription_ends_at = partner_data.get('subscription_ends_at')
    if subscription_ends_at:
        sub_date = datetime.fromisoformat(subscription_ends_at.replace('Z', '+00:00'))
        return datetime.utcnow() < sub_date
    
    return True

def can_partner_access_endpoint(partner, endpoint: PartnerEndpoint) -> bool:
    """Vérifie si un partenaire peut accéder à un endpoint"""
    # Support à la fois dict et PartnerResponse
    if hasattr(partner, 'status'):  # PartnerResponse object
        if partner.status == PartnerStatus.SUSPENDED:
            return False
        tier = partner.tier
        allowed_endpoints = get_partner_permissions(tier)
        return endpoint in allowed_endpoints
    else:  # Dict data
        if partner.get('status') == PartnerStatus.SUSPENDED.value:
            return False
        
        # Vérifier la période d'essai ou l'abonnement
        if not (is_partner_in_trial(partner) or is_partner_subscription_active(partner)):
            return False
        
        # Vérifier les permissions du palier
        tier = PartnerTier(partner.get('tier', 'starter'))
        allowed_endpoints = get_partner_permissions(tier)
        return endpoint in allowed_endpoints

def can_partner_access_territory(partner, territory_slug: str) -> bool:
    """Vérifie si un partenaire peut accéder à un territoire"""
    # Support à la fois dict et PartnerResponse
    if hasattr(partner, 'allowed_territories'):  # PartnerResponse object
        allowed_territories = partner.allowed_territories
    else:  # Dict data
        allowed_territories = partner.get('allowed_territories', [])
    
    if not allowed_territories:
        return True  # Accès à tous les territoires si aucune restriction
    
    return territory_slug in allowed_territories