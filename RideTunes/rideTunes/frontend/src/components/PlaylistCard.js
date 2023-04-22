import React, { useState } from 'react';
import './PlaylistCard.css';
import Modal from './Modal';

const PlaylistCard = ({ provider, accessToken, id, name, imageUrl, description }) => {
  const [showModal, setShowModal] = useState(false);
  const [playlistItems, setPlaylistItems] = useState([]);

  const fetchPlaylistItems = async () => {
    try {
      const response = await fetch(
        `${process.env.REACT_APP_BACKEND_URL}/music/api/playlist_items/?provider=${provider}&access_token=${accessToken}&playlist_id=${id}`,
        {
          credentials: 'include',
        }
      );
      if (response.ok) {
        const data = await response.json();
        console.log('Playlist items data:', data);
        setPlaylistItems(data.playlist_items);
      } else {
        console.error(`Error fetching playlist items: ${response.statusText}`);
      }
    } catch (error) {
      console.error(`Error fetching playlist items: ${error}`);
    }
  };

  const handleOpenModal = async () => {
    await fetchPlaylistItems();
    setShowModal(true);
  };

  return (
    <div className="playlist-card">
      <div className="playlist-image-container">
        <img
          src={imageUrl}
          alt={name}
          className="playlist-image"
          onClick={handleOpenModal}
        />
      </div>
      <div className="playlist-details">
        <h3 className="playlist-name">{name}</h3>
        <p className="playlist-description">{description}</p>
      </div>
      {showModal && (
        <Modal onClose={() => setShowModal(false)}>
          <h2>Playlist Items</h2>
          <ul>
            {playlistItems.map((item) => (
              <li key={item.id}>
                {provider === 'spotify'
                  ? item.track.name
                  : item.snippet.title}
              </li>
            ))}
          </ul>
        </Modal>
      )}
    </div>
  );
};

export default PlaylistCard;
