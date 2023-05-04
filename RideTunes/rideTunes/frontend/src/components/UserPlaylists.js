import React, { useState, useEffect } from 'react';
import './UserPlaylists.css';
import PlaylistCard from './PlaylistCard';
import { ClipLoader } from 'react-spinners';

const UserPlaylists = ({ provider, username, playlistUpdated }) => {
  const [playlists, setPlaylists] = useState([]);
  const [loading, setLoading] = useState(true);
  const accessToken = localStorage.getItem('access_token');


  const fetchUserPlaylists = async (forceUpdate = false) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      const provider = localStorage.getItem('provider');
      const cacheKey = `user_playlists_cache_${provider}`;
      const cacheExpiryKey = `user_playlists_cache_expiry_${provider}`;
      const now = Date.now();
      const cacheExpiry = localStorage.getItem(cacheExpiryKey);
  
      if (!forceUpdate && cacheExpiry && now < parseInt(cacheExpiry, 10)) {
        const cachedData = localStorage.getItem(cacheKey);
        if (cachedData) {
          setPlaylists(JSON.parse(cachedData));
          setLoading(false);
          return;
        }
      }
  
      const response = await fetch(
        `${process.env.REACT_APP_BACKEND_URL}/music/api/user_playlists/?provider=${provider}&access_token=${accessToken}`,
        {
          credentials: 'include',
        }
      );
      if (response.ok) {
        const data = await response.json();
        console.log('User playlists data:', data);
        setPlaylists(data.playlists);
  
        // Cache the data
        localStorage.setItem(cacheKey, JSON.stringify(data.playlists));
        localStorage.setItem(cacheExpiryKey, now + 3600000); // 1 hour cache expiry
      } else {
        console.error(`Error fetching user playlists: ${response.statusText}`);
      }
    } catch (error) {
      console.error(`Error fetching user playlists: ${error}`);
    } finally {
      setLoading(false);
    }
  };
  
  // This useEffect will be called only when the component is mounted for the first time
  useEffect(() => {
    fetchUserPlaylists(true);
  }, []); // Removed playlistUpdated dependency

  // Add a new useEffect to listen for playlistUpdated changes and call fetchUserPlaylists accordingly
  useEffect(() => {
    if (playlistUpdated) {
      fetchUserPlaylists(true);
    }
  }, [playlistUpdated]);

  

  return (
    <div className="user-playlists">
      <div className="user-playlists-container">
        <h2>{username} Playlists</h2>
        {loading ? (
          <div className="spinner">
            <ClipLoader color="#123abc" loading={loading} size={50} />
          </div>
        ) : (
          <div className="playlists-grid">
            {playlists.map((playlist) => (
              <PlaylistCard
              key={playlist.id}
              id={playlist.id}
              provider={provider}
              accessToken={accessToken}
              name={
                provider === 'spotify'
                  ? playlist.name
                  : playlist.snippet.title
              }
              imageUrl={
                provider === 'spotify'
                  ? playlist.images[0]?.url
                  : playlist.snippet.thumbnails.high.url
              }
              description={playlist.description}
            />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default UserPlaylists;