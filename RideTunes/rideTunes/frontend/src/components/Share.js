import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import ProtectedComponent from './ProtectedComponent';


function Share() {
  const { provider, id, username} = useParams();
  const [playlistInfo, setPlaylistInfo] = useState(null);


  const fetchPlaylistInfo = async () => {
    try {
      const response = await fetch(
        `${process.env.REACT_APP_BACKEND_URL}/music/api/fetch_playlist_info/?playlist_id=${id}&provider=${provider}&username=${username}`,
        {
          credentials: 'include',
        }
      );
      if (response.ok) {
        const data = await response.json();
        console.log('Playlist info data:', data);
        setPlaylistInfo(data);
      } else {
        console.error(`Error fetching playlist info: ${response.statusText}`);
      }
    } catch (error) {
      console.error(`Error fetching playlist info: ${error}`);
    }
  };

  useEffect(() => {
    fetchPlaylistInfo();
  }, []);  
  

  // Now you can use 'provider' and 'id' in your component.

  return (
    <ProtectedComponent>
    <div>
      <h1>Sharing playlist</h1>
      <p>Provider: {provider}</p>
      <p>Playlist ID: {id}</p>
    </div>
    </ProtectedComponent>
  );
}

export default Share;
