import React, { useState, useEffect } from 'react';
import './MusicPlayer.css';

const MusicPlayer = ({ provider, access_token }) => {
  const [playerState, setPlayerState] = useState(null);
  const [currentTrack, setCurrentTrack] = useState(null);
  const [currentPlayer, setCurrentPlayer] = useState(null);
  const [devices, setDevices] = useState([]);



  const fetchAvailableDevices = async () => {
    const response = await fetch(
      `${process.env.REACT_APP_BACKEND_URL}/music/api/available_devices/?provider=${provider}&access_token=${access_token}`,
      { credentials: 'include' }
    );
  
    if (response.ok) {
      const data = await response.json();
      console.log(data);
      setDevices(data.devices);
    } else {
      console.error('Failed to fetch available devices');
    }
  };
  
  useEffect(() => {
    console.log('useEffect called');  // Debug line
    console.log('provider', provider);  // Debug line
    console.log('accessToken', access_token);  // Debug line
    if (provider === 'spotify') {
      console.log('fetching available devices');  // Debug line
      fetchAvailableDevices();
    }
  }, [provider, access_token]);
  
  

  useEffect(() => {
    // Initialize the player for Spotify or YouTube here
  }, [provider, access_token]);

  const play = () => {
    // Play the current track for Spotify or YouTube
  };

  const pause = () => {
    // Pause the current track for Spotify or YouTube
  };

  const nextTrack = () => {
    // Go to the next track for Spotify or YouTube
  };

  const previousTrack = () => {
    // Go to the previous track for Spotify or YouTube
  };

  return (
    <div className="music-player">
      <img src={currentTrack?.imageUrl} alt={currentTrack?.name} className="cover-art" />
      <div className="player-controls">
        <button className="player-button" onClick={previousTrack}>
          {/* Add backward icon */}
        </button>
        <button className="player-button" onClick={playerState === 'playing' ? pause : play}>
          {/* Add play/pause icon depending on playerState */}
        </button>
        <button className="player-button" onClick={nextTrack}>
          {/* Add forward icon */}
        </button>
      </div>
    </div>
  );
};

export default MusicPlayer;
