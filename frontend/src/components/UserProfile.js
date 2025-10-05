import React, { useState } from 'react';
import {
  Box,
  Avatar,
  IconButton,
  Menu,
  MenuItem,
  Typography,
  Divider,
  ListItemIcon
} from '@mui/material';
import {
  AccountCircle as AccountIcon,
  Logout as LogoutIcon
} from '@mui/icons-material';
import { signOutUser } from '../firebase';

const UserProfile = ({ user }) => {
  const [anchorEl, setAnchorEl] = useState(null);
  const open = Boolean(anchorEl);

  const handleClick = (event) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleLogout = async (e) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    
    console.log('🔴 UserProfile: Logout clicked');
    
    try {
      handleClose(); // Close the menu first
      console.log('🔴 UserProfile: Calling signOutUser...');
      const result = await signOutUser();
      console.log('🔴 UserProfile: signOutUser result:', result);
      
      if (!result.success) {
        console.error('🔴 UserProfile: Logout failed:', result.error);
        alert(`Logout failed: ${result.error}`);
      } else {
        console.log('🔴 UserProfile: Logout successful');
        // Force page reload to clear all state
        window.location.reload();
      }
    } catch (error) {
      console.error('🔴 UserProfile: Logout error:', error);
      alert(`Logout error: ${error.message}`);
    }
  };

  return (
    <Box>
      <IconButton
        onClick={handleClick}
        size="small"
        sx={{ ml: 2 }}
        aria-controls={open ? 'account-menu' : undefined}
        aria-haspopup="true"
        aria-expanded={open ? 'true' : undefined}
      >
        <Avatar 
          src={user.photoURL} 
          alt={user.displayName}
          sx={{ width: 32, height: 32 }}
        >
          {user.displayName?.[0] || user.email?.[0] || '?'}
        </Avatar>
      </IconButton>
      
      <Menu
        anchorEl={anchorEl}
        id="account-menu"
        open={open}
        onClose={handleClose}
        PaperProps={{
          elevation: 0,
          sx: {
            overflow: 'visible',
            filter: 'drop-shadow(0px 2px 8px rgba(0,0,0,0.32))',
            mt: 1.5,
            '& .MuiAvatar-root': {
              width: 32,
              height: 32,
              ml: -0.5,
              mr: 1,
            },
            '&:before': {
              content: '""',
              display: 'block',
              position: 'absolute',
              top: 0,
              right: 14,
              width: 10,
              height: 10,
              bgcolor: 'background.paper',
              transform: 'translateY(-50%) rotate(45deg)',
              zIndex: 0,
            },
          },
        }}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
      >
        {/* User Info */}
        <Box sx={{ px: 2, py: 1 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>
            {user.displayName || 'User'}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {user.email}
          </Typography>
        </Box>
        
        <Divider />
        
        {/* Profile Option */}
        <MenuItem onClick={(e) => { e.stopPropagation(); handleClose(); }}>
          <ListItemIcon>
            <AccountIcon fontSize="small" />
          </ListItemIcon>
          Profile
        </MenuItem>
        
        {/* Logout Option */}
        <MenuItem onClick={handleLogout}>
          <ListItemIcon>
            <LogoutIcon fontSize="small" />
          </ListItemIcon>
          Logout
        </MenuItem>
      </Menu>
    </Box>
  );
};

export default UserProfile;