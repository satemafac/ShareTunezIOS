import React, { useState } from 'react';
import Modal from 'react-modal';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faPlusCircle, faPlus, faTrash } from '@fortawesome/free-solid-svg-icons';
import './PlaylistManager.css';
import UserPlaylists from './UserPlaylists';



const PlaylistManager = ({ provider, access_token,onPlaylistCreated }) => {
  const [playlists, setPlaylists] = useState([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [playlistName, setPlaylistName] = useState('');
  const [usernames, setUsernames] = useState(['']);
  const [currentStep, setCurrentStep] = useState(0);
  

  const handleAddUser = () => {
    setUsernames([...usernames, '']);
  };

  const handleUserChange = (index, value) => {
    const newUsers = [...usernames];
    newUsers[index] = value;
    setUsernames(newUsers);
  };

  const handleRemoveUser = (index) => {
    const newUsers = [...usernames];
    newUsers.splice(index, 1);
    setUsernames(newUsers);
  };

  const handleNext = () => {
    if (currentStep === 0 && playlistName) {
      // Only go to the next step if playlistName is not empty
      setCurrentStep(currentStep + 1);
    }
    // Additional validation for other steps can go here
  };

  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

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
            <div className="create-modal-header">
              <h2 className="modal-title">Create a Shared Playlist</h2>
              <button className="modal-close" onClick={() => setIsModalOpen(false)}>
                &times;
              </button>
            </div>
            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                {currentStep === 0 && (
                  <input
                    className="modal-input"
                    placeholder="Enter playlist name"
                    value={playlistName}
                    onChange={(e) => setPlaylistName(e.target.value)}
                  />
                )}
                {currentStep === 1 && (
                  <div>
                  {usernames.map((username, index) => (
                    <div key={index} className="user-input-row">
                      <input
                        className="modal-input"
                        placeholder="Add User"
                        value={username}
                        onChange={(e) => handleUserChange(index, e.target.value)}
                        style={{ flexGrow: 1 }}
                      />
                      {index > 0 && (
                        <button type="button" onClick={() => handleRemoveUser(index)} style={{ marginLeft: 'auto' }}>
                          <FontAwesomeIcon icon={faTrash} size="1x" />
                        </button>
                      )}
                    </div>
                  ))}
                  <button type="button" className="create-playlist-btn" onClick={handleAddUser} style={{margin: "auto", display: "flex", justifyContent: "center"}}>
                    <div className="icon-container">
                      <FontAwesomeIcon icon={faPlus} size="1x" />
                    </div>
                  </button>
                </div>
                )}
                {/* Additional steps can go here */}
              </div>
              <div className="modal-actions">
                <button type="button" onClick={handleBack} disabled={currentStep === 0}>
                  Back
                </button>
                <button type="button" onClick={handleNext} disabled={currentStep === 1 && !playlistName}>
                  Next
                </button>
                {currentStep === 1 && <button type="submit">Create</button>}
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default PlaylistManager;
