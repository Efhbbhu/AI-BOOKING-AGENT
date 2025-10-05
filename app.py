# Flask API routes for the Service Booking Agent
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv

from agent import BookingAgent
from firebase import validate_token
from fcm_notifications import HybridNotificationService

# Load environment variables
load_dotenv()

BUILD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "build")

app = Flask(
    __name__,
    static_folder=os.path.join(BUILD_DIR, "static"),
    template_folder=BUILD_DIR
)
CORS(app)

# Initialize booking agent and notification service
booking_agent = BookingAgent()
notification_service = HybridNotificationService()

@app.route('/health', methods=['GET'])
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "Service Booking Agent is running"})

@app.route('/book', methods=['POST'])
def book_service():
    """Book a service using natural language"""
    try:
        # Get request data
        data = request.get_json()
        
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        uid = data.get('uid')
        query = data.get('query')
        confirm = data.get('confirm', False)
        
        if not uid or not query:
            return jsonify({"success": False, "error": "Missing uid or query"}), 400
        
        # Process booking request
        result = booking_agent.process_booking_request(uid, query, confirm)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/book-confirm', methods=['POST'])
def confirm_booking():
    """Confirm and save a booking to Firestore"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        # Handle both data formats: new enhanced format and original format
        uid = data.get('uid') or data.get('user_id')
        
        # New format (from enhanced BookingResult component)
        if 'service' in data and 'provider' in data and isinstance(data['provider'], str):
            service_name = data.get('service', '')
            provider_name = data.get('provider', '')
            provider_phone = data.get('provider_phone', '')
            provider_rating = data.get('provider_rating', 0)
            price = data.get('price', 'AED 0')
            date = data.get('date', '')
            time = data.get('time', '')
            slot_id = data.get('slot_id', '')
        else:
            # Original format (from current BookingResult component)
            provider = data.get('provider', {})
            selected_slot = data.get('selected_slot', {})
            pricing = data.get('pricing', {})
            service_name = data.get('service_name', '')
            provider_name = provider.get('name', '')
            provider_phone = provider.get('phone', '')
            provider_rating = provider.get('rating', 0)
            price = f"AED {pricing.get('total_price', 0)}"
            
            # Handle datetime properly
            start_time = selected_slot.get('start', '')
            if start_time:
                # If it's already an ISO string, use it
                if isinstance(start_time, str):
                    date = start_time
                    time = start_time
                # If it's a datetime object, convert to ISO
                elif hasattr(start_time, 'isoformat'):
                    date = start_time.isoformat()
                    time = start_time.isoformat()
                else:
                    # Fallback
                    date = str(start_time)
                    time = str(start_time)
            else:
                date = ''
                time = ''
            
            slot_id = selected_slot.get('slot_id', '')
        
        if not uid:
            return jsonify({"success": False, "error": "Missing user ID"}), 400
        
        # Generate unique booking ID
        booking_id = str(uuid.uuid4())
        
        # Create booking document for Firestore
        booking_data = {
            "id": booking_id,
            "user_id": uid,
            "user_name": data.get('user_name', ''),
            "user_email": data.get('user_email', ''),
            "service": service_name,
            "provider": provider_name,
            "provider_phone": provider_phone,
            "provider_rating": provider_rating,
            "price": price,
            "date": date,
            "time": time,
            "slot_id": slot_id,
            "status": "confirmed",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Save to Firestore
        booking_agent.firestore_client.add_booking(booking_data)
        
        return jsonify({
            "success": True,
            "booking_id": booking_id,
            "message": f"Booking confirmed for {service_name}"
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.errorhandler(404)
def not_found(_):
    """Serve React app for unknown routes"""
    if os.path.exists(os.path.join(BUILD_DIR, 'index.html')):
        return send_from_directory(BUILD_DIR, 'index.html')
    return jsonify({"error": "Not found"}), 404


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_spa(path):
    """Serve React static files and index.html fallback"""
    requested_path = os.path.join(BUILD_DIR, path)
    if path != "" and os.path.exists(requested_path) and os.path.isfile(requested_path):
        return send_from_directory(BUILD_DIR, path)
    return send_from_directory(BUILD_DIR, 'index.html')

@app.route('/bookings', methods=['GET'])
def get_bookings():
    """Get user bookings"""
    try:
        # Support both uid and user_id parameters
        uid = request.args.get('uid') or request.args.get('user_id')
        
        if not uid:
            return jsonify({"success": False, "error": "Missing uid or user_id parameter"}), 400
        
        # Get user bookings
        bookings = booking_agent.get_user_bookings(uid)
        
        return jsonify({"success": True, "bookings": bookings})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/bookings/<booking_id>/cancel', methods=['POST'])
def cancel_booking(booking_id):
    """Cancel a booking"""
    try:
        # Get uid from request body
        data = request.get_json()
        uid = data.get('uid')
        
        if not uid:
            return jsonify({"success": False, "error": "Missing uid"}), 400
        
        # Update booking status to cancelled
        success = booking_agent.firestore_client.update_booking(booking_id, {
            "status": "cancelled",
            "cancelled_at": datetime.now(timezone.utc).isoformat()
        })
        
        if success:
            return jsonify({"success": True, "message": "Booking cancelled successfully"})
        else:
            return jsonify({"success": False, "error": "Failed to cancel booking"}), 500
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/send-notification', methods=['POST'])
def send_notification():
    """Send notification for a booking"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        user_id = data.get('user_id')
        booking_id = data.get('booking_id')
        service = data.get('service')
        provider = data.get('provider')
        date = data.get('date')
        time = data.get('time')
        send_email = data.get('send_email', True)
        send_fcm = data.get('send_fcm', True)
        
        if not user_id:
            return jsonify({"success": False, "error": "Missing user_id"}), 400
        
        # Create notification message
        title = f"Booking Reminder: {service}"
        message = f"Your {service} appointment with {provider} is coming up!"
        
        # Get user details from Firebase Auth
        from firebase import FirestoreClient
        firestore_client = FirestoreClient()
        user_email = None
        user_fcm_token = None
        
        # Try to get user email from data or default
        user_email = data.get('user_email', 'user@example.com')
        
        # Try to get FCM token from localStorage (frontend should send this)
        user_fcm_token = data.get('fcm_token') or data.get('user_fcm_token')
        
        # Fetch REAL booking details from Firestore database
        booking_details = None
        if booking_id:
            try:
                booking_doc = firestore_client.db.collection('bookings').document(booking_id).get()
                if booking_doc.exists:
                    real_booking = booking_doc.to_dict()
                    
                    # Extract price (format: "AED 150" -> 150)
                    price_str = real_booking.get('price', 'AED 0')
                    try:
                        price_value = float(price_str.replace('AED', '').strip())
                    except:
                        price_value = 0
                    
                    # Use REAL data from database
                    booking_details = {
                        'booking_id': booking_id,
                        'service': real_booking.get('service', service),
                        'provider': {
                            'name': real_booking.get('provider', provider),
                            'phone': real_booking.get('provider_phone', 'N/A'),
                            'address': real_booking.get('provider_address', 'Dubai, UAE'),
                            'rating': real_booking.get('provider_rating', 0)
                        },
                        'selected_slot': {
                            'start': real_booking.get('time') or real_booking.get('date') or date or time,
                            'duration': 60
                        },
                        'pricing': {
                            'base_price': price_value * 0.95,
                            'tax': price_value * 0.05,
                            'total_price': price_value,
                            'currency': 'AED'
                        }
                    }
            except Exception as e:
                print(f"Error fetching booking: {e}")
        
        # Fallback to minimal data if booking not found
        if not booking_details:
            start_datetime = date or time
            booking_details = {
                'booking_id': booking_id,
                'service': service,
                'provider': {'name': provider},
                'selected_slot': {'start': start_datetime},
                'pricing': {'total_price': 0, 'currency': 'AED'}
            }
        
        # Send notifications
        results = {}
        
        if send_email and user_email and user_email != 'user@example.com':
            try:
                if notification_service.email_service:
                    email_result = notification_service.email_service.send_booking_confirmation(
                        user_email=user_email,
                        booking_details=booking_details
                    )
                else:
                    email_result = {"success": False, "error": "Email service not available"}
                results['email'] = email_result
            except Exception as e:
                results['email'] = {"success": False, "error": str(e)}
        else:
            results['email'] = {"success": False, "error": "Email not sent"}
        
        if send_fcm and user_fcm_token:
            try:
                fcm_result = notification_service.fcm_service.send_booking_notification(
                    user_token=user_fcm_token,
                    booking_details=booking_details
                )
                results['fcm'] = fcm_result
            except Exception as e:
                results['fcm'] = {"success": False, "error": str(e)}
        else:
            results['fcm'] = {"success": False, "error": "FCM not sent"}
        
        # Consider success if at least one notification was sent
        overall_success = any(result.get('success', False) for result in results.values())
        
        return jsonify({
            "success": overall_success,
            "results": results,
            "message": "Notifications sent successfully" if overall_success else "Failed to send notifications"
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    # Try different ports until we find one that works
    ports_to_try = [8088, 8089, 8090, 5555, 7777, 9999]
    
    for port in ports_to_try:
        try:
            print(f"Trying to start server on port {port}...")
            app.run(host='127.0.0.1', port=port, debug=True, use_reloader=False)
            break
        except OSError as e:
            if "Address already in use" in str(e) or "access permissions" in str(e).lower():
                print(f"Port {port} not available, trying next...")
                continue
            else:
                raise e
    else:
        print("Could not find an available port!")