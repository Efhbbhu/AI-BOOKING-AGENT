// Firebase configuration for authentication
import { initializeApp } from 'firebase/app';
import { 
  getAuth, 
  GoogleAuthProvider, 
  signInWithPopup, 
  signInWithRedirect,
  getRedirectResult,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  sendPasswordResetEmail,
  signOut, 
  onAuthStateChanged 
} from 'firebase/auth';

// Firebase config - can use environment variables for production
const firebaseConfig = {
  apiKey: process.env.REACT_APP_FIREBASE_API_KEY ,
  authDomain: process.env.REACT_APP_FIREBASE_AUTH_DOMAIN ,
  projectId: process.env.REACT_APP_FIREBASE_PROJECT_ID ,
  storageBucket: process.env.REACT_APP_FIREBASE_STORAGE_BUCKET ,
  messagingSenderId: process.env.REACT_APP_FIREBASE_MESSAGING_SENDER_ID ,
  appId: process.env.REACT_APP_FIREBASE_APP_ID ,
  measurementId: process.env.REACT_APP_FIREBASE_MEASUREMENT_ID 
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const googleProvider = new GoogleAuthProvider();

// Authentication functions
export const signInWithGoogle = async () => {
  try {
    // First try popup method
    const result = await signInWithPopup(auth, googleProvider);
    return {
      success: true,
      user: {
        uid: result.user.uid,
        displayName: result.user.displayName,
        email: result.user.email,
        photoURL: result.user.photoURL
      }
    };
  } catch (error) {
    // If popup is blocked, try redirect method
    if (error.code === 'auth/popup-blocked') {
      console.log('🔄 Popup blocked, using redirect method...');
      try {
        await signInWithRedirect(auth, googleProvider);
        // The redirect will handle the rest, so we return a pending state
        return {
          success: true,
          redirecting: true,
          message: 'Redirecting to Google Sign-In...'
        };
      } catch (redirectError) {
        return {
          success: false,
          error: `Redirect failed: ${redirectError.message}`
        };
      }
    }
    
    return {
      success: false,
      error: error.message
    };
  }
};

// Function to handle redirect result
export const handleRedirectResult = async () => {
  try {
    const result = await getRedirectResult(auth);
    if (result && result.user) {
      return {
        success: true,
        user: {
          uid: result.user.uid,
          displayName: result.user.displayName,
          email: result.user.email,
          photoURL: result.user.photoURL
        }
      };
    }
    return { success: true, user: null }; // No redirect result
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
};

export const signInWithEmail = async (email, password) => {
  try {
    const result = await signInWithEmailAndPassword(auth, email, password);
    return {
      success: true,
      user: {
        uid: result.user.uid,
        displayName: result.user.displayName || result.user.email.split('@')[0],
        email: result.user.email,
        photoURL: result.user.photoURL
      }
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
};

export const createAccount = async (email, password) => {
  try {
    const result = await createUserWithEmailAndPassword(auth, email, password);
    return {
      success: true,
      user: {
        uid: result.user.uid,
        displayName: result.user.email.split('@')[0], // Use email prefix as display name
        email: result.user.email,
        photoURL: result.user.photoURL
      }
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
};

export const resetPassword = async (email) => {
  try {
    await sendPasswordResetEmail(auth, email);
    return { success: true };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
};

export const signOutUser = async () => {
  try {
    console.log('🔵 Firebase signOut function called');
    console.log('🔵 Current user before signOut:', auth.currentUser);
    await signOut(auth);
    console.log('🔵 Firebase signOut completed successfully');
    console.log('🔵 Current user after signOut:', auth.currentUser);
    return { success: true };
  } catch (error) {
    console.error('🔵 Firebase signOut error:', error);
    return { success: false, error: error.message };
  }
};

export const getCurrentUser = () => {
  return auth.currentUser;
};

export const onAuthChange = (callback) => {
  return onAuthStateChanged(auth, (user) => {
    console.log('🟢 Auth state changed:', user ? `User: ${user.email}` : 'User signed out');
    callback(user);
  });
};