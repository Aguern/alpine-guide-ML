"""
Modèle Event pour l'agenda des événements locaux
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class Event(BaseModel):
    """Modèle unifié pour les événements locaux"""
    id: str
    tenant_id: str
    
    # Temporal
    start_time: datetime
    end_time: datetime
    
    # Spatial
    latitude: float
    longitude: float
    
    # Content
    title: str
    description: str
    tags: List[str] = Field(default_factory=list)
    
    # Practical
    price: Optional[float] = None  # None = gratuit
    price_text: Optional[str] = None  # "Gratuit", "20-50€", etc.
    audience: Optional[str] = None  # "family", "adult", "all"
    url: Optional[str] = None  # Billetterie
    image_url: Optional[str] = None
    capacity: Optional[int] = None  # Nombre de places
    
    # Liens cartographiques
    gmaps_url: Optional[str] = None  # URL Google Maps générée automatiquement
    apple_url: Optional[str] = None  # URL Apple Plans générée automatiquement
    
    # Metadata
    source: str  # "apidae", "datatourisme", "calendar", "manual"
    kind: str = "event"  # Pour distinguer des POIs standards
    weather_dependent: bool = True  # Annulé si mauvais temps ?
    indoor: bool = False  # En intérieur ?
    
    # Scoring hints
    is_free: bool = Field(default=False)
    is_popular: bool = Field(default=False)
    is_recurring: bool = Field(default=False)  # Marché hebdo, etc.
    
    # Computed
    @property
    def is_upcoming(self) -> bool:
        """L'événement est-il à venir ?"""
        return self.start_time > datetime.now()
    
    @property
    def starts_today(self) -> bool:
        """L'événement commence-t-il aujourd'hui ?"""
        return self.start_time.date() == datetime.now().date()
    
    @property
    def display_time(self) -> str:
        """Format d'affichage de l'heure"""
        if self.starts_today:
            return f"Aujourd'hui {self.start_time.strftime('%H:%M')}"
        elif (self.start_time.date() - datetime.now().date()).days == 1:
            return f"Demain {self.start_time.strftime('%H:%M')}"
        else:
            return self.start_time.strftime("%d/%m %H:%M")
    
    def to_rag_document(self) -> dict:
        """Convertit l'événement pour l'indexation RAG"""
        return {
            "id": f"event_{self.id}",
            "kind": "event",
            "title": self.title,
            "content": f"{self.title}. {self.description}. Tags: {', '.join(self.tags)}",
            "metadata": {
                "tenant_id": self.tenant_id,
                "start_time": self.start_time.isoformat(),
                "end_time": self.end_time.isoformat(),
                "location": {"lat": self.latitude, "lon": self.longitude},
                "is_free": self.is_free,
                "audience": self.audience,
                "weather_dependent": self.weather_dependent,
                "indoor": self.indoor,
                "display_time": self.display_time,
                "url": self.url,
                "capacity": self.capacity
            }
        }


def create_mock_events(territory_slug: str) -> List[Event]:
    """Créer des événements de test pour un territoire"""
    now = datetime.now()
    
    mock_events = [
        Event(
            id="ev_1",
            tenant_id=territory_slug,
            title="Marché de Noël",
            description="Marché traditionnel avec produits locaux, vin chaud et animations",
            start_time=now.replace(hour=16, minute=0),
            end_time=now.replace(hour=21, minute=0),
            latitude=45.9237,
            longitude=6.8694,
            tags=["marché", "noël", "famille", "tradition"],
            price=None,
            price_text="Entrée gratuite",
            audience="all",
            is_free=True,
            weather_dependent=True,
            indoor=False,
            source="manual",
            is_popular=True
        ),
        Event(
            id="ev_2",
            tenant_id=territory_slug,
            title="Concert Jazz au Bistrot",
            description="Soirée jazz avec le quartet local Les Alpes Blues",
            start_time=now.replace(hour=20, minute=30),
            end_time=now.replace(hour=23, minute=0),
            latitude=45.9230,
            longitude=6.8700,
            tags=["concert", "jazz", "musique", "soirée"],
            price=15.0,
            price_text="15€",
            audience="adult",
            url="https://example.com/billetterie/jazz",
            is_free=False,
            weather_dependent=False,
            indoor=True,
            source="manual",
            capacity=80
        ),
        Event(
            id="ev_3",
            tenant_id=territory_slug,
            title="Randonnée guidée - Découverte faune alpine",
            description="Sortie nature avec guide pour observer marmottes et bouquetins",
            start_time=now.replace(hour=9, minute=0).replace(day=now.day+1),
            end_time=now.replace(hour=12, minute=0).replace(day=now.day+1),
            latitude=45.9350,
            longitude=6.8600,
            tags=["randonnée", "nature", "faune", "guide", "famille"],
            price=25.0,
            price_text="25€/adulte, 15€/enfant",
            audience="family",
            url="https://example.com/reservation/rando",
            is_free=False,
            weather_dependent=True,
            indoor=False,
            source="apidae",
            capacity=15
        ),
        Event(
            id="ev_4",
            tenant_id=territory_slug,
            title="Exposition Photo - Montagnes du Monde",
            description="Exposition de photographies des plus beaux sommets",
            start_time=now.replace(hour=10, minute=0),
            end_time=now.replace(hour=18, minute=0).replace(day=now.day+7),
            latitude=45.9240,
            longitude=6.8690,
            tags=["exposition", "photo", "culture", "art"],
            price=5.0,
            price_text="5€, gratuit -12 ans",
            audience="all",
            is_free=False,
            weather_dependent=False,
            indoor=True,
            source="datatourisme",
            is_recurring=True
        )
    ]
    
    return mock_events