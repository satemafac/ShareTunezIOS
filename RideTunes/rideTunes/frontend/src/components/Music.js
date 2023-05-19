import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useLocation } from 'react-router-dom';
import './Music.css';
import ProtectedComponent from './ProtectedComponent';
import PlaylistManager from './PlaylistManager';
import UserPlaylists from './UserPlaylists';
import MusicPlayer from './MusicPlayer';
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline';
import LibraryMusicIcon from '@mui/icons-material/LibraryMusic';
import Badge from '@mui/material/Badge';
import IconButton from '@mui/material/IconButton';
import NotificationsIcon from '@mui/icons-material/Notifications';
import Modal from '@mui/material/Modal';

const Music = () => {
  const [isDropdownVisible, setDropdownVisible] = useState(false);
  const [userProfile, setUserProfile] = useState({ display_name: '', profile_image: '' });
  const location = useLocation();
  const dropdownRef = useRef(null);
  const navigate = useNavigate();
  const provider = localStorage.getItem('provider');
  const [username, setUsername] = useState('');
  const [activeTab, setActiveTab] = useState(0); // Change this line
  const [playlistUpdated, setPlaylistUpdated] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [isNotificationModalOpen, setNotificationModalOpen] = useState(false);



  const handleChange = (event, newValue) => {
    setActiveTab(newValue);
  };


  
  useEffect(() => {
    const token = getCookie('jwt');
    const csrfToken = getCookie('csrfToken');
    const provider = getCookie('provider');
    const accessToken = getCookie('access_token');
  
    if (token) {
      localStorage.setItem('jwt', token);
    }
  
    if (csrfToken) {
      document.cookie = `csrftoken=${csrfToken}; path=/;`;
    }
  
    if (provider) {
      localStorage.setItem('provider', provider);
    }
  
    if (accessToken) {
      localStorage.setItem('access_token', accessToken);
    }
  
    // Clear cookies after storing values in local storage
    document.cookie = 'jwt=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
    document.cookie = 'csrfToken=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
    document.cookie = 'provider=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
    document.cookie = 'access_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
  }, []);
  

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setDropdownVisible(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [dropdownRef]);

  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }
  
  function clearAuthCookies() {
    // Add a list of cookies to be cleared, e.g., 'sessionid', 'csrftoken'
    const authCookies = ['sessionid', 'csrftoken'];
  
    authCookies.forEach((cookieName) => {
      document.cookie = `${cookieName}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`;
    });
  }
  
  const handleLogout = async () => {
    const provider = localStorage.getItem('provider'); // Get the authProvider from localStorage
    const accessToken = localStorage.getItem('access_token'); // Get the provider's access token from localStorage
  
    try {
      const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/music/logout/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken'),
        },
        body: JSON.stringify({ provider, access_token: accessToken }), // Include the provider and access token in the request body
        credentials: 'include',
      });
  
      if (response.ok) {
        // Add a request to Django's logout view
        await fetch(`${process.env.REACT_APP_BACKEND_URL}/music/accounts/logout/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken'),
          },
          credentials: 'include',
        });
  
        localStorage.removeItem('jwt'); // Remove the JWT token from localStorage
        localStorage.removeItem('provider'); // Remove the authProvider from localStorage
        localStorage.removeItem('access_token'); // Remove the provider's access token from localStorage
        clearAuthCookies(); // Clear authentication-related cookies
        navigate('/'); // Navigate to the login page
        window.location.reload(); // Reload the page to reset the state completely
      } else {
        console.error('Logout failed.');
      }
    } catch (error) {
      console.error('Logout error:', error);
    }
  };

  useEffect(() => {
    const fetchNotifications = async () => {
      const response = await fetch(
        `${process.env.REACT_APP_BACKEND_URL}/music/api/fetch_notifications/`,
        { credentials: 'include' }
      );
  
      if (response.ok) {
        const data = await response.json();
        setNotifications(data);
      } else {
        console.error('Failed to fetch notifications');
      }
    };
  
    fetchNotifications();
  }, [isNotificationModalOpen]);
  
  

  useEffect(() => {
    const fetchUserProfile = async () => {
      // Get the provider's access token and provider from local storage
      const accessToken = localStorage.getItem('access_token');
      const provider = localStorage.getItem('provider');
  
      // Include the provider parameter in the fetch request URL
      const response = await fetch(
        `http://localhost:8000/music/api/get_user_profile/?access_token=${accessToken}&provider=${provider}`
      );
  
      if (response.ok) {
        const data = await response.json();
        setUserProfile(data);
        setUsername(data.display_name); // Set the username state here
        console.log(data.profile_image)
      } else {
        console.error(`Error fetching user profile: ${response.statusText}`);
      }
    };
  
    fetchUserProfile();
  }, []);
  
  
  return (
    <ProtectedComponent>
      <div>
        <header className="header">
          <h1 className="title">RideTunes</h1>
          <div className="profile" ref={dropdownRef}>
  <IconButton aria-label="show new notifications" color="inherit" onClick={() => setNotificationModalOpen(true)}>
    <Badge badgeContent={notifications.length} color="secondary">
      <NotificationsIcon />
    </Badge>
  </IconButton>
  <img
    src={userProfile.profile_image || 'https://via.placeholder.com/40'}
    alt="Profile"
    className="profile-image"
    onClick={() => setDropdownVisible(!isDropdownVisible)}
  />
  <span className="username">{userProfile.display_name}</span>
  {isDropdownVisible && (
    <ul className="dropdown-menu">
      <li onClick={() => console.log('Settings clicked')}>Settings</li>
      <li onClick={handleLogout}>Logout</li>
    </ul>
  )}
</div>

<Modal
  open={isNotificationModalOpen}
  onClose={() => setNotificationModalOpen(false)}
  aria-labelledby="simple-modal-title"
  aria-describedby="simple-modal-description"
>
  <div style={{backgroundColor: 'white', padding: '20px'}}>
    <h2>Notifications</h2>
    {notifications.map((notification, index) => (
      <p key={index}>{notification.message} at {notification.timestamp}</p>
    ))}
  </div>
</Modal>
        </header>
        <main className="content">
          <div className="playlist-creation">
          <PlaylistManager
  provider={provider}
  access_token={localStorage.getItem('access_token')}
  onPlaylistCreated={() => setPlaylistUpdated(!playlistUpdated)}
/>
          </div>
          <Tabs
            value={activeTab}
            onChange={handleChange}
            variant="fullWidth"
            indicatorColor="secondary"
            textColor="secondary"
            aria-label="music app tabs"
          >
            <Tab
              icon={<LibraryMusicIcon />}
              label="Playlists"
              value={0} // Change this line
            />
            <Tab
              icon={<PlayCircleOutlineIcon />}
              label="Player"
              value={1} // Change this line
            />
          </Tabs>
          <div
        className="user-playlists"
        style={activeTab !== 0 ? { display: "none" } : {}}
      >
        <UserPlaylists
          provider={provider}
          username={username}
          playlistUpdated={playlistUpdated}
        />
      </div>
      <div
        className="music-player"
        style={activeTab !== 1 ? { display: "none" } : {}}
      >
        <MusicPlayer />
      </div>
        </main>
      </div>
    </ProtectedComponent>
  );  
};

export default Music;