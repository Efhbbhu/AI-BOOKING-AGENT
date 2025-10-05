# Email notification system for booking confirmations
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
import os
from urllib.parse import quote
from email.utils import parsedate_to_datetime

class EmailNotificationService:
    """Email notification service for booking confirmations"""
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
        """Convert a datetime to Gulf Standard Time for display"""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(self._gst_timezone)
    
    def __init__(self):
        # Email configuration (you'll need to set these as environment variables)
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.sender_email = os.getenv("SENDER_EMAIL", "your-email@gmail.com")
        self.sender_password = os.getenv("SENDER_PASSWORD", "your-app-password")
        
    def send_booking_confirmation(
        self, 
        user_email: str, 
        booking_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send booking confirmation email with calendar invite"""
        
        try:
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = f"Booking Confirmation - {booking_details.get('service', 'Service')}"
            message["From"] = self.sender_email
            message["To"] = user_email
            
            # Create HTML content
            html_content = self._create_booking_email_html(booking_details)
            
            # Create calendar invite
            calendar_invite = self._create_calendar_invite(booking_details)
            
            # Attach HTML content
            html_part = MIMEText(html_content, "html")
            message.attach(html_part)
            
            # Send email
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, user_email, message.as_string())
            
            return {
                "success": True,
                "message": "Booking confirmation email sent successfully",
                "calendar_link": calendar_invite
            }
            
        except Exception as e:
            print(f"Email sending failed: {e}")
            return {
                "success": False,
                "error": f"Failed to send email: {str(e)}"
            }
    
    def _create_booking_email_html(self, booking_details: Dict[str, Any]) -> str:
        """Create HTML email content for booking confirmation"""
        
        provider = booking_details.get('provider', {})
        pricing = booking_details.get('pricing', {})
        slot = booking_details.get('selected_slot', {})
        
        # Format datetime
        start_time = slot.get('start', datetime.now())
        start_time = self._parse_datetime(start_time) if isinstance(start_time, str) else start_time
        display_time = self._to_gst(start_time)

        formatted_date = display_time.strftime("%A, %B %d, %Y")
        formatted_time = display_time.strftime("%I:%M %p GST")
        
        # Create calendar link
        calendar_link = self._create_google_calendar_link(booking_details)
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Booking Confirmation</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .booking-card {{ background: white; padding: 25px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin: 20px 0; }}
                .detail-row {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #eee; }}
                .detail-label {{ font-weight: bold; color: #555; }}
                .detail-value {{ color: #333; }}
                .price-total {{ background: #e8f5e8; padding: 15px; border-radius: 5px; text-align: center; font-size: 18px; font-weight: bold; color: #2d7a2d; }}
                .calendar-btn {{ display: inline-block; background: #4285f4; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; margin: 20px 0; font-weight: bold; }}
                .calendar-btn:hover {{ background: #3367d6; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 14px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎉 Booking Confirmed!</h1>
                    <p>Your beauty appointment has been successfully booked</p>
                </div>
                
                <div class="content">
                    <div class="booking-card">
                        <h2>📅 Appointment Details</h2>
                        
                        <div class="detail-row">
                            <span class="detail-label">Service:</span>
                            <span class="detail-value">{booking_details.get('service', 'N/A').title()}</span>
                        </div>
                        
                        <div class="detail-row">
                            <span class="detail-label">Date:</span>
                            <span class="detail-value">{formatted_date}</span>
                        </div>
                        
                        <div class="detail-row">
                            <span class="detail-label">Time:</span>
                            <span class="detail-value">{formatted_time}</span>
                        </div>
                        
                        <div class="detail-row">
                            <span class="detail-label">Duration:</span>
                            <span class="detail-value">{slot.get('duration', 60)} minutes</span>
                        </div>
                        
                        <div class="detail-row">
                            <span class="detail-label">Provider:</span>
                            <span class="detail-value">{provider.get('name', 'Beauty Center')}</span>
                        </div>
                        
                        <div class="detail-row">
                            <span class="detail-label">Location:</span>
                            <span class="detail-value">{provider.get('address', 'Dubai, UAE')}</span>
                        </div>
                        
                        <div class="detail-row">
                            <span class="detail-label">Phone:</span>
                            <span class="detail-value">{provider.get('phone', 'N/A')}</span>
                        </div>
                    </div>
                    
                    <div class="booking-card">
                        <h2>💰 Pricing Details</h2>
                        
                        <div class="detail-row">
                            <span class="detail-label">Service Fee:</span>
                            <span class="detail-value">AED {pricing.get('base_price', 0)}</span>
                        </div>
                        
                        <div class="detail-row">
                            <span class="detail-label">Tax (5%):</span>
                            <span class="detail-value">AED {pricing.get('tax', 0)}</span>
                        </div>
                        
                        <div class="price-total">
                            Total: AED {pricing.get('total_price', 0)}
                        </div>
                    </div>
                    
                    <div style="text-align: center;">
                        <a href="{calendar_link}" class="calendar-btn">📅 Add to Google Calendar</a>
                    </div>
                    
                    <div class="footer">
                        <p><strong>Important Notes:</strong></p>
                        <p>• Please arrive 10 minutes early for your appointment</p>
                        <p>• Cancellation policy: 24 hours advance notice required</p>
                        <p>• For any changes, please contact the provider directly</p>
                        
                        <p style="margin-top: 30px;">
                            <small>This is an automated message from Beauty Booking Agent</small>
                        </p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _create_google_calendar_link(self, booking_details: Dict[str, Any]) -> str:
        """Create Google Calendar link for the booking"""
        
        provider = booking_details.get('provider', {})
        slot = booking_details.get('selected_slot', {})
        pricing = booking_details.get('pricing', {})
        
        # Format datetime
        start_time = slot.get('start', datetime.now())
        start_time = self._parse_datetime(start_time) if isinstance(start_time, str) else start_time
        
        end_time = slot.get('end')
        if isinstance(end_time, str):
            end_time = self._parse_datetime(end_time)
        elif not end_time:
            end_time = start_time + timedelta(minutes=slot.get('duration', 60))
        
        # Format for Google Calendar (YYYYMMDDTHHMMSSZ)
        start_str = start_time.strftime("%Y%m%dT%H%M%SZ")
        end_str = end_time.strftime("%Y%m%dT%H%M%SZ")
        
        # Create event details
        title = f"{booking_details.get('service', 'Beauty Appointment').title()} - {provider.get('name', 'Beauty Center')}"
        location = provider.get('address', 'Dubai, UAE')
        description = f"""
Beauty Appointment Details:
• Service: {booking_details.get('service', 'N/A').title()}
• Provider: {provider.get('name', 'Beauty Center')}
• Phone: {provider.get('phone', 'N/A')}
• Total Cost: AED {pricing.get('total_price', 0)}

Please arrive 10 minutes early.
Cancellation policy: 24 hours advance notice required.
        """.strip()
        
        # Create Google Calendar URL
        base_url = "https://calendar.google.com/calendar/render"
        params = {
            'action': 'TEMPLATE',
            'text': title,
            'dates': f"{start_str}/{end_str}",
            'location': location,
            'details': description
        }
        
        # Build URL
        param_string = "&".join([f"{k}={quote(str(v))}" for k, v in params.items()])
        calendar_url = f"{base_url}?{param_string}"
        
        return calendar_url
    
    def _create_calendar_invite(self, booking_details: Dict[str, Any]) -> str:
        """Create ICS calendar invite content"""
        
        provider = booking_details.get('provider', {})
        slot = booking_details.get('selected_slot', {})
        
        # Format datetime
        start_time = slot.get('start', datetime.now())
        start_time = self._parse_datetime(start_time) if isinstance(start_time, str) else start_time
        
        end_time = slot.get('end')
        if isinstance(end_time, str):
            end_time = self._parse_datetime(end_time)
        elif not end_time:
            end_time = start_time + timedelta(minutes=slot.get('duration', 60))
        
        # Format for ICS (YYYYMMDDTHHMMSSZ)
        start_str = start_time.strftime("%Y%m%dT%H%M%SZ")
        end_str = end_time.strftime("%Y%m%dT%H%M%SZ")
        
        ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Beauty Booking Agent//EN
BEGIN:VEVENT
UID:booking-{booking_details.get('booking_id', 'temp')}@beautyagent.com
DTSTART:{start_str}
DTEND:{end_str}
SUMMARY:{booking_details.get('service', 'Beauty Appointment').title()} - {provider.get('name', 'Beauty Center')}
DESCRIPTION:Beauty appointment at {provider.get('name', 'Beauty Center')}
LOCATION:{provider.get('address', 'Dubai, UAE')}
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR"""
        
        return ics_content