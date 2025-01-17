import React, { useState } from 'react';
import './PlaylistCard.css';
import Modal from './Modal';
import './PlaylistItems.css';
import GroupAddIcon from '@mui/icons-material/GroupAdd'; // Add this import
import DeleteIcon from '@mui/icons-material/Delete';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import QRCode from 'qrcode.react';



const PlaylistCard = ({ provider, accessToken, id, name, imageUrl, description,username }) => {
  const [showModal, setShowModal] = useState(false);
  const [playlistItems, setPlaylistItems] = useState([]);
  const [anchorEl, setAnchorEl] = useState(null);
  const [showShareByUsernameModal, setShowShareByUsernameModal] = useState(false);
  const [enteredUsername, setEnteredUsername] = useState('');
  const [enteredProvider, setEnteredProvider] = useState('');
  const [showQRCodeModal, setShowQRCodeModal] = useState(false);
  const user_name = localStorage.getItem('user_name'); // Get the provider's access token from localStorage


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
      `${process.env.REACT_APP_BACKEND_URL}/music/api/send_invite/`,
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
  
    const responseData = await response.json(); // Extract JSON data from response
  
    if (response.ok) {
      alert(responseData.message); // Alert the message from the server
    } else {
      alert(`Error sharing playlist: ${responseData.error}`);
    }
  
    // Reset the inputs after a successful share
    setEnteredUsername('');
    setEnteredProvider('');
    setShowShareByUsernameModal(false);
  };

  const deletePlaylist = async () => {
    if (window.confirm("Are you sure you want to delete this playlist?")) {
        try {
            const csrfToken = document.cookie
                .split('; ')
                .find(row => row.startsWith('csrftoken='))
                .split('=')[1];
                
            const response = await fetch(
                `${process.env.REACT_APP_BACKEND_URL}/music/api/delete_playlist/`,
                {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    },
                    credentials: 'include',
                    body: JSON.stringify({
                        provider: provider,
                        username: user_name,
                        playlist_id: id,
                    })
                }
            );
  
            if (!response.ok) {
                throw new Error(`Error deleting playlist: ${response.statusText}`);
            }
  
            alert('Playlist deleted successfully!');
            window.location.reload();  // Add this line to refresh the page
        } catch (error) {
            alert(`Error deleting playlist: ${error}`);
        }
    }
  };
  
  

  const handleShareByQRCode = () => {
    handleMenuClose();
    setShowQRCodeModal(true); // Show the QR code modal
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
          <div className="modal-footer">
          <button 
            className="delete-button"
            onClick={deletePlaylist}
          >
              <DeleteIcon color="error" />
          </button>
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
            <option value="Spotify">Spotify</option>
            <option value="YouTube">YouTube</option>
          </select>
          <button type="submit" disabled={!enteredProvider}>Share</button> {/* Disable the button if enteredProvider is empty */}
        </form>
      </div>
    </Modal>
  )}
  {showQRCodeModal && (
  <Modal onClose={() => setShowQRCodeModal(false)}>
    <div className="qr-code-modal">
      <h2>Share Playlist by QR Code</h2>
      <QRCode value={`${window.location.origin}/music/share/${provider}/${user_name}/${id}`} />
    </div>
  </Modal>
)}
    </div>
  );
};

export default PlaylistCard;