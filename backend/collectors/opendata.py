"""
OpenStreetMap collector using Overpass API
Free API for extracting POIs from OpenStreetMap data
"""
from typing import List, Dict, Any, Optional, Tuple
import requests
import time
import logging
from datetime import datetime
import json

from .base_collector import BaseCollector, CollectedPOI, POIType

logger = logging.getLogger(__name__)


class OSMCollector(BaseCollector):
    """
    Collector for OpenStreetMap data via Overpass API
    
    Completely free, no authentication required.
    Rate limit: ~1 request per second to be respectful.
    """
    
    OVERPASS_URL = "https://overpass-api.de/api/interpreter"
    
    # Département 74 (Haute-Savoie) INSEE code
    HAUTE_SAVOIE_INSEE = "74"
    
    # OSM tag mapping to our POI types
    TAG_MAPPING = {
        # Cultural
        "amenity=museum": POIType.MUSEUM,
        "amenity=theatre": POIType.THEATER,
        "amenity=cinema": POIType.CINEMA,
        "amenity=library": POIType.LIBRARY,
        "tourism=museum": POIType.MUSEUM,
        "tourism=gallery": POIType.GALLERY,
        
        # Nature & Tourism
        "tourism=viewpoint": POIType.VIEWPOINT,
        "natural=peak": POIType.MOUNTAIN_PEAK,
        "leisure=park": POIType.PARK,
        "natural=water": POIType.LAKE,
        "tourism=attraction": POIType.NATURAL_SITE,
        
        # Food & Drink
        "amenity=restaurant": POIType.RESTAURANT,
        "amenity=cafe": POIType.CAFE,
        "amenity=bar": POIType.BAR,
        
        # Transport
        "highway=bus_stop": POIType.BUS_STOP,
        "railway=station": POIType.TRAIN_STATION,
        "amenity=parking": POIType.PARKING,
        "amenity=bicycle_rental": POIType.BIKE_RENTAL,
        
        # Accommodation
        "tourism=hotel": POIType.HOTEL,
        "tourism=hostel": POIType.HOSTEL,
        "tourism=camp_site": POIType.CAMPING,
        
        # Shopping & Services
        "shop": POIType.SHOP,
        "amenity=marketplace": POIType.MARKET,
        "tourism=information": POIType.TOURIST_INFO,
    }
    
    def get_source_name(self) -> str:
        return "openstreetmap"
    
    def collect(self, bounds: Dict[str, float]) -> List[CollectedPOI]:
        """
        Collect POIs from OpenStreetMap using Overpass API
        
        Uses department 74 (Haute-Savoie) filter for more precise results
        """
        logger.info(f"Starting OSM collection for bounds: {bounds}")
        
        # Build the Overpass query
        query = self._build_overpass_query(bounds)
        
        try:
            # Make the API request
            response = requests.post(
                self.OVERPASS_URL,
                data=query.encode('utf-8'),
                headers={'Content-Type': 'text/plain; charset=utf-8'},
                timeout=60
            )
            
            if response.status_code != 200:
                logger.error(f"Overpass API error: {response.status_code}")
                return []
            
            data = response.json()
            
            # Transform OSM elements to CollectedPOI
            pois = []
            for element in data.get('elements', []):
                poi = self._transform_osm_element(element)
                if poi and self.validate_poi(poi):
                    pois.append(poi)
            
            logger.info(f"Collected {len(pois)} valid POIs from OSM")
            
            # Rate limiting - be respectful
            time.sleep(1)
            
            return pois
            
        except requests.exceptions.Timeout:
            logger.error("Overpass API timeout")
            return []
        except Exception as e:
            logger.error(f"Error collecting from OSM: {e}")
            return []
    
    def validate_poi(self, poi: CollectedPOI) -> bool:
        """Validate OSM POI"""
        # Basic validation
        if not poi.name or not poi.lat or not poi.lon:
            return False
            
        # Check coordinates are valid
        if not (-90 <= poi.lat <= 90) or not (-180 <= poi.lon <= 180):
            return False
            
        return True
    
    def _build_overpass_query(self, bounds: Dict[str, float]) -> str:
        """Build Overpass QL query for department 74 within bounds"""
        
        # Use area filter for department 74 (more efficient)
        # This ensures we only get POIs in Haute-Savoie
        query = f"""
[out:json][timeout:60];
// Département 74 (Haute-Savoie)
area["ref:INSEE"="{self.HAUTE_SAVOIE_INSEE}"]->.hautesavoie;

// Collect POIs within department AND bounds
(
  // Restaurants and Food
  node["amenity"~"restaurant|cafe|bar|pub|fast_food|food_court"](area.hautesavoie)({bounds['south']},{bounds['west']},{bounds['north']},{bounds['east']});
  way["amenity"~"restaurant|cafe|bar|pub|fast_food"](area.hautesavoie)({bounds['south']},{bounds['west']},{bounds['north']},{bounds['east']});
  
  // Cultural
  node["amenity"~"museum|theatre|cinema|library|arts_centre"](area.hautesavoie)({bounds['south']},{bounds['west']},{bounds['north']},{bounds['east']});
  node["tourism"="museum"](area.hautesavoie)({bounds['south']},{bounds['west']},{bounds['north']},{bounds['east']});
  way["amenity"~"museum|theatre|cinema|library"](area.hautesavoie)({bounds['south']},{bounds['west']},{bounds['north']},{bounds['east']});
  
  // Tourism & Nature
  node["tourism"~"hotel|hostel|guest_house|apartment|chalet|viewpoint|attraction|information|picnic_site"](area.hautesavoie)({bounds['south']},{bounds['west']},{bounds['north']},{bounds['east']});
  node["natural"~"peak|water|beach"](area.hautesavoie)({bounds['south']},{bounds['west']},{bounds['north']},{bounds['east']});
  node["leisure"~"park|nature_reserve|swimming_pool"](area.hautesavoie)({bounds['south']},{bounds['west']},{bounds['north']},{bounds['east']});
  way["leisure"="park"](area.hautesavoie)({bounds['south']},{bounds['west']},{bounds['north']},{bounds['east']});
  
  // Sports
  node["sport"](area.hautesavoie)({bounds['south']},{bounds['west']},{bounds['north']},{bounds['east']});
  node["leisure"~"sports_centre|stadium"](area.hautesavoie)({bounds['south']},{bounds['west']},{bounds['north']},{bounds['east']});
  way["leisure"~"sports_centre|stadium|pitch"](area.hautesavoie)({bounds['south']},{bounds['west']},{bounds['north']},{bounds['east']});
  
  // Transport
  node["amenity"~"parking|bicycle_rental"](area.hautesavoie)({bounds['south']},{bounds['west']},{bounds['north']},{bounds['east']});
  node["highway"="bus_stop"](area.hautesavoie)({bounds['south']},{bounds['west']},{bounds['north']},{bounds['east']});
  node["railway"="station"](area.hautesavoie)({bounds['south']},{bounds['west']},{bounds['north']},{bounds['east']});
  node["aerialway"="station"](area.hautesavoie)({bounds['south']},{bounds['west']},{bounds['north']},{bounds['east']});
  
  // Shopping
  node["shop"~"supermarket|mall|department_store|gift|souvenirs"](area.hautesavoie)({bounds['south']},{bounds['west']},{bounds['north']},{bounds['east']});
  node["amenity"="marketplace"](area.hautesavoie)({bounds['south']},{bounds['west']},{bounds['north']},{bounds['east']});
);

// Output with tags
out body;
>;
out skel qt;
"""
        
        return query
    
    def _extract_poi_type(self, tags: Dict[str, str]) -> POIType:
        """Extract POI type from OSM tags"""
        # Check each tag mapping
        for osm_tag, poi_type in self.TAG_MAPPING.items():
            key, value = osm_tag.split('=', 1) if '=' in osm_tag else (osm_tag, None)
            
            if value:
                if tags.get(key) == value:
                    return poi_type
            else:
                if key in tags:
                    return poi_type
        
        # Default fallback
        return POIType.TOURIST_INFO
    
    def _transform_osm_element(self, element: Dict[str, Any]) -> Optional[CollectedPOI]:
        """Transform OSM element to CollectedPOI"""
        tags = element.get('tags', {})
        
        # Skip if no name
        if 'name' not in tags:
            return None
        
        # Extract coordinates
        if element['type'] == 'node':
            lat = element['lat']
            lon = element['lon']
        elif element['type'] == 'way' and 'center' in element:
            lat = element['center']['lat']
            lon = element['center']['lon']
        else:
            return None
        
        # Determine POI type
        poi_type = self._extract_poi_type(tags)
        
        # Build POI
        poi = CollectedPOI(
            external_id=f"osm_{element['type']}_{element['id']}",
            source=self.get_source_name(),
            name=tags['name'],
            lat=lat,
            lon=lon,
            poi_type=poi_type,
            description=self._build_description(tags),
            address=self._extract_address(tags),
            city=tags.get('addr:city', tags.get('addr:municipality')),
            postal_code=tags.get('addr:postcode'),
            website=tags.get('website', tags.get('contact:website')),
            phone=tags.get('phone', tags.get('contact:phone')),
            email=tags.get('email', tags.get('contact:email')),
            opening_hours=self._extract_opening_hours(tags.get('opening_hours')),
            tags=self._extract_tags_list(tags),
            amenities=self._extract_amenities(tags),
            accessibility=self._extract_accessibility(tags),
            price_range=self._extract_price_range(tags),
            raw_data=tags
        )
        
        return poi
    
    def _build_description(self, tags: Dict[str, str]) -> Optional[str]:
        """Build description from OSM tags"""
        parts = []
        
        # Add cuisine type for restaurants
        if tags.get('cuisine'):
            parts.append(f"Cuisine: {tags['cuisine'].replace('_', ' ')}")
        
        # Add description if available
        if tags.get('description'):
            parts.append(tags['description'])
        elif tags.get('description:fr'):
            parts.append(tags['description:fr'])
        
        # Add tourism type
        if tags.get('tourism'):
            parts.append(f"Type: {tags['tourism'].replace('_', ' ')}")
        
        # Add sport type
        if tags.get('sport'):
            parts.append(f"Sport: {tags['sport'].replace('_', ' ')}")
        
        return ' | '.join(parts) if parts else None
    
    def _extract_address(self, tags: Dict[str, str]) -> Optional[str]:
        """Extract address from OSM tags"""
        parts = []
        
        if tags.get('addr:housenumber'):
            parts.append(tags['addr:housenumber'])
        
        if tags.get('addr:street'):
            parts.append(tags['addr:street'])
        elif tags.get('addr:place'):
            parts.append(tags['addr:place'])
        
        return ' '.join(parts) if parts else None
    
    def _extract_tags_list(self, osm_tags: Dict[str, str]) -> List[str]:
        """Extract relevant tags for categorization"""
        tags = []
        
        # Add main categories
        for key in ['amenity', 'tourism', 'leisure', 'sport', 'natural', 'shop']:
            if key in osm_tags:
                tags.append(osm_tags[key].replace('_', ' '))
        
        # Add cuisine types
        if 'cuisine' in osm_tags:
            cuisines = osm_tags['cuisine'].split(';')
            tags.extend([c.strip() for c in cuisines])
        
        # Add specific tags
        if osm_tags.get('historic') == 'yes':
            tags.append('historic')
        
        if osm_tags.get('wheelchair') == 'yes':
            tags.append('accessible')
        
        return list(set(tags))
    
    def _extract_amenities(self, tags: Dict[str, str]) -> List[str]:
        """Extract amenities from OSM tags"""
        amenities = []
        
        amenity_tags = [
            'wheelchair', 'toilets', 'parking', 'internet_access',
            'wifi', 'outdoor_seating', 'terrace', 'garden',
            'playground', 'changing_table'
        ]
        
        for tag in amenity_tags:
            if tags.get(tag) in ['yes', 'true', '1']:
                amenities.append(tag.replace('_', ' '))
        
        return amenities
    
    def _extract_accessibility(self, tags: Dict[str, str]) -> Dict[str, bool]:
        """Extract accessibility information"""
        return {
            'wheelchair': tags.get('wheelchair') == 'yes',
            'wheelchair_toilets': tags.get('toilets:wheelchair') == 'yes',
            'hearing_loop': tags.get('hearing_loop') == 'yes',
            'tactile_paving': tags.get('tactile_paving') == 'yes'
        }
    
    def _extract_price_range(self, tags: Dict[str, str]) -> Optional[str]:
        """Extract price range from tags"""
        # OSM uses price_range tag with values: inexpensive, moderate, expensive, very_expensive
        price_map = {
            'inexpensive': '€',
            'moderate': '€€',
            'expensive': '€€€',
            'very_expensive': '€€€€'
        }
        
        osm_price = tags.get('price_range')
        return price_map.get(osm_price)
    
    def _extract_opening_hours(self, osm_hours: str) -> Optional[Dict[str, List[Tuple[str, str]]]]:
        """Parse OSM opening_hours format (simplified)"""
        if not osm_hours:
            return None
        
        # Common simple formats
        if osm_hours.lower() == '24/7':
            hours = {}
            for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
                hours[day] = [("00:00", "23:59")]
            return hours
        
        # For complex formats, return None (would need proper parser)
        # In production, use python-openinghours library
        return None