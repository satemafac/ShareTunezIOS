import React from 'react';
import './PlaylistCard.css';

const PlaylistCard = ({ id, name, imageUrl, description }) => {
  return (
    <div className="playlist-card">
      <div className="playlist-image-container">
        <img src={imageUrl} alt={name} className="playlist-image" />
      </div>
      <div className="playlist-details">
        <h3 className="playlist-name">{name}</h3>
        <p className="playlist-description">{description}</p>
      </div>
    </div>
  );
};

export default PlaylistCard;
