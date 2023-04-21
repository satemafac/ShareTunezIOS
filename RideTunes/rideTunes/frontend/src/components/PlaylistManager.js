import React, { useState } from 'react';
import Modal from 'react-modal';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faPlusCircle } from '@fortawesome/free-solid-svg-icons';
import './PlaylistManager.css';


const PlaylistManager = () => {
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
      }
    }
  };

  const createPlaylist = async (playlistName) => {
    // Implement your API call to create a new playlist
    // Return the new playlist object if successful
  };

  return (
    <div className="playlist-manager">
      <button className="create-playlist-btn" onClick={() => setIsModalOpen(true)}>
        <div className="icon-container">
          <FontAwesomeIcon icon={faPlusCircle} size="2x" />
        </div>
        <span>Create Playlist</span>
      </button>
      <ul className="playlist-list">
        {playlists.map((playlist) => (
          <li key={playlist.id} className="playlist-item">
            {playlist.name}
          </li>
        ))}
      </ul>

      {isModalOpen && (
        <div className="modal-overlay">
          <div className="modal">
            <div className="modal-header">
              <h2 className="modal-title">Create Playlist</h2>
              <button className="modal-close" onClick={() => setIsModalOpen(false)}>
                &times;
              </button>
            </div>
            <div className="modal-body">
              <input
                className="modal-input"
                placeholder="Enter playlist name"
                value={playlistName}
                onChange={(e) => setPlaylistName(e.target.value)}
              />
            </div>
            <div className="modal-actions">
              <button onClick={handleSubmit}>Create</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PlaylistManager;
