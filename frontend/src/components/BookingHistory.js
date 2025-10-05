import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  Alert,
  CircularProgress,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Rating,
  Divider
} from '@mui/material';
import {
  History as HistoryIcon,
  Phone as PhoneIcon,
  Star as StarIcon,
  Schedule as ScheduleIcon,
  Cancel as CancelIcon,
  Notifications as NotificationsIcon
} from '@mui/icons-material';

const BookingHistory = ({ user }) => {
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false);
  const [bookingToCancel, setBookingToCancel] = useState(null);
  const [cancelling, setCancelling] = useState(false);

  useEffect(() => {
    if (user) {
      fetchBookings();
    }
  }, [user]);

  const fetchBookings = async () => {
    if (!user) return;

    setLoading(true);
    setError('');

    try {
      const response = await fetch(`/bookings?user_id=${user.uid}`);
      const data = await response.json();

      console.log('Bookings API response:', data);

      if (response.ok) {
        console.log('Bookings received:', data.bookings);
        setBookings(data.bookings || []);
      } else {
        throw new Error(data.error || 'Failed to fetch bookings');
      }
    } catch (err) {
      console.error('Fetch bookings error:', err);
      setError(err.message || 'Failed to load booking history');
    } finally {
      setLoading(false);
    }
  };

  const handleCancelBooking = async () => {
    if (!bookingToCancel) return;

    setCancelling(true);

    try {
      const response = await fetch(`/bookings/${bookingToCancel.id}/cancel`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          uid: user.uid
        })
      });

      const data = await response.json();

      if (response.ok && data.success) {
        setBookings(bookings.map(booking => 
          booking.id === bookingToCancel.id 
            ? { ...booking, status: 'cancelled' }
            : booking
        ));
        setCancelDialogOpen(false);
        setBookingToCancel(null);
      } else {
        throw new Error(data.error || 'Failed to cancel booking');
      }
    } catch (err) {
      console.error('Cancel booking error:', err);
      setError(err.message || 'Failed to cancel booking');
    } finally {
      setCancelling(false);
    }
  };

  const handleNotifyBooking = async (booking) => {
    try {
      // Get FCM token from localStorage
      const fcmToken = localStorage.getItem('fcm_token');
      
      // Use the raw datetime from booking
      // Priority: start > time (time has full datetime, date is corrupted/truncated)
      const rawDateTime = booking.start || booking.time || booking.date;
      
      console.log('handleNotifyBooking - rawDateTime:', rawDateTime);
      
      // Convert to ISO string if needed
      let dateTimeStr = rawDateTime;
      if (rawDateTime && typeof rawDateTime === 'object' && rawDateTime.toISOString) {
        dateTimeStr = rawDateTime.toISOString();
      } else if (rawDateTime && typeof rawDateTime === 'object') {
        // Handle Firebase timestamp
        dateTimeStr = new Date(rawDateTime._seconds * 1000 || rawDateTime.seconds * 1000).toISOString();
      } else if (typeof rawDateTime === 'string') {
        // Try to parse and convert to ISO format
        try {
          const parsedDate = new Date(rawDateTime);
          if (!isNaN(parsedDate.getTime())) {
            dateTimeStr = parsedDate.toISOString();
            console.log('Converted string to ISO:', dateTimeStr);
          }
        } catch (e) {
          console.error('Failed to parse datetime:', e);
        }
      }
      
      console.log('Sending dateTimeStr to backend:', dateTimeStr);
      
      const response = await fetch('/send-notification', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: user.uid,
          user_email: user.email,
          fcm_token: fcmToken,
          booking_id: booking.id,
          service: booking.service,
          provider: booking.provider,
          date: dateTimeStr,
          time: dateTimeStr,
          send_email: true,
          send_fcm: true
        })
      });

      const data = await response.json();
      
      console.log('Notification API response:', data);
      
      if (data.success) {
        setError(''); // Clear any previous errors
        alert('Notification sent successfully! ✅');
      } else {
        // Show detailed error information
        const errorDetails = data.results 
          ? `Email: ${data.results.email?.error || 'OK'}, FCM: ${data.results.fcm?.error || 'OK'}`
          : data.error;
        throw new Error(errorDetails || 'Failed to send notifications');
      }
    } catch (err) {
      console.error('Notification error:', err);
      setError(err.message || 'Failed to send notifications');
      alert(`Failed to send notification:\n${err.message}`);
    }
  };

  const getStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case 'confirmed':
        return 'success';
      case 'pending':
        return 'warning';
      case 'cancelled':
        return 'error';
      case 'completed':
        return 'info';
      default:
        return 'default';
    }
  };

  const formatDateTime = (dateStr, timeStr) => {
    try {
      // Try multiple sources for the datetime
      let dateToUse = dateStr || timeStr;
      
      // Debug log to see what we're getting
      console.log('formatDateTime input:', { dateStr, timeStr, dateToUse });
      
      // If we have a valid date/time string or object
      if (dateToUse) {
        let date;
        
        // Handle different input formats
        if (typeof dateToUse === 'string') {
          // Remove any timezone abbreviations that might cause issues
          let cleanedDate = dateToUse.replace(/\s*GMT.*$/i, '').trim();
          
          // Try parsing the cleaned date string
          date = new Date(cleanedDate);
          
          // If that failed, try with the original string
          if (isNaN(date.getTime())) {
            date = new Date(dateToUse);
          }
        } else if (dateToUse instanceof Date) {
          date = dateToUse;
        } else if (dateToUse && typeof dateToUse === 'object') {
          // Handle Firebase timestamp-like objects
          if (dateToUse._seconds) {
            date = new Date(dateToUse._seconds * 1000);
          } else if (dateToUse.seconds) {
            date = new Date(dateToUse.seconds * 1000);
          } else {
            // Try converting to date
            date = new Date(dateToUse);
          }
        } else {
          // Try converting to date
          date = new Date(dateToUse);
        }
        
        // Check if date is valid
        if (date && !isNaN(date.getTime())) {
          const timeZone = 'Asia/Dubai';
          const dateFormatter = new Intl.DateTimeFormat('en-US', {
            weekday: 'short',
            month: 'short',
            day: '2-digit',
            year: 'numeric',
            timeZone
          });
          const timeFormatter = new Intl.DateTimeFormat('en-US', {
            hour: 'numeric',
            minute: '2-digit',
            hour12: true,
            timeZone
          });

          const formattedResult = {
            date: `${dateFormatter.format(date)} (GST)`,
            time: `${timeFormatter.format(date)} Gulf Standard Time`
          };

          console.log('formatDateTime result:', formattedResult);
          return formattedResult;
        }
      }
      
      console.log('formatDateTime fallback triggered - no valid date');
      // Fallback if we can't parse the date
      return { 
        date: 'Date not available', 
        time: 'Time not available' 
      };
    } catch (e) {
      console.error('formatDateTime error:', e);
      return { 
        date: 'Date not available', 
        time: 'Time not available' 
      };
    }
  };

  if (!user) {
    return (
      <Card elevation={2} sx={{ mt: 2 }}>
        <CardContent sx={{ textAlign: 'center', py: 4 }}>
          <HistoryIcon sx={{ fontSize: 60, color: 'text.secondary', mb: 2 }} />
          <Typography variant="h6" color="text.secondary">
            Sign in to view your booking history
          </Typography>
        </CardContent>
      </Card>
    );
  }

  if (loading) {
    return (
      <Card elevation={2} sx={{ mt: 2 }}>
        <CardContent sx={{ textAlign: 'center', py: 4 }}>
          <CircularProgress />
          <Typography variant="body1" sx={{ mt: 2 }}>
            Loading your bookings...
          </Typography>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card elevation={2} sx={{ mt: 2 }}>
        <CardContent>
          <Alert severity="error">
            {error}
          </Alert>
          <Button variant="outlined" onClick={fetchBookings} sx={{ mt: 2 }}>
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (bookings.length === 0) {
    return (
      <Card elevation={2} sx={{ mt: 2 }}>
        <CardContent sx={{ textAlign: 'center', py: 4 }}>
          <HistoryIcon sx={{ fontSize: 60, color: 'text.secondary', mb: 2 }} />
          <Typography variant="h6" color="text.secondary">
            No bookings found
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Your booking history will appear here after you make your first booking.
          </Typography>
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card elevation={2} sx={{ mt: 2 }}>
        <CardContent>
          <Box display="flex" alignItems="center" gap={1} mb={3}>
            <HistoryIcon color="primary" />
            <Typography variant="h5" color="primary">
              Your Booking History
            </Typography>
            <Chip label={`${bookings.length} booking${bookings.length !== 1 ? 's' : ''}`} size="small" />
          </Box>

          {bookings.map((booking) => {
            // Debug log to see the actual booking structure
            console.log('Raw booking data:', booking);
            console.log('booking.start:', booking.start, typeof booking.start);
            console.log('booking.date:', booking.date, typeof booking.date);
            console.log('booking.time:', booking.time, typeof booking.time);
            
            // Try to get the datetime from various fields
            // Priority: start > time > date > created_at
            // NOTE: 'time' before 'date' because existing bookings have corrupted 'date' field
            // 'date' = "Sat, 04 Oc" (truncated), 'time' = "Sat, 04 Oct 2025 15:00:00 GMT" (full)
            let rawDateTime = booking.start || booking.time || booking.date || booking.created_at;
            
            console.log('Selected rawDateTime for display:', rawDateTime, typeof rawDateTime);
            
            // Format the datetime for display
            const { date, time } = formatDateTime(rawDateTime, rawDateTime);
            
            return (
              <Card key={booking.id} variant="outlined" sx={{ mb: 2 }}>
                <CardContent>
                  <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={2}>
                    <Box>
                      <Typography variant="h6" color="primary">
                        {booking.service}
                      </Typography>
                      <Typography variant="subtitle1" color="text.secondary">
                        {booking.provider}
                      </Typography>
                    </Box>
                    <Chip 
                      label={booking.status || 'confirmed'} 
                      color={getStatusColor(booking.status)}
                      size="small"
                    />
                  </Box>

                  <Divider sx={{ my: 2 }} />

                  <Box display="flex" flexWrap="wrap" gap={2} mb={2}>
                    <Box display="flex" alignItems="center" gap={0.5}>
                      <ScheduleIcon fontSize="small" color="primary" />
                      <Typography variant="body2">
                        {date} at {time}
                      </Typography>
                    </Box>

                    {booking.provider_phone && (
                      <Box display="flex" alignItems="center" gap={0.5}>
                        <PhoneIcon fontSize="small" color="primary" />
                        <Typography variant="body2">
                          {booking.provider_phone}
                        </Typography>
                      </Box>
                    )}

                    {booking.provider_rating && (
                      <Box display="flex" alignItems="center" gap={0.5}>
                        <StarIcon fontSize="small" color="primary" />
                        <Rating
                          value={booking.provider_rating}
                          readOnly
                          precision={0.1}
                          size="small"
                        />
                        <Typography variant="body2" color="text.secondary">
                          ({booking.provider_rating})
                        </Typography>
                      </Box>
                    )}
                  </Box>

                  <Box display="flex" justifyContent="space-between" alignItems="center">
                    <Typography variant="h6" color="success.main">
                      {booking.price}
                    </Typography>

                    <Box display="flex" gap={1}>
                      {booking.status?.toLowerCase() === 'confirmed' && (
                        <>
                          <Button
                            variant="outlined"
                            color="primary"
                            size="small"
                            onClick={() => handleNotifyBooking(booking)}
                          >
                            Notify/Mail Me
                          </Button>
                          <Button
                            variant="outlined"
                            color="error"
                            size="small"
                            startIcon={<CancelIcon />}
                            onClick={() => {
                              setBookingToCancel(booking);
                              setCancelDialogOpen(true);
                            }}
                          >
                            Cancel
                          </Button>
                        </>
                      )}
                    </Box>
                  </Box>

                  {booking.created_at && (
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                      Booked on: {new Date(booking.created_at).toLocaleDateString()}
                    </Typography>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </CardContent>
      </Card>

      {/* Cancel Booking Dialog */}
      <Dialog open={cancelDialogOpen} onClose={() => setCancelDialogOpen(false)}>
        <DialogTitle>
          Cancel Booking
        </DialogTitle>
        <DialogContent>
          <Typography variant="body1" gutterBottom>
            Are you sure you want to cancel this booking?
          </Typography>
          {bookingToCancel && (
            <Box mt={2} p={2} bgcolor="grey.50" borderRadius={1}>
              <Typography variant="body2"><strong>Service:</strong> {bookingToCancel.service}</Typography>
              <Typography variant="body2"><strong>Provider:</strong> {bookingToCancel.provider}</Typography>
              <Typography variant="body2"><strong>Date:</strong> {bookingToCancel.date}</Typography>
              <Typography variant="body2"><strong>Time:</strong> {bookingToCancel.time}</Typography>
            </Box>
          )}
          <Alert severity="warning" sx={{ mt: 2 }}>
            This action cannot be undone. Please contact the provider if you need to reschedule.
          </Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCancelDialogOpen(false)} disabled={cancelling}>
            Keep Booking
          </Button>
          <Button 
            onClick={handleCancelBooking} 
            color="error" 
            variant="contained"
            disabled={cancelling}
            startIcon={cancelling ? <CircularProgress size={20} /> : <CancelIcon />}
          >
            {cancelling ? 'Cancelling...' : 'Cancel Booking'}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default BookingHistory;