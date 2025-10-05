# FCM Web Push Notification Service (Updated for HTTP v1 API)
import os
import json
import requests
from typing import Dict, Any, List
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from email.utils import parsedate_to_datetime

load_dotenv()

class FCMNotificationService:
    """Firebase Cloud Messaging service for web push notifications using HTTP v1 API"""
    _gst_timezone = timezone(timedelta(hours=4))
    
    def _parse_datetime(self, dt_string: str) -> datetime:
        """Parse datetime string in multiple formats"""
        if not isinstance(dt_string, str):
            return dt_string if isinstance(dt_string, datetime) else datetime.now()
        
        try:
            # Try ISO format first (e.g., "2025-10-04T15:00:00.000Z")
            return datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
        except:
            try:
                # Try RFC 822 format (e.g., "Sat, 04 Oct 2025 15:00:00 GMT")
                return parsedate_to_datetime(dt_string)
            except:
                # Fallback to current time
                return datetime.now()

    def _to_gst(self, dt: datetime) -> datetime:
        """Convert a datetime to Gulf Standard Time for notifications"""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(self._gst_timezone)
    
    def __init__(self):
        # FCM configuration
        self.project_id = os.getenv('FIREBASE_PROJECT_ID', 'booking-agent-dbf87')
        self.service_account_path = os.getenv('FCM_SERVICE_ACCOUNT_PATH', './credentials/firebase-service-account.json.json')
        self.web_push_key = os.getenv('FCM_WEB_PUSH_KEY', '')
        self.fcm_url = f"https://fcm.googleapis.com/v1/projects/{self.project_id}/messages:send"
        self.credentials = None
        self._initialize_credentials()
    
    def _initialize_credentials(self):
        """Initialize Firebase credentials for HTTP v1 API"""
        try:
            if os.path.exists(self.service_account_path):
                self.credentials = service_account.Credentials.from_service_account_file(
                    self.service_account_path,
                    scopes=['https://www.googleapis.com/auth/firebase.messaging']
                )
                print("✅ FCM credentials initialized successfully")
            else:
                print(f"⚠️ FCM service account file not found: {self.service_account_path}")
        except Exception as e:
            print(f"❌ FCM initialization error: {e}")
    
    def _get_access_token(self):
        """Get OAuth2 access token for HTTP v1 API"""
        if not self.credentials:
            return None
        
        try:
            request = Request()
            self.credentials.refresh(request)
            return self.credentials.token
        except Exception as e:
            print(f"❌ Failed to get FCM access token: {e}")
            return None
    
    def send_booking_notification(
        self, 
        user_token: str, 
        booking_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send FCM push notification for booking confirmation using HTTP v1 API"""
        
        if not self.credentials:
            return {
                "success": False,
                "error": "FCM credentials not initialized"
            }
        
        try:
            # Get access token
            access_token = self._get_access_token()
            if not access_token:
                return {
                    "success": False,
                    "error": "Failed to get FCM access token"
                }
            
            provider = booking_details.get('provider', {})
            pricing = booking_details.get('pricing', {})
            slot = booking_details.get('selected_slot', {})
            
            # Format datetime
            start_time = slot.get('start', datetime.now())
            start_time = self._parse_datetime(start_time) if isinstance(start_time, str) else start_time
            display_time = self._to_gst(start_time)
            
            formatted_date = display_time.strftime("%A, %B %d")
            formatted_time = display_time.strftime("%I:%M %p GST")
            
            # Create HTTP v1 API message payload
            message_payload = {
                "message": {
                    "token": user_token,
                    "notification": {
                        "title": f"🎉 Booking Confirmed - {booking_details.get('service', 'Service')}",
                        "body": f"{provider.get('name', 'Provider')} • {formatted_date} at {formatted_time}"
                    },
                    "webpush": {
                        "notification": {
                            "title": f"🎉 Booking Confirmed - {booking_details.get('service', 'Service')}",
                            "body": f"{provider.get('name', 'Provider')} • {formatted_date} at {formatted_time}",
                            "icon": "/favicon.svg",
                            "badge": "/favicon.svg",
                            "click_action": f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/bookings",
                            "tag": f"booking-{booking_details.get('booking_id', 'unknown')}"
                        }
                    },
                    "data": {
                        "type": "booking_confirmation",
                        "booking_id": booking_details.get('booking_id', ''),
                        "service": booking_details.get('service', ''),
                        "provider": provider.get('name', ''),
                        "date": formatted_date,
                        "time": formatted_time,
                        "price": str(pricing.get('total_price', 0)),
                        "currency": pricing.get('currency', 'AED')
                    }
                }
            }
            
            # Set headers for HTTP v1 API
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            # Send FCM request
            response = requests.post(
                self.fcm_url,
                headers=headers,
                data=json.dumps(message_payload),
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ FCM notification sent successfully: {result}")
                return {
                    "success": True,
                    "message_id": result.get('name', 'unknown'),
                    "status": "FCM notification sent successfully"
                }
            else:
                print(f"❌ FCM error: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"FCM error: {response.status_code} - {response.text}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to send FCM notification: {str(e)}"
            }
    
    def send_reminder_notification(
        self, 
        user_token: str, 
        booking_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send reminder notification 24h before appointment"""
        
        try:
            provider = booking_details.get('provider', {})
            slot = booking_details.get('selected_slot', {})
            
            start_time = slot.get('start', datetime.now())
            start_time = self._parse_datetime(start_time) if isinstance(start_time, str) else start_time
            
            display_time = self._to_gst(start_time)
            formatted_time = display_time.strftime("tomorrow at %I:%M %p GST")
            
            notification_data = {
                "to": user_token,
                "notification": {
                    "title": f"⏰ Appointment Reminder",
                    "body": f"Don't forget: {booking_details.get('service', 'Service')} {formatted_time}",
                    "icon": "/favicon.svg",
                    "click_action": f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/bookings"
                },
                "data": {
                    "type": "appointment_reminder",
                    "booking_id": booking_details.get('booking_id', ''),
                    "provider": provider.get('name', ''),
                    "service": booking_details.get('service', '')
                }
            }
            
            response = requests.post(
                self.fcm_url,
                headers=self.headers,
                data=json.dumps(notification_data),
                timeout=10
            )
            
            return {
                "success": response.status_code == 200,
                "status": f"Reminder notification {'sent' if response.status_code == 200 else 'failed'}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to send reminder: {str(e)}"
            }
    
    def get_notification_status(self, user_token=None):
        """Get FCM notification status for the service"""
        status = {
            "fcm_initialized": self.credentials is not None,
            "project_id": self.project_id,
            "service_account_available": os.path.exists(self.service_account_path) if self.service_account_path else False
        }
        
        if user_token:
            status["user_token_provided"] = True
            status["token_length"] = len(user_token)
        else:
            status["user_token_provided"] = False
            
        return status

# Enhanced notification service that combines Email + FCM
class HybridNotificationService:
    """Combined Email + FCM notification service"""
    
    def __init__(self):
        self.email_service = None
        self.fcm_service = FCMNotificationService()
        
        # Import EmailNotificationService if available
        try:
            from notification import EmailNotificationService
            self.email_service = EmailNotificationService()
        except ImportError:
            print("Email service not available")
    
    def send_booking_notifications(
        self, 
        user_email: str,
        user_fcm_token: str,
        booking_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send both email and FCM notifications"""
        
        results = {
            "email": {"success": False},
            "fcm": {"success": False},
            "overall_success": False
        }
        
        # Send email notification
        if self.email_service and user_email:
            try:
                email_result = self.email_service.send_booking_confirmation(
                    user_email=user_email,
                    booking_details=booking_details
                )
                results["email"] = email_result
            except Exception as e:
                results["email"] = {"success": False, "error": str(e)}
        
        # Send FCM notification
        if user_fcm_token:
            fcm_result = self.fcm_service.send_booking_notification(
                user_token=user_fcm_token,
                booking_details=booking_details
            )
            results["fcm"] = fcm_result
        
        # Overall success if at least one method succeeded
        results["overall_success"] = (
            results["email"].get("success", False) or 
            results["fcm"].get("success", False)
        )
        
        return results