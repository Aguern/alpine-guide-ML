"""
Models for external API configuration and data
"""
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class APIProvider(str, Enum):
    """Supported API providers"""
    OPENSTREETMAP = "openstreetmap"
    CULTURAL_GOV = "cultural_gov"
    TRANSPORT_LOCAL = "transport_local"
    EVENTBRITE = "eventbrite"
    TICKETMASTER = "ticketmaster"
    VIATOR = "viator"
    GEOAPIFY = "geoapify"
    FOURSQUARE = "foursquare"
    GOOGLE_PLACES = "google_places"
    YELP = "yelp"
    TRIPADVISOR = "tripadvisor"
    CUSTOM = "custom"


class APIAuthType(str, Enum):
    """API authentication types"""
    NONE = "none"
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    OAUTH2 = "oauth2"
    BASIC_AUTH = "basic_auth"
    CUSTOM_HEADER = "custom_header"


class APIConfig(BaseModel):
    """Configuration for an external API"""
    provider: APIProvider
    name: str
    base_url: str
    auth_type: APIAuthType
    
    # Authentication details (stored securely in env vars)
    api_key_env_var: Optional[str] = None
    client_id_env_var: Optional[str] = None
    client_secret_env_var: Optional[str] = None
    
    # Request configuration
    headers: Dict[str, str] = Field(default_factory=dict)
    default_params: Dict[str, Any] = Field(default_factory=dict)
    
    # Rate limiting
    rate_limit_per_second: Optional[float] = 10.0
    rate_limit_per_day: Optional[int] = 10000
    
    # Response configuration
    response_format: str = "json"  # json, xml, csv
    
    # Mapping configuration
    field_mappings: Dict[str, str] = Field(default_factory=dict)
    coordinate_fields: Dict[str, str] = Field(default_factory=lambda: {
        "latitude": "lat",
        "longitude": "lon"
    })
    
    # Features
    supports_bbox_search: bool = True
    supports_radius_search: bool = False
    supports_pagination: bool = True
    max_results_per_request: int = 100
    
    # Caching
    cache_ttl_seconds: int = 3600  # 1 hour default
    
    class Config:
        json_schema_extra = {
            "example": {
                "provider": "openstreetmap",
                "name": "OpenStreetMap Overpass API",
                "base_url": "https://overpass-api.de/api/interpreter",
                "auth_type": "none",
                "rate_limit_per_second": 1.0,
                "supports_bbox_search": True
            }
        }


class DataSource(BaseModel):
    """Represents a data source (combination of API + specific endpoint/dataset)"""
    api_config: APIConfig
    endpoint: str
    name: str
    description: Optional[str] = None
    
    # Query templates
    bbox_query_template: Optional[str] = None
    radius_query_template: Optional[str] = None
    
    # Data filters
    poi_type_filters: Dict[str, Any] = Field(default_factory=dict)
    required_fields: List[str] = Field(default_factory=list)
    
    # Quality settings
    min_data_quality_score: float = 0.5
    require_images: bool = False
    require_opening_hours: bool = False
    require_contact_info: bool = False


class ExternalPOI(BaseModel):
    """POI data from external source before transformation"""
    source_id: str
    source_name: str
    provider: APIProvider
    
    # Raw data
    raw_data: Dict[str, Any]
    
    # Extracted basic fields
    name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    # Metadata
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    quality_score: float = 0.0
    
    class Config:
        json_schema_extra = {
            "example": {
                "source_id": "node/12345",
                "source_name": "osm_restaurants",
                "provider": "openstreetmap",
                "raw_data": {
                    "id": 12345,
                    "lat": 45.899,
                    "lon": 6.129,
                    "tags": {
                        "name": "Restaurant Example",
                        "amenity": "restaurant"
                    }
                }
            }
        }


class CollectorResult(BaseModel):
    """Result from a collector run"""
    collector_name: str
    source_name: str
    success: bool
    
    # Statistics
    total_fetched: int = 0
    total_valid: int = 0
    total_imported: int = 0
    
    # Timing
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    
    # Errors
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    
    # Data
    pois: List[ExternalPOI] = Field(default_factory=list)
    
    class Config:
        json_schema_extra = {
            "example": {
                "collector_name": "OSMCollector",
                "source_name": "openstreetmap",
                "success": True,
                "total_fetched": 150,
                "total_valid": 145,
                "total_imported": 140,
                "started_at": "2024-01-01T10:00:00Z",
                "completed_at": "2024-01-01T10:02:30Z",
                "duration_seconds": 150.5
            }
        }