import React, { useState } from 'react';
import { 
  Paper, 
  TextField, 
  Button, 
  Typography, 
  Box,
  Container
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';

const BookingForm = ({ onBookingSubmit, user }) => {
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!query.trim()) return;
    
    // Allow browsing without authentication, but show user state
    const userForRequest = user || { uid: 'guest_user', isGuest: true };
    
    setIsLoading(true);
    
    try {
      const response = await fetch('/book', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          uid: userForRequest.uid,
          query: query.trim()
        }),
      });

      const data = await response.json();
      
      if (data.success) {
        onBookingSubmit(data);
      } else {
        console.error('Booking request failed:', data.error);
        onBookingSubmit({ 
          success: false, 
          error: data.error || 'Failed to process booking request' 
        });
      }
    } catch (error) {
      console.error('Network error:', error);
      onBookingSubmit({ 
        success: false, 
        error: 'Network error occurred' 
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Container maxWidth="md">
      <Paper elevation={3} sx={{ p: 4, mb: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom align="center">
          Beauty & Wellness Booking Agent
        </Typography>
        
        <Typography variant="body1" color="text.secondary" align="center" sx={{ mb: 3 }}>
          Tell us what service you need in natural language!
        </Typography>

        <Box component="form" onSubmit={handleSubmit}>
          <TextField
            fullWidth
            multiline
            rows={3}
            variant="outlined"
            placeholder="Example: Book me a massage this Friday evening in JLT"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={isLoading}
            sx={{ mb: 2 }}
          />
          
          <Button
            type="submit"
            variant="contained"
            size="large"
            fullWidth
            disabled={isLoading || !query.trim()}
            startIcon={<SearchIcon />}
            sx={{ py: 2 }}
          >
            {isLoading ? 'Finding Services...' : 'Find Services'}
          </Button>
        </Box>

        {!user && (
          <Typography variant="body2" color="info.main" align="center" sx={{ mt: 2 }}>
            Browse services without signing in • Sign in required to make bookings
          </Typography>
        )}

        <Box sx={{ mt: 3 }}>
          <Typography variant="h6" gutterBottom>Example Queries:</Typography>
          <Typography variant="body2" color="text.secondary">
            • "Book me a massage this Friday evening in JLT"<br/>
            • "I need a manicure appointment tomorrow afternoon in Business Bay"<br/>
            • "Find me a facial treatment on Saturday morning"<br/>
            • "Schedule a haircut this Wednesday afternoon in Marina"<br/>
            • "I want a pedicure on Monday evening downtown"
          </Typography>
        </Box>
      </Paper>
    </Container>
  );
};

export default BookingForm;