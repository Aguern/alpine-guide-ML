from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime
import uuid

class TenantBranding(BaseModel):
    appName: str
    primaryColor: str
    logoUrl: str
    description: Optional[str] = None

class TenantFeatures(BaseModel):
    maxDays: int = 7
    enableWeather: bool = True
    enableChat: bool = True
    enableWeatherChat: bool = False
    defaultCenter: Dict[str, float]
    defaultZoom: int = 11

class TenantBoundaries(BaseModel):
    north: float
    south: float
    east: float
    west: float

class TenantConfig(BaseModel):
    branding: TenantBranding
    features: TenantFeatures
    boundaries: TenantBoundaries

class Tenant(BaseModel):
    id: Optional[str] = None
    slug: str
    name: str
    config: TenantConfig
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True