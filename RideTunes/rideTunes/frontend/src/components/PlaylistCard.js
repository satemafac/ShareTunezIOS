import React, { useState } from 'react';
import './PlaylistCard.css';
import Modal from './Modal';
import './PlaylistItems.css';
import GroupAddIcon from '@mui/icons-material/GroupAdd'; // Add this import
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';



const PlaylistCard = ({ provider, accessToken, id, name, imageUrl, description }) => {
  const [showModal, setShowModal] = useState(false);
  const [playlistItems, setPlaylistItems] = useState([]);
  const [anchorEl, setAnchorEl] = useState(null);
  const [showShareByUsernameModal, setShowShareByUsernameModal] = useState(false);
  const [enteredUsername, setEnteredUsername] = useState('');
  const [enteredProvider, setEnteredProvider] = useState('');

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


  const handleShareByUsernameSubmit = async (event) => {
    event.preventDefault();
    const response = await fetch(
      `${process.env.REACT_APP_BACKEND_URL}/music/api/add_user_to_shared_playlist/`,
      {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          playlist_id: id,
          username: enteredUsername,
          creator_provider: provider, // Send the creator's provider
          target_provider: enteredProvider, // Send the user being added provider
        }),
      }
    );
  
    if (response.ok) {
      alert('Playlist shared successfully');
      // Reset the inputs after a successful share
      setEnteredUsername('');
      setEnteredProvider('');
    } else {
      const errorData = await response.json();
      setEnteredUsername('');
      setEnteredProvider('');
      alert(`Error sharing playlist: ${errorData.error}`);
    }
    setShowShareByUsernameModal(false);
  };
  

  const handleOpenModal = async () => {
    await fetchPlaylistItems();
    setShowModal(true);
  };

  const handleMenuOpen = (event) => {
    setAnchorEl(event.currentTarget);
  };
  
  const handleMenuClose = () => {
    setAnchorEl(null);
  };
  
  const handleShareByUsername = () => {
    handleMenuClose();
    setShowShareByUsernameModal(true);
  };
  
  
  const handleShareByQRCode = () => {
    handleMenuClose();
    // Your logic for sharing the playlist by QR code
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
          <div className="modal-header">
            <h2>{name} Playlist</h2>
            <div onClick={handleMenuOpen}> {/* Use onMouseEnter for hover */}
              <GroupAddIcon className="modal-header-icon" />
            </div>
            <Menu
              anchorEl={anchorEl}
              open={Boolean(anchorEl)}
              onClose={handleMenuClose}
              MenuListProps={{
                'aria-labelledby': 'basic-button',
              }}
            >
              <MenuItem onClick={handleShareByUsername}>Share by Username</MenuItem>
              <MenuItem onClick={handleShareByQRCode}>Share by QR Code</MenuItem>
            </Menu>
          </div>
          <div className="playlist-items-container">
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
          </div>
        </Modal>
      )}
  {showShareByUsernameModal && (
    <Modal onClose={() => setShowShareByUsernameModal(false)}>
      <div className="share-by-username-modal">
        <h2>Share Playlist by Username</h2>
        <form onSubmit={handleShareByUsernameSubmit}>
          <input
            type="text"
            placeholder="Enter username"
            value={enteredUsername}
            onChange={(e) => setEnteredUsername(e.target.value)}
          />
          <select
            value={enteredProvider}
            onChange={(e) => setEnteredProvider(e.target.value)}
          >
            <option value="" disabled>
              Select provider
            </option>
            <option value="spotify">Spotify</option>
            <option value="YouTube">YouTube</option>
          </select>
          <button type="submit" disabled={!enteredProvider}>Share</button> {/* Disable the button if enteredProvider is empty */}
        </form>
      </div>
    </Modal>
  )}
    </div>
  );
};

export default PlaylistCard;