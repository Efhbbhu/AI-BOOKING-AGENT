# Tools for the booking agent
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta
import json

from firebase import FirestoreClient
from geo import GeoService

DUBAI_TZ = timezone(timedelta(hours=4))

class AvailabilityTool:
    """Tool to check service availability"""
    
    def __init__(self):
        self.firestore = FirestoreClient()
    
    def _parse_datetime_robust(self, date_string):
        """
        Robust datetime parser that handles multiple formats:
        - ISO format: "2025-10-02T17:00:00+00:00" or "2025-10-02T17:00:00Z"
        - GMT format: "Thu, 02 Oct 2025 17:00:00 GMT"
        """
        if not date_string:
            return None
        
        import re
        
        # Handle GMT format first (the actual problem)
        if 'GMT' in str(date_string):
            try:
                # Parse format like "Thu, 02 Oct 2025 17:00:00 GMT"
                cleaned = re.sub(r'^[A-Za-z]+,\s*', '', str(date_string))  # Remove "Thu, "
                cleaned = cleaned.replace(' GMT', '')  # Remove " GMT"
                
                # Parse the remaining: "02 Oct 2025 17:00:00"
                dt = datetime.strptime(cleaned, '%d %b %Y %H:%M:%S')
                
                # Add UTC timezone info
                dt = dt.replace(tzinfo=timezone.utc)
                return dt
                
            except Exception as e:
                print(f"GMT parsing failed for '{date_string}': {e}")
                return None
        
        # Handle ISO format (current expectation)
        elif 'T' in str(date_string):
            try:
                return datetime.fromisoformat(str(date_string).replace('Z', '+00:00'))
            except Exception as e:
                print(f"ISO parsing failed for '{date_string}': {e}")
                return None
        
        # Handle datetime objects
        elif isinstance(date_string, datetime):
            return date_string
            
        else:
            print(f"Unknown datetime format: '{date_string}'")
            return None
        
    def run(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Check availability for a service
        
        Args:
            params: Dictionary with service_type, provider_id, preferred_date, preferred_time
        """
        try:
            service_type = params.get("service_type", "manicure")
            provider_id = params.get("provider_id")
            preferred_date = params.get("preferred_date", "today")
            preferred_time = params.get("preferred_time", "afternoon")
            
            if not provider_id:
                print("Warning: No provider_id provided to AvailabilityTool")
                return []
            
            print(f"AvailabilityTool: Checking slots for provider {provider_id}, service {service_type}")
            
            # Get available slots from Firestore
            available_slots = self.firestore.get_available_slots(
                provider_id=provider_id,
                service_type=service_type,
                date_filter=preferred_date
            )
            
            # Remove duplicates first
            unique_slots = self._remove_duplicate_slots(available_slots)
            print(f"AvailabilityTool: Removed duplicates: {len(available_slots)} -> {len(unique_slots)} slots")

            # Filter by time preference
            print(f"AvailabilityTool: Before filtering: {len(unique_slots)} slots")
            print(f"AvailabilityTool: Time preference: '{preferred_time}'")
            
            # Debug: show what slots we have before filtering
            for i, slot in enumerate(available_slots[:3]):
                start_time = self._parse_datetime_robust(slot.get("start"))
                if start_time:
                    print(f"  Slot {i+1}: {start_time.strftime('%H:%M')} ({start_time.hour})")
            
            filtered_slots = self._filter_by_time_preference(unique_slots, preferred_time)
            
            print(f"AvailabilityTool: After filtering: {len(filtered_slots)} slots")
            
            # Ensure we always return exactly 3 slots
            if len(filtered_slots) < 3:
                print(f"⚠️  Only {len(filtered_slots)} filtered slots, need 3. Adding fallback slots...")
                # Add more slots from unique_slots to reach 3
                for slot in unique_slots:
                    if slot not in filtered_slots and len(filtered_slots) < 3:
                        filtered_slots.append(slot)
                print(f"AvailabilityTool: After fallback: {len(filtered_slots)} slots")
            
            # Debug: show what slots we have after filtering
            for i, slot in enumerate(filtered_slots[:3]):
                start_time = self._parse_datetime_robust(slot.get("start"))
                if start_time:
                    print(f"  Filtered slot {i+1}: {start_time.strftime('%H:%M')} ({start_time.hour})")
            
            # Always return exactly 3 slots
            final_slots = filtered_slots[:3]
            print(f"AvailabilityTool: Returning {len(final_slots)} slots")
            return final_slots
            
        except Exception as e:
            print(f"Error in AvailabilityTool: {e}")
            return []
    
    def _filter_by_time_preference(self, slots: List[Dict], time_preference: str) -> List[Dict]:
        """
        Enhanced filter slots based on time preference with smart fallback logic
        Supports:
        - Basic time periods: morning (6AM-12PM), afternoon (12PM-6PM), evening (6PM-10PM)
        - Specific time queries: "after 6 PM", "before 2 PM"
        - Fallback: Returns next appropriate slots within reasonable hours (6AM-10PM), never after-midnight
        """
        if not time_preference or time_preference.lower() == "any":
            return slots
        
        time_preference = time_preference.lower()
        filtered_slots = []
        reasonable_hours_slots = []  # Only slots within 6 AM - 10 PM
        
        # Parse specific time patterns (e.g., "after 6 PM", "before 2 PM")
        specific_time_match = self._parse_specific_time(time_preference)
        
        for slot in slots:
            if not slot.get("start"):
                continue
                
            try:
                # Parse the start time with robust parser
                start_time = self._parse_datetime_robust(slot["start"])
                
                if not start_time:
                    continue
                
                local_time = start_time.astimezone(DUBAI_TZ)
                hour = local_time.hour
                
                # Filter out after-midnight and very early morning slots (10 PM - 6 AM)
                is_reasonable_hour = 6 <= hour < 22
                
                if is_reasonable_hour:
                    slot_with_time = {**slot, '_parsed_hour': hour, '_parsed_time': start_time}
                    reasonable_hours_slots.append(slot_with_time)
                
                # Handle specific time queries first
                if specific_time_match:
                    target_hour, operator = specific_time_match
                    if operator == "after" and hour >= target_hour and hour < 22:  # Cap at 10 PM
                        filtered_slots.append(slot)
                    elif operator == "before" and hour <= target_hour and hour >= 6:  # Start from 6 AM
                        filtered_slots.append(slot)
                    continue
                
                # Standard time preference matching (stricter boundaries)
                if time_preference in ["morning", "am"] and 6 <= hour < 12:
                    filtered_slots.append(slot)
                elif time_preference in ["afternoon", "pm"] and 12 <= hour < 18:
                    filtered_slots.append(slot)
                elif time_preference in ["evening", "night"] and 18 <= hour < 22:  # Cap evening at 10 PM
                    filtered_slots.append(slot)
                elif time_preference == "any" and is_reasonable_hour:
                    filtered_slots.append(slot)
                    
            except Exception as e:
                print(f"Error parsing slot time: {e}")
                continue
        
        # Strict time enforcement: Return only slots that match the requested time range
        # Return 2-3 slots that actually match, don't add slots from different time ranges
        if len(filtered_slots) >= 2:
            print(f"✅ Found {len(filtered_slots)} slots matching '{time_preference}' time range")
            return filtered_slots[:3]  # Return max 3 matching slots
        elif len(filtered_slots) == 1:
            print(f"⚠️  Only 1 slot found for '{time_preference}', need at least 2 - will try another provider")
            return []  # Return empty to try another provider
        else:
            print(f"⚠️  No slots found for '{time_preference}' - will try another provider")
            return []  # Return empty to try another provider
        
        return filtered_slots[:3]  # Always return maximum 3 slots

    def _parse_specific_time(self, time_preference: str):
        """
        Parse specific time queries like 'after 6 PM', 'before 2 PM'
        Returns: (hour, operator) or None
        """
        import re
        
        # Pattern for "after/before X PM/AM"
        pattern = r'(after|before)\s+(\d{1,2})\s*(pm|am)'
        match = re.search(pattern, time_preference)
        
        if match:
            operator = match.group(1)
            hour = int(match.group(2))
            period = match.group(3)
            
            # Convert to 24-hour format
            if period == 'pm' and hour != 12:
                hour += 12
            elif period == 'am' and hour == 12:
                hour = 0
                
            return (hour, operator)
        
        return None
    
    def _remove_duplicate_slots(self, slots: List[Dict]) -> List[Dict]:
        """Remove duplicate slots based on start time and service"""
        seen_slots = set()
        unique_slots = []
        
        for slot in slots:
            # Create unique identifier
            start_time = slot.get('start', slot.get('start_time', ''))
            service = slot.get('serviceName', slot.get('service', ''))
            
            # Convert datetime to string for comparison
            if hasattr(start_time, 'isoformat'):
                time_str = start_time.isoformat()
            else:
                time_str = str(start_time)
            
            unique_key = f"{time_str}_{service}"
            
            if unique_key not in seen_slots:
                seen_slots.add(unique_key)
                unique_slots.append(slot)
            
        return unique_slots

class PricingTool:
    """Tool to calculate service pricing"""
    
    def __init__(self):
        self.firestore = FirestoreClient()
        
    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate pricing for a service
        
        Args:
            params: Dictionary with service_type and add_ons
        """
        try:
            service_type = params.get("service_type", "manicure")
            add_ons = params.get("add_ons", [])
            
            print(f"PricingTool: Calculating pricing for {service_type} with add-ons: {add_ons}")
            
            # Get service pricing from Firestore
            service_data = self.firestore.get_service_by_name(service_type)
            
            if not service_data:
                print(f"Warning: Service '{service_type}' not found in database")
                return {
                    "service_name": service_type.title(),
                    "base_price": 100,
                    "add_ons": [],
                    "add_on_total": 0,
                    "subtotal": 100,
                    "tax": 5,
                    "total_price": 105
                }
            
            base_price = service_data.get("basePrice", 0)
            service_add_ons = service_data.get("addOns", [])
            
            # Calculate add-on costs
            add_on_total = 0
            selected_add_ons = []
            
            if add_ons and service_add_ons:
                for addon_name in add_ons:
                    for service_addon in service_add_ons:
                        if service_addon.get("name", "").lower() == addon_name.lower():
                            add_on_total += service_addon.get("price", 0)
                            selected_add_ons.append(service_addon)
                            break
            
            subtotal = base_price + add_on_total
            tax = round(subtotal * 0.05, 2)  # 5% tax
            total_price = subtotal + tax
            
            pricing_info = {
                "service_name": service_data.get("name", service_type.title()),
                "base_price": base_price,
                "add_ons": selected_add_ons,
                "add_on_total": add_on_total,
                "subtotal": subtotal,
                "tax": tax,
                "total_price": total_price
            }
            
            print(f"PricingTool: Total price calculated: AED {total_price}")
            return pricing_info
            
        except Exception as e:
            print(f"Error in PricingTool: {e}")
            return {
                "service_name": params.get("service_type", "Service").title(),
                "base_price": 100,
                "add_ons": [],
                "add_on_total": 0,
                "subtotal": 100,
                "tax": 5,
                "total_price": 105
            }

class DistanceTool:
    """Tool to find nearest providers"""
    
    def __init__(self):
        self.firestore = FirestoreClient()
        self.geo_service = GeoService()
        
    def run(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Find nearest providers for a service
        
        Args:
            params: Dictionary with location and service
        """
        try:
            location = params.get("location", "Business Bay")
            service = params.get("service", "manicure")
            
            print(f"DistanceTool: Finding providers for {service} near {location}")
            
            # Get all providers that offer this service
            providers = self.firestore.get_providers_by_service(service)
            
            if not providers:
                print(f"Warning: No providers found for service '{service}'")
                return []
            
            print(f"DistanceTool: Found {len(providers)} providers offering {service}")
            
            # Find nearest providers
            nearest_providers = self.geo_service.find_nearest_providers(
                user_location=location,
                providers=providers,
                limit=3
            )
            
            print(f"DistanceTool: Returning {len(nearest_providers)} nearest providers")
            return nearest_providers
            
        except Exception as e:
            print(f"Error in DistanceTool: {e}")
            return []