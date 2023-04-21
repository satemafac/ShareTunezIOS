import React, { useState, useEffect } from 'react';
import './UserPlaylists.css';
import PlaylistCard from './PlaylistCard';


const UserPlaylists = ({ provider,username }) => {
  const [playlists, setPlaylists] = useState([]);

  const fetchUserPlaylists = async () => {
    try {
      const accessToken = localStorage.getItem('access_token');
      const provider = localStorage.getItem('provider');
      const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/music/api/user_playlists/?provider=${provider}&access_token=${accessToken}`, {
        credentials: 'include',
      });
      if (response.ok) {
        const data = await response.json();
        console.log('User playlists data:', data); // Log the data to the console
        setPlaylists(data.playlists);
      } else {
        console.error(`Error fetching user playlists: ${response.statusText}`);
      }
    } catch (error) {
      console.error(`Error fetching user playlists: ${error}`);
    }
  };

  const gridStyle = {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
    gridGap: '16px',
    justifyContent: 'center',
  };
    
  useEffect(() => {
    fetchUserPlaylists();
  }, []);

  return (
    <div className="user-playlists">
      <div className="user-playlists-container">
        <h2>{username} Playlists</h2>
        <div className="playlists-grid">
          {playlists.map((playlist) => (
            <PlaylistCard
              key={playlist.id}
              id={playlist.id}
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
      </div>
    </div>
  );
  
  
};

export default UserPlaylists;
