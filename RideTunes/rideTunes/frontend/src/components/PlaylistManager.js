import React, { useState } from 'react';
import Modal from 'react-modal';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faPlusCircle } from '@fortawesome/free-solid-svg-icons';
import './PlaylistManager.css';
import UserPlaylists from './UserPlaylists';



const PlaylistManager = ({ provider, access_token,onPlaylistCreated }) => {
  const [playlists, setPlaylists] = useState([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [playlistName, setPlaylistName] = useState('');

const handleSubmit = async (e) => {
  e.preventDefault();
  if (playlistName) {
    const newPlaylist = await createPlaylist(playlistName);
    if (newPlaylist) {
      setPlaylists([...playlists, newPlaylist]);
      setIsModalOpen(false);
      setPlaylistName('');
      onPlaylistCreated(); // Call the callback function
    }
  }
};


  const getCookie = (name) => {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
  };
  
  const createPlaylist = async (playlistName) => {
    // Implement your API call to create a new playlist
    try {
      const csrfToken = getCookie('csrftoken'); // Get CSRF token from cookies
  
      const response = await fetch(
        `${process.env.REACT_APP_BACKEND_URL}/music/api/create_shared_playlist/`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${access_token}`,
            'X-CSRFToken': csrfToken, // Include CSRF token in headers
          },
          body: JSON.stringify({
            provider: provider,
            access_token: access_token,
            playlist_name: playlistName,
          }),
          credentials: 'include',
        }
      );
  
      if (response.ok) {
        const data = await response.json();
        return data.new_playlist;
      } else {
        console.error('Failed to create a new shared playlist');
        return null;
      }
    } catch (error) {
      console.error('Error creating a new shared playlist:', error);
      return null;
    }
  };
  
  

  return (
    <div className="playlist-manager">
      <button className="create-playlist-btn" onClick={() => setIsModalOpen(true)}>
        <div className="icon-container">
          <FontAwesomeIcon icon={faPlusCircle} size="2x" />
        </div>
        <span>Create Shared Playlist</span>
      </button>
      {/* <ul className="playlist-list">
        {playlists.map((playlist) => (
          <li key={playlist.id} className="playlist-item">
            {playlist.name}
          </li>
        ))}
      </ul> */}
      {isModalOpen && (
      <div className="modal-overlay">
        <div className="modal">
          <div className="modal-header">
            <h2 className="modal-title">Create a Shared Playlist</h2>
            <button className="modal-close" onClick={() => setIsModalOpen(false)}>
              &times;
            </button>
          </div>
          <form onSubmit={handleSubmit}>
            <div className="modal-body">
              <input
                className="modal-input"
                placeholder="Enter playlist name"
                value={playlistName}
                onChange={(e) => setPlaylistName(e.target.value)}
              />
            </div>
            <div className="modal-actions">
              <button type="submit">Create</button>
            </div>
          </form>
        </div>
      </div>
    )}
    </div>
  );
};

export default PlaylistManager;
