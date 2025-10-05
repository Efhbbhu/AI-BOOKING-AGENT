import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Button,
  Box,
  Typography,
  Avatar,
  Alert,
  CircularProgress,
  TextField,
  Tabs,
  Tab,
  Link
} from '@mui/material';
import { 
  Google as GoogleIcon, 
  Logout as LogoutIcon,
  Email as EmailIcon,
  PersonAdd as PersonAddIcon
} from '@mui/icons-material';
import { 
  signInWithGoogle, 
  handleRedirectResult,
  signInWithEmail,
  createAccount,
  resetPassword,
  signOutUser, 
  onAuthChange as onFirebaseAuthChange 
} from '../firebase';

const AuthComponent = ({ onAuthChange }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [authTab, setAuthTab] = useState(0); // 0: Sign In, 1: Sign Up
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [emailLoading, setEmailLoading] = useState(false);
  const [resetEmailSent, setResetEmailSent] = useState(false);

  useEffect(() => {
    // Handle redirect result first
    const checkRedirectResult = async () => {
      const result = await handleRedirectResult();
      if (!result.success && result.error) {
        setError(result.error);
      }
    };
    
    checkRedirectResult();
    
    // Listen for authentication state changes
    console.log('🟢 Setting up auth state listener');
    
    const unsubscribe = onFirebaseAuthChange((user) => {
      console.log('🟢 Auth state changed in component:', user ? `User: ${user.email}` : 'User signed out');
      
      setUser(user);
      setLoading(false);
      
      if (onAuthChange) {
        onAuthChange(user);
      }
    });

    return () => {
      console.log('🟢 Cleaning up auth state listener');
      if (typeof unsubscribe === 'function') {
        unsubscribe();
      }
    };
  }, [onAuthChange]);

  const handleGoogleSignIn = async () => {
    setLoading(true);
    setError('');
    
    const result = await signInWithGoogle();
    
    if (!result.success) {
      if (result.error.includes('popup-blocked')) {
        setError('Popup was blocked by your browser. Please allow popups for this site or try again.');
      } else {
        setError(result.error);
      }
    } else if (result.redirecting) {
      // Keep loading state for redirect
      setError('');
      // Don't set loading to false as we're redirecting
      return;
    }
    
    setLoading(false);
  };

  const handleSignOut = async () => {
    console.log('🔴 Logout clicked');
    setLoading(true); // Show loading state
    setError('');
    
    const result = await signOutUser();
    
    if (!result.success) {
      setError(result.error);
      setLoading(false); // Reset loading on error
    }
    // Auth state change will be handled by the listener, which will set loading to false
  };

  const handleEmailAuth = async (e) => {
    e.preventDefault();
    if (!email || !password) return;

    setEmailLoading(true);
    setError('');

    const result = authTab === 0 
      ? await signInWithEmail(email, password)
      : await createAccount(email, password);

    if (!result.success) {
      setError(result.error);
    }

    setEmailLoading(false);
  };

  const handlePasswordReset = async () => {
    if (!email) {
      setError('Please enter your email address first');
      return;
    }

    setError('');
    const result = await resetPassword(email);
    
    if (result.success) {
      setResetEmailSent(true);
    } else {
      setError(result.error);
    }
  };

  const handleTabChange = (event, newValue) => {
    setAuthTab(newValue);
    setError('');
    setResetEmailSent(false);
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" p={2}>
        <CircularProgress />
      </Box>
    );
  }

  if (user) {
    // User is signed in - don't show anything, UserProfile handles logout
    return null;
  }

  // User is not signed in
  return (
    <Box display="flex" justifyContent="center" sx={{ mb: 2 }}>
      <Card elevation={2} sx={{ width: '100%', maxWidth: 400 }}>
        <CardContent sx={{ py: 3, px: 3 }}>
        <Typography variant="h6" gutterBottom textAlign="center">
          Sign in to Book Services
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }} textAlign="center">
          Please sign in to make bookings and view your booking history.
        </Typography>
        
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {resetEmailSent && (
          <Alert severity="success" sx={{ mb: 2 }}>
            Password reset email sent! Check your inbox.
          </Alert>
        )}
        
        {/* Google Sign In */}
        <Box sx={{ textAlign: 'center', mb: 2 }}>
          <Button
            variant="contained"
            fullWidth
            startIcon={<GoogleIcon />}
            onClick={handleGoogleSignIn}
            disabled={loading}
          >
            {loading ? <CircularProgress size={20} /> : 'Sign in with Google'}
          </Button>
        </Box>

        <Typography variant="body2" color="text.secondary" textAlign="center" sx={{ mb: 1.5 }}>
          or
        </Typography>

        {/* Email Authentication Tabs */}
        <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 1.5 }}>
          <Tabs value={authTab} onChange={handleTabChange} centered size="small">
            <Tab label="Sign In" />
            <Tab label="Sign Up" />
          </Tabs>
        </Box>

        {/* Email Form */}
        <Box component="form" onSubmit={handleEmailAuth}>
          <TextField
            fullWidth
            type="email"
            label="Email Address"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            margin="dense"
            required
            disabled={emailLoading}
            size="small"
          />
          <TextField
            fullWidth
            type="password"
            label="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            margin="dense"
            required
            disabled={emailLoading}
            size="small"
          />
          
          <Button
            type="submit"
            fullWidth
            variant="outlined"
            startIcon={authTab === 0 ? <EmailIcon /> : <PersonAddIcon />}
            disabled={emailLoading || !email || !password}
            sx={{ mt: 2, mb: 1 }}
          >
            {emailLoading ? (
              <CircularProgress size={24} />
            ) : (
              authTab === 0 ? 'Sign In with Email' : 'Create Account'
            )}
          </Button>
        </Box>

        {/* Forgot Password Link */}
        {authTab === 0 && (
          <Box sx={{ textAlign: 'center', mt: 1 }}>
            <Link
              component="button"
              variant="body2"
              onClick={handlePasswordReset}
              disabled={!email}
              sx={{ cursor: 'pointer' }}
            >
              Forgot your password?
            </Link>
          </Box>
        )}
      </CardContent>
    </Card>
    </Box>
  );
};

export default AuthComponent;