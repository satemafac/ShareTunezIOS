import React, { useState } from 'react';
import './PlaylistCard.css';
import Modal from './Modal';
import './PlaylistItems.css';


const PlaylistCard = ({ provider, accessToken, id, name, imageUrl, description }) => {
  const [showModal, setShowModal] = useState(false);
  const [playlistItems, setPlaylistItems] = useState([]);

  const fetchPlaylistItems = async () => {
    try {
      const response = await fetch(
        `${process.env.REACT_APP_BACKEND_URL}/music/api/fetch_playlist_items/?provider=${provider}&access_token=${accessToken}&playlist_id=${id}`,
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
          <div className="playlist-items">
            {playlistItems.map((item) => {
              const track = provider === 'spotify' ? item.track : item.snippet;
              const title = provider === 'spotify' ? track.name : track.title;
              const artist = provider === 'spotify' ? track.artists[0].name : track.videoOwnerChannelTitle.replace(' - Topic', '');
              const thumbnailUrl =
                provider === 'spotify'
                  ? track.album.images[0]?.url
                  : track.thumbnails.default.url;

              return (
                <div key={item.id} className="playlist-item">
                  <img src={thumbnailUrl} alt={title} className="playlist-item-img" />
                  <div className="playlist-item-details">
                    <h3 className="playlist-item-title">{title}</h3>
                    <p className="playlist-item-artist">{artist}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </Modal>
      )}
    </div>
  );
};

export default PlaylistCard;