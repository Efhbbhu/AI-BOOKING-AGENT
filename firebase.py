# Firebase Firestore and Auth helpers
import os
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import credentials, firestore, auth
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class FirestoreClient:
    """Client for interacting with Firestore database"""
    
    def __init__(self):
        # Initialize Firebase Admin SDK
        if not firebase_admin._apps:
            # Get service account path from environment
            service_account_path = os.getenv('FIREBASE_SERVICE_ACCOUNT')
            if service_account_path and os.path.exists(service_account_path):
                cred = credentials.Certificate(service_account_path)
            else:
                # Fallback to default credentials for Cloud Run
                cred = credentials.ApplicationDefault()
            
            firebase_admin.initialize_app(cred, {
                'projectId': os.getenv('FIREBASE_PROJECT_ID')
            })
        
        self.db = firestore.client()
        self._service_cache = {}
        self._providers_cache = {}
    
    # User management
    def create_or_update_user(self, uid: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update user document"""
        user_ref = self.db.collection('users').document(uid)
        
        # Add timestamps
        now = datetime.now(timezone.utc)
        user_data['lastActiveAt'] = now
        
        # Check if user exists
        if not user_ref.get().exists:
            user_data['createdAt'] = now
        
        user_ref.set(user_data, merge=True)
        return {"status": "success", "uid": uid}
    
    def get_user(self, uid: str) -> Optional[Dict[str, Any]]:
        """Get user document"""
        user_doc = self.db.collection('users').document(uid).get()
        if user_doc.exists:
            return user_doc.to_dict()
        return None
    
    # Service management
    def get_service_info(self, service_type: str) -> Optional[Dict[str, Any]]:
        """Get service information by service type/name"""
        if not service_type:
            return None

        cache_key = service_type.strip().lower()
        if cache_key in self._service_cache:
            return self._service_cache[cache_key]
            
        services_ref = self.db.collection('services')
        # Make case-insensitive search
        query = services_ref.where(field_path='name', op_string='==', value=service_type.title()).limit(1)
        
        docs = query.get()
        for doc in docs:
            service_data = doc.to_dict()
            service_data['service_id'] = doc.id
            self._service_cache[cache_key] = service_data
            return service_data
        
        # If exact match fails, try case-insensitive search across all services
        all_docs = services_ref.get()
        for doc in all_docs:
            service_data = doc.to_dict()
            if service_data.get('name', '').lower() == service_type.lower():
                service_data['service_id'] = doc.id
                self._service_cache[cache_key] = service_data
                return service_data
        
        return None
    
    def get_all_services(self) -> List[Dict[str, Any]]:
        """Get all available services"""
        services = []
        docs = self.db.collection('services').get()
        
        for doc in docs:
            service_data = doc.to_dict()
            service_data['service_id'] = doc.id
            services.append(service_data)
        
        return services
    
    # Provider management
    def get_providers_by_service(self, service_type: str) -> List[Dict[str, Any]]:
        """Get all providers that offer a specific service"""
        # First get the service ID
        cache_key = service_type.strip().lower() if service_type else ""
        if cache_key and cache_key in self._providers_cache:
            return self._providers_cache[cache_key]

        service_info = self.get_service_info(service_type)
        if not service_info:
            return []
        
        service_id = service_info['service_id']
        
        # Query providers that have this service
        providers_ref = self.db.collection('providers')
        query = providers_ref.where(field_path='services', op_string='array_contains', value=service_id)
        
        providers = []
        docs = query.get()
        
        for doc in docs:
            provider_data = doc.to_dict()
            provider_data['provider_id'] = doc.id
            providers.append(provider_data)
        
        if cache_key:
            self._providers_cache[cache_key] = providers

        return providers
    
    def get_provider(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """Get provider information"""
        provider_doc = self.db.collection('providers').document(provider_id).get()
        if provider_doc.exists:
            provider_data = provider_doc.to_dict()
            provider_data['provider_id'] = provider_id
            return provider_data
        return None
    
    # Schedule and availability management
    def get_available_slots(
        self, 
        provider_id: str, 
        service_type: str, 
        date_filter: str = None,
        date: str = None, 
        start_time: str = None, 
        end_time: str = None,
        include_booked: bool = False
    ) -> List[Dict[str, Any]]:
        """Get available time slots for a provider
        
        Args:
            include_booked: If True, returns both available and booked slots
                          If False, returns only available slots (default)
        """
        from datetime import datetime
        
        slots_ref = self.db.collection('schedules').document(provider_id).collection('slots')
        
        # Build query based on filters
        # Only filter by isBooked if include_booked is False
        if not include_booked:
            query = slots_ref.where(field_path='isBooked', op_string='==', value=False)
        else:
            query = slots_ref  # Get all slots regardless of booking status
        
        if service_type:
            # Get service ID first
            service_info = self.get_service_info(service_type)
            if service_info:
                query = query.where(field_path='serviceId', op_string='==', value=service_info['service_id'])
        
        # Add date/time filters if provided
        # Handle both 'date' and 'date_filter' parameters for compatibility
        date_param = date_filter or date
        
        slots = []
        docs = query.limit(200).get()  # Get more slots to filter from (increased for better date coverage)
        
        # Get current time for filtering past slots (timezone-aware)
        from datetime import timezone
        now = datetime.now(timezone.utc)
        
        for doc in docs:
            slot_data = doc.to_dict()
            slot_data['slot_id'] = doc.id
            
            # Filter out past slots - check BEFORE converting to ISO format
            if 'start' in slot_data:
                slot_start = slot_data['start']
                # Handle both datetime objects and already-converted ISO strings
                if hasattr(slot_start, 'replace'):  # It's a datetime object
                    # Make timezone-aware if needed
                    if slot_start.tzinfo is None:
                        from datetime import timezone
                        slot_start = slot_start.replace(tzinfo=timezone.utc)
                    # Skip slots that are in the past (with 1 hour buffer to avoid edge cases)
                    from datetime import timedelta
                    if slot_start < (now - timedelta(hours=1)):
                        continue
                elif isinstance(slot_start, str):  # It's already an ISO string
                    try:
                        slot_start_dt = datetime.fromisoformat(slot_start.replace('Z', '+00:00'))
                        if slot_start_dt.tzinfo is None:
                            from datetime import timezone
                            slot_start_dt = slot_start_dt.replace(tzinfo=timezone.utc)
                        from datetime import timedelta
                        if slot_start_dt < (now - timedelta(hours=1)):
                            continue
                    except Exception as e:
                        pass  # Keep the slot if we can't parse it
            
            # Convert datetime objects to ISO format strings for JSON serialization
            for field in ['start', 'end', 'createdAt']:
                if field in slot_data and hasattr(slot_data[field], 'isoformat'):
                    slot_data[field] = slot_data[field].isoformat()
            
            slots.append(slot_data)
        
        # Apply date filtering in Python if requested
        if date_param:
            slots = self._filter_slots_by_date(slots, date_param)
        
        # If include_booked is True, sort so available slots come first
        if include_booked:
            # Sort: available slots first, then booked slots
            slots = sorted(slots, key=lambda x: (x.get('isBooked', False), x.get('start', '')))
        
        return slots
    
    def _filter_slots_by_date(self, slots: List[Dict[str, Any]], date_filter: str) -> List[Dict[str, Any]]:
        """Filter slots by date preference (today, tomorrow, friday, etc.)"""
        from datetime import datetime, timedelta
        
        if not date_filter or date_filter.lower() == "any":
            return slots
        
        today = datetime.now()
        target_date = None
        
        date_filter_lower = date_filter.lower()
        
        if date_filter_lower == "today":
            target_date = today
        elif date_filter_lower == "tomorrow":
            target_date = today + timedelta(days=1)
        elif "monday" in date_filter_lower:
            # Find next Monday (or today if it's Monday)
            days_until_monday = (0 - today.weekday()) % 7
            if days_until_monday == 0:  # Today is Monday
                target_date = today
            else:
                target_date = today + timedelta(days=days_until_monday)
        elif "tuesday" in date_filter_lower:
            # Find next Tuesday
            days_until_tuesday = (1 - today.weekday()) % 7
            if days_until_tuesday == 0:
                target_date = today
            else:
                target_date = today + timedelta(days=days_until_tuesday)
        elif "wednesday" in date_filter_lower:
            # Find next Wednesday
            days_until_wednesday = (2 - today.weekday()) % 7
            if days_until_wednesday == 0:
                target_date = today
            else:
                target_date = today + timedelta(days=days_until_wednesday)
        elif "thursday" in date_filter_lower:
            # Find next Thursday
            days_until_thursday = (3 - today.weekday()) % 7
            if days_until_thursday == 0:
                target_date = today
            else:
                target_date = today + timedelta(days=days_until_thursday)
        elif "friday" in date_filter_lower:
            # Find next Friday (or today if it's Friday)
            days_until_friday = (4 - today.weekday()) % 7
            if days_until_friday == 0:  # Today is Friday
                target_date = today
            else:
                target_date = today + timedelta(days=days_until_friday)
        elif "saturday" in date_filter_lower:
            # Find next Saturday
            days_until_saturday = (5 - today.weekday()) % 7
            if days_until_saturday == 0:
                target_date = today
            else:
                target_date = today + timedelta(days=days_until_saturday)
        elif "sunday" in date_filter_lower:
            # Find next Sunday
            days_until_sunday = (6 - today.weekday()) % 7
            if days_until_sunday == 0:
                target_date = today
            else:
                target_date = today + timedelta(days=days_until_sunday)
        
        if not target_date:
            return slots  # No filtering if date not recognized
        
        filtered_slots = []
        target_date_str = target_date.strftime('%Y-%m-%d')
        
        for slot in slots:
            try:
                start_time = slot.get('start')
                if isinstance(start_time, str):
                    start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                
                if start_time:
                    slot_date_str = start_time.strftime('%Y-%m-%d')
                    if slot_date_str == target_date_str:
                        filtered_slots.append(slot)
                        
            except Exception as e:
                print(f"Error filtering slot by date: {e}")
                continue
        
        print(f"Date filtering: {len(slots)} -> {len(filtered_slots)} slots for {date_filter}")
        return filtered_slots
    
    def update_slot_booking_status(self, provider_id: str, slot_id: str, is_booked: bool) -> bool:
        """Update the booking status of a slot"""
        try:
            slot_ref = self.db.collection('schedules').document(provider_id).collection('slots').document(slot_id)
            slot_ref.update({'isBooked': is_booked})
            return True
        except Exception as e:
            print(f"Error updating slot status: {e}")
            return False
    
    # Booking management
    def create_booking(self, uid: str, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new booking"""
        booking_ref = self.db.collection('bookings').document()
        
        # Extract booking details from proposal
        provider = proposal.get('provider', {})
        slots = proposal.get('available_slots', [])
        pricing = proposal.get('pricing', {})
        
        if not slots:
            return {"error": "No time slot selected"}
        
        # Use first available slot (in real app, user would select)
        selected_slot = slots[0]
        
        booking_data = {
            'uid': uid,
            'user_id': uid,  # Add both for compatibility
            'providerId': provider.get('provider_id'),
            'provider': provider.get('name', 'Unknown Provider'),
            'provider_phone': provider.get('phone'),
            'provider_rating': provider.get('rating'),
            'serviceId': selected_slot.get('service_type'),
            'service': proposal.get('service_name', selected_slot.get('service_type')),
            'slotId': selected_slot.get('slot_id'),
            'start': selected_slot.get('start_time'),
            'end': selected_slot.get('end_time'),
            'date': selected_slot.get('start_time'),  # Duplicate for frontend compatibility
            'time': selected_slot.get('start_time'),  # Duplicate for frontend compatibility
            'price': f"{pricing.get('currency', 'AED')} {pricing.get('total', 0)}",
            'currency': pricing.get('currency', 'AED'),
            'status': 'confirmed',
            'createdAt': datetime.now(timezone.utc),
            'created_at': datetime.now(timezone.utc),  # Add both for compatibility
            'pricing_breakdown': pricing
        }
        
        # Save booking
        booking_ref.set(booking_data)
        
        # Update slot to mark as booked
        provider_id = provider.get('provider_id')
        slot_id = selected_slot.get('slot_id')
        if provider_id and slot_id:
            self.update_slot_booking_status(provider_id, slot_id, True)
        
        # Return booking details
        booking_data['booking_id'] = booking_ref.id
        return booking_data
    
    def get_user_bookings(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all bookings for a user (supports both uid and user_id)"""
        bookings_ref = self.db.collection('bookings')
        
        # Try both field names for compatibility
        try:
            # Try with 'user_id' field first (new format)
            query = bookings_ref.where('user_id', '==', user_id).order_by('created_at', direction=firestore.Query.DESCENDING)
            docs = query.get()
            
            # If no results, try with 'uid' field (legacy format)
            if not docs:
                query = bookings_ref.where('uid', '==', user_id).order_by('createdAt', direction=firestore.Query.DESCENDING)
                docs = query.get()
        except Exception:
            # Fallback: try without ordering if index doesn't exist
            try:
                query = bookings_ref.where('user_id', '==', user_id)
                docs = query.get()
                if not docs:
                    query = bookings_ref.where('uid', '==', user_id)
                    docs = query.get()
            except Exception:
                return []
        
        bookings = []
        for doc in docs:
            booking_data = doc.to_dict()
            booking_data['id'] = doc.id
            # Ensure consistent field naming
            if 'booking_id' not in booking_data:
                booking_data['booking_id'] = doc.id
            
            # Convert Firebase timestamps to proper format for frontend
            if 'start' in booking_data and booking_data['start']:
                try:
                    if hasattr(booking_data['start'], 'isoformat'):
                        start_dt = booking_data['start']
                    else:
                        start_dt = datetime.fromisoformat(str(booking_data['start']).replace('Z', '+00:00'))
                    
                    booking_data['date'] = start_dt.isoformat()
                    booking_data['time'] = start_dt.isoformat()
                except:
                    pass
            
            # Handle legacy createdAt field
            if 'createdAt' in booking_data and 'created_at' not in booking_data:
                booking_data['created_at'] = booking_data['createdAt']
                
            bookings.append(booking_data)
        
        return bookings
    
    def get_service_by_name(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get service data by service name with graceful fallbacks"""
        if not service_name:
            return None

        # Reuse the more robust lookup to benefit from case-insensitive matching
        service_info = self.get_service_info(service_name)
        if service_info:
            return service_info

        # Handle common synonyms to avoid falling back to default pricing
        normalized = service_name.strip().lower()
        synonym_map = {
            "hair cut": "haircut",
            "hair styling": "haircut",
            "nails": "manicure",
            "nail service": "manicure",
            "face treatment": "facial",
            "skin treatment": "facial",
            "foot spa": "pedicure",
        }

        if normalized in synonym_map:
            return self.get_service_info(synonym_map[normalized])

        return None
    
    # Query logging for analytics and debugging
    def log_query(self, uid: str, query: str, result: Dict[str, Any]) -> None:
        """Log user queries and results for analytics"""
        log_ref = self.db.collection('plans').document(uid).collection('queries').document()
        
        log_data = {
            'query': query,
            'proposal': result.get('proposal', {}),
            'steps': result.get('steps', []),
            'createdAt': datetime.now(timezone.utc)
        }
        
        log_ref.set(log_data)
    
    # Policy management (optional)
    def get_policy(self, provider_id: str, policy_type: str) -> Optional[Dict[str, Any]]:
        """Get policy information for a provider"""
        policy_doc = self.db.collection('providers').document(provider_id).collection('policies').document(policy_type).get()
        
        if policy_doc.exists:
            return policy_doc.to_dict()
        return None
    
    # Booking management
    def add_booking(self, booking_data: Dict[str, Any]) -> str:
        """Add a new booking to Firestore"""
        bookings_ref = self.db.collection('bookings')
        doc_ref = bookings_ref.document(booking_data['id'])
        doc_ref.set(booking_data)
        return booking_data['id']
    

    
    def update_booking(self, booking_id: str, update_data: Dict[str, Any]) -> bool:
        """Update a booking"""
        booking_ref = self.db.collection('bookings').document(booking_id)
        booking_ref.update(update_data)
        return True
    
    def get_booking(self, booking_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific booking"""
        booking_doc = self.db.collection('bookings').document(booking_id).get()
        if booking_doc.exists:
            booking_data = booking_doc.to_dict()
            booking_data['id'] = booking_id
            return booking_data
        return None
    
    def delete_booking(self, booking_id: str) -> bool:
        """Delete a booking"""
        booking_ref = self.db.collection('bookings').document(booking_id)
        booking_ref.delete()
        return True

def validate_token(auth_header: str) -> Dict[str, Any]:
    """Validate Firebase ID token from Authorization header"""
    if not auth_header or not auth_header.startswith('Bearer '):
        raise ValueError("Invalid authorization header")
    
    id_token = auth_header.split('Bearer ')[1]
    
    try:
        # Verify the token
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token
    except Exception as e:
        raise ValueError(f"Invalid token: {str(e)}")

def get_user_from_token(auth_header: str) -> str:
    """Extract user ID from Firebase token"""
    decoded_token = validate_token(auth_header)
    return decoded_token['uid']