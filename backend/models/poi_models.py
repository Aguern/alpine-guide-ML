"""
Modèles pour les Points d'Intérêt (POI)
"""
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class POIType(str, Enum):
    """Types de POI standardisés"""
    # Culture
    MUSEUM = "museum"
    GALLERY = "gallery" 
    THEATER = "theater"
    CINEMA = "cinema"
    LIBRARY = "library"
    MONUMENT = "monument"
    RELIGIOUS = "religious"
    
    # Nature & Outdoor
    PARK = "park"
    GARDEN = "garden"
    LAKE = "lake"
    MOUNTAIN_PEAK = "mountain_peak"
    VIEWPOINT = "viewpoint"
    NATURAL_SITE = "natural_site"
    BEACH = "beach"
    TRAIL = "trail"
    
    # Food & Drink
    RESTAURANT = "restaurant"
    CAFE = "cafe"
    BAR = "bar"
    BREWERY = "brewery"
    WINERY = "winery"
    MARKET = "market"
    
    # Accommodation
    HOTEL = "hotel"
    HOSTEL = "hostel"
    CAMPING = "camping"
    BNB = "bnb"
    
    # Activities
    SPORT = "sport"
    ENTERTAINMENT = "entertainment"
    SHOPPING = "shopping"
    SPA = "spa"
    ADVENTURE = "adventure"
    
    # Services
    TRANSPORT = "transport"
    PARKING = "parking"
    TOURIST_INFO = "tourist_info"
    
    # Others
    OTHER = "other"


class POIAddress(BaseModel):
    """Adresse d'un POI"""
    street: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None


class POIContact(BaseModel):
    """Informations de contact d'un POI"""
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    social_media: Optional[Dict[str, str]] = None


class POI(BaseModel):
    """Modèle principal pour un Point d'Intérêt"""
    id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    type: POIType
    
    # Géolocalisation
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    
    # Informations détaillées
    address: Optional[POIAddress] = None
    contact: Optional[POIContact] = None
    
    # Métadonnées
    tags: List[str] = Field(default_factory=list)
    rating: Optional[float] = Field(None, ge=0, le=5)
    price_level: Optional[int] = Field(None, ge=1, le=4)  # 1=$ à 4=$$$$
    
    # Liens cartographiques
    gmaps_url: Optional[str] = Field(None, description="URL Google Maps générée automatiquement")
    apple_url: Optional[str] = Field(None, description="URL Apple Plans générée automatiquement")
    
    # Données techniques
    source: Optional[str] = None  # DataTourisme, OSM, etc.
    external_id: Optional[str] = None
    tenant_id: Optional[str] = None
    territory_id: Optional[str] = None
    
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    active: bool = True
    
    class Config:
        from_attributes = True
        use_enum_values = True


class POIFilter(BaseModel):
    """Filtres pour rechercher des POIs"""
    types: Optional[List[POIType]] = None
    tags: Optional[List[str]] = None
    min_rating: Optional[float] = None
    max_price_level: Optional[int] = None
    radius_km: Optional[float] = None
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None


class POICollection(BaseModel):
    """Collection de POIs avec métadonnées"""
    pois: List[POI]
    total_count: int
    filters_applied: Optional[POIFilter] = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)