import React from 'react';
import './MusicPlayer.css';

const MusicPlayer = ({ provider, accessToken }) => {
  const play = () => {
    // Play the music using the provider's API
  };

  const pause = () => {
    // Pause the music using the provider's API
  };

  const forward = () => {
    // Skip to the next track using the provider's API
  };

  const backward = () => {
    // Skip to the previous track using the provider's API
  };

  return (
    <div className="music-player">
      <button className="music-player-button backward" onClick={backward}>
        {/* Add backward icon */}
      </button>
      <button className="music-player-button play" onClick={play}>
        {/* Add play icon */}
      </button>
      <button className="music-player-button pause" onClick={pause}>
        {/* Add pause icon */}
      </button>
      <button className="music-player-button forward" onClick={forward}>
        {/* Add forward icon */}
      </button>
    </div>
  );
};

export default MusicPlayer;
