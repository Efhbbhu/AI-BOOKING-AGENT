# Geocoding and distance calculation utilities
import requests
import math
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timezone

class GeoService:
    """Geocoding and distance calculation service"""
    
    def __init__(self):
        self.nominatim_url = "https://nominatim.openstreetmap.org/search"
        self.headers = {
            'User-Agent': 'BookingAgent/1.0'
        }
        # In-memory cache to avoid repeated network lookups for the same location
        self._location_cache = {}
    
    def geocode_location(self, location_text: str, city: str = "Dubai") -> Dict[str, float]:
        """
        Convert location text to coordinates using Nominatim
        
        Args:
            location_text: Area name like "Business Bay", "JLT"
            city: City name (default: Dubai)
        
        Returns:
            Dictionary with lat, lng coordinates
        """
        # Known Dubai locations (fallback)
        dubai_locations = {
            # Existing locations
            'business bay': {'lat': 25.1870, 'lng': 55.2669},
            'jlt': {'lat': 25.0690, 'lng': 55.1398},
            'jumeirah lake towers': {'lat': 25.0690, 'lng': 55.1398},
            'marina': {'lat': 25.0777, 'lng': 55.1393},
            'dubai marina': {'lat': 25.0777, 'lng': 55.1393},
            'downtown': {'lat': 25.1972, 'lng': 55.2744},
            'downtown dubai': {'lat': 25.1972, 'lng': 55.2744},
            'deira': {'lat': 25.2711, 'lng': 55.3095},
            'jumeirah': {'lat': 25.2285, 'lng': 55.2708},
            'bur dubai': {'lat': 25.2631, 'lng': 55.3029},
            
            # New locations added
            'jumeirah beach': {'lat': 25.2285, 'lng': 55.2708},
            'umm suqeim': {'lat': 25.2022, 'lng': 55.2360},
            'al barsha': {'lat': 25.1167, 'lng': 55.1938},
            'mall of the emirates': {'lat': 25.1167, 'lng': 55.1938},
            'mirdif': {'lat': 25.2186, 'lng': 55.4115},
            'festival city': {'lat': 25.2186, 'lng': 55.4115},
            'dubai hills': {'lat': 25.1167, 'lng': 55.2465},
            'karama': {'lat': 25.2416, 'lng': 55.3095},
            'satwa': {'lat': 25.2392, 'lng': 55.2695},
            'trade centre': {'lat': 25.2392, 'lng': 55.2695},
            'world trade centre': {'lat': 25.2228, 'lng': 55.2829},
            'motor city': {'lat': 25.0451, 'lng': 55.2263},
            'sports city': {'lat': 25.0451, 'lng': 55.2263},
            'arabian ranches': {'lat': 25.0667, 'lng': 55.2667},
            'silicon oasis': {'lat': 25.1242, 'lng': 55.3847},
            'academic city': {'lat': 25.1242, 'lng': 55.3847},
            'dubai south': {'lat': 25.0204, 'lng': 55.1344},
            'jbr': {'lat': 25.0805, 'lng': 55.1396},
            'burj khalifa': {'lat': 25.1972, 'lng': 55.2744},
            'dubai mall': {'lat': 25.1972, 'lng': 55.2744},
            'al rigga': {'lat': 25.2711, 'lng': 55.3095},
            'difc': {'lat': 25.1870, 'lng': 55.2669}
        }
        
        # Check cache before doing any work
        cache_key = f"{location_text.lower().strip()}|{city.lower().strip()}"
        if cache_key in self._location_cache:
            return self._location_cache[cache_key].copy()

        # Check known locations first
        location_key = location_text.lower().strip()
        if location_key in dubai_locations:
            coords = dubai_locations[location_key]
            self._location_cache[cache_key] = coords
            return coords.copy()
        
        # Try Nominatim API
        try:
            params = {
                'q': f"{location_text}, {city}, UAE",
                'format': 'json',
                'limit': 1,
                'countrycodes': 'ae'
            }
            
            response = requests.get(
                self.nominatim_url, 
                params=params, 
                headers=self.headers,
                timeout=5
            )
            response.raise_for_status()
            
            data = response.json()
            if data:
                coords = {
                    'lat': float(data[0]['lat']),
                    'lng': float(data[0]['lon'])
                }
                self._location_cache[cache_key] = coords
                return coords.copy()
        
        except Exception as e:
            print(f"Geocoding failed for {location_text}: {e}")
        
        # Default to Business Bay if all fails
        fallback = dubai_locations['business bay']
        self._location_cache[cache_key] = fallback
        return fallback.copy()
    
    def calculate_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """
        Calculate distance between two coordinates using Haversine formula
        
        Returns:
            Distance in kilometers
        """
        # Convert to radians
        lat1_rad = math.radians(lat1)
        lng1_rad = math.radians(lng1)
        lat2_rad = math.radians(lat2)
        lng2_rad = math.radians(lng2)
        
        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlng = lng2_rad - lng1_rad
        
        a = (math.sin(dlat / 2) ** 2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng / 2) ** 2)
        
        c = 2 * math.asin(math.sqrt(a))
        
        # Earth's radius in kilometers
        earth_radius_km = 6371.0
        
        return earth_radius_km * c
    
    def find_nearest_providers(self, user_location: str, providers: List[Dict], limit: int = 3) -> List[Dict]:
        """
        Find nearest providers to user location
        
        Args:
            user_location: Text location like "Business Bay"
            providers: List of provider documents from Firestore
            limit: Maximum number of providers to return
        
        Returns:
            List of providers sorted by distance
        """
        user_coords = self.geocode_location(user_location)
        
        # Calculate distances
        providers_with_distance = []
        for provider in providers:
            if 'coords' in provider and provider['coords']:
                distance = self.calculate_distance(
                    user_coords['lat'], user_coords['lng'],
                    provider['coords']['lat'], provider['coords']['lng']
                )
                
                provider_copy = provider.copy()
                provider_copy['distance_km'] = round(distance, 2)
                providers_with_distance.append(provider_copy)
        
        # Sort by distance
        providers_with_distance.sort(key=lambda x: x['distance_km'])
        
        return providers_with_distance[:limit]
    
    def get_travel_time_estimate(self, distance_km: float) -> int:
        """
        Estimate travel time based on distance
        
        Args:
            distance_km: Distance in kilometers
        
        Returns:
            Estimated travel time in minutes
        """
        # Simple estimation: assume 30 km/h average speed in Dubai traffic
        average_speed_kmh = 30
        travel_time_hours = distance_km / average_speed_kmh
        travel_time_minutes = int(travel_time_hours * 60)
        
        # Minimum 5 minutes, maximum 60 minutes
        return max(5, min(60, travel_time_minutes))