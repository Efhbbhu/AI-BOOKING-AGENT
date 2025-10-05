import React, { useState, useEffect } from 'react';
import {
  Container,
  Typography,
  Box,
  Chip,
  Alert,
  Snackbar,
  IconButton
} from '@mui/material';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import NotificationsIcon from '@mui/icons-material/Notifications';
import BookingForm from './components/BookingForm';
import BookingResult from './components/BookingResult';
import BookingHistory from './components/BookingHistory';
import AuthComponent from './components/AuthComponent';
import UserProfile from './components/UserProfile';
import FCMService from './fcm';

const theme = createTheme({
  palette: {
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
    background: {
      default: '#f5f5f5',
    },
  },
});

function App() {
  const [currentView, setCurrentView] = useState('booking'); // 'booking', 'result', 'history'
  const [bookingResult, setBookingResult] = useState(null);
  const [user, setUser] = useState(null);
  const [fcmService] = useState(new FCMService());
  const [notificationStatus, setNotificationStatus] = useState('default');
  const [fcmMessage, setFcmMessage] = useState('');

  const handleBookingSubmit = (result) => {
    setBookingResult(result);
    setCurrentView('result');
  };

  const handleSearchAgain = () => {
    setCurrentView('booking');
    setBookingResult(null);
  };

  const handleBookingComplete = (bookingResponse) => {
    if (bookingResponse?.success) {
      setFcmMessage('Booking confirmed successfully! 🎉');
      setCurrentView('history');
    }
  };

  const handleAuthChange = React.useCallback((authUser) => {
    console.log('🟢 App: Auth state changed:', authUser ? `User: ${authUser.email}` : 'User signed out');
    setUser(authUser);
    // If user signs out, go back to booking view
    if (!authUser && currentView === 'history') {
      setCurrentView('booking');
    }
  }, [currentView]);

  // FCM initialization and handlers
  useEffect(() => {
    // Initialize FCM service
    const initFCM = async () => {
      if (fcmService.isSupported()) {
        const status = fcmService.getNotificationStatus();
        setNotificationStatus(status.status);
        
        // Listen for foreground messages
        fcmService.onMessage((payload) => {
          console.log('📨 FCM message received:', payload);
          setFcmMessage(`New notification: ${payload.notification.title}`);
        });
      }
    };
    
    initFCM();
  }, [fcmService]);

  const handleEnableNotifications = async () => {
    try {
      const result = await fcmService.requestPermission();

      if (result.success) {
        setNotificationStatus('enabled');
        setFcmMessage('Push notifications enabled! 🎉');
      } else {
        const denied = result.error === 'Notification permission denied' || result.code === 'permission-denied';
        const unsupported = result.code === 'push-service-error';
        setNotificationStatus(unsupported ? 'unsupported' : denied ? 'denied' : 'default');
        setFcmMessage(`Failed to enable notifications: ${result.error}`);
      }
    } catch (error) {
      console.error('Enable notifications error:', error);
      setNotificationStatus('default');
      const message = error?.message || String(error);
      setFcmMessage(`Failed to enable notifications: ${message}`);
    }
  };

  const renderCurrentView = () => {
    switch (currentView) {
      case 'booking':
        return <BookingForm onBookingSubmit={handleBookingSubmit} user={user} />;
      case 'result':
        return (
          <BookingResult 
            result={bookingResult} 
            onBookSlot={handleBookingComplete}
            onReset={handleSearchAgain}
            user={user}
          />
        );
      case 'history':
        return <BookingHistory user={user} />;
      default:
        return <BookingForm onBookingSubmit={handleBookingSubmit} user={user} />;
    }
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          {/* Header */}
          <Box sx={{ position: 'relative', textAlign: 'center', mb: 4 }}>
            {/* User Profile and Notifications in Top Right */}
            {user && (
              <Box sx={{ position: 'absolute', top: 0, right: 0, display: 'flex', alignItems: 'center', gap: 1 }}>
                {/* Push Notification Toggle */}
                {fcmService.isSupported() && notificationStatus !== 'enabled' && (
                  notificationStatus === 'unsupported' ? (
                    <Chip
                      icon={<NotificationsIcon />}
                      label="Not Available"
                      color="default"
                      size="small"
                      variant="outlined"
                      sx={{ fontSize: '0.75rem', height: 24 }}
                    />
                  ) : (
                    <IconButton
                      color="primary"
                      onClick={handleEnableNotifications}
                      title="Enable Push Notifications"
                      size="small"
                    >
                      <NotificationsIcon />
                    </IconButton>
                  )
                )}
                
                {notificationStatus === 'enabled' && (
                  <Chip 
                    icon={<NotificationsIcon />}
                    label="ON" 
                    color="success"
                    size="small"
                    variant="outlined"
                    clickable
                    onClick={() => setFcmMessage('Notifications are enabled. Disable in browser settings if needed.')}
                    sx={{ fontSize: '0.75rem', height: 24 }}
                  />
                )}
                
                <UserProfile user={user} />
              </Box>
            )}
            
            <Typography variant="h3" component="h1" gutterBottom>
               Beauty & Wellness 
            </Typography>
            <Typography variant="h6" color="text.secondary" gutterBottom>
              Book your services with natural language
            </Typography>

            {/* Navigation */}
            <Box sx={{ mt: 3, display: 'flex', justifyContent: 'center', gap: 1 }}>
              <Chip 
                label="New Booking" 
                onClick={() => setCurrentView('booking')}
                color={currentView === 'booking' ? 'primary' : 'default'}
                clickable
              />
              <Chip 
                label="My Bookings" 
                onClick={() => setCurrentView('history')}
                color={currentView === 'history' ? 'primary' : 'default'}
                clickable
              />
            </Box>
          </Box>

          {/* Show AuthComponent only when user is not logged in */}
          {!user && <AuthComponent onAuthChange={handleAuthChange} />}

          {/* Main Content */}
          {renderCurrentView()}
        </Box>
        
        {/* FCM Message Snackbar */}
        <Snackbar
          open={!!fcmMessage}
          autoHideDuration={6000}
          onClose={() => setFcmMessage('')}
        >
          <Alert 
            onClose={() => setFcmMessage('')} 
            severity="info"
            sx={{ width: '100%' }}
          >
            {fcmMessage}
          </Alert>
        </Snackbar>
      </Container>
    </ThemeProvider>
  );
}

export default App;