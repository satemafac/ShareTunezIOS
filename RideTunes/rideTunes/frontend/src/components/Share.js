import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useNavigate } from 'react-router-dom';  // Replace useHistory with useNavigate in your imports.
import ProtectedComponent from './ProtectedComponent';
import styled, { keyframes, css } from 'styled-components';

// Keyframes for the scrolling text animation
const scroll = keyframes`
  0% {
    transform: translateX(0%);
  }
  100% {
    transform: translateX(-100%);
  }
`;

const PlaylistContainer = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100vh;
  background: linear-gradient(to right, #f5f5f5, #3f51b5);
`;

const PlaylistImage = styled.img`
  width: 200px;
  height: 200px;
  border-radius: 10%;
  object-fit: cover;
`;

const PlaylistTitle = styled.h2`
  margin-top: 20px;
  text-align: center;
`;

const PlaylistDescription = styled.p`
  text-align: center;
`;

const SharedBy = styled.p`
  margin-bottom: 30px;
`;

const Button = styled.button`
  margin: 10px;
  padding: 10px 20px;
  font-size: 1em;
  border-radius: 5px;
  border: none;
  color: white;
  cursor: pointer;
`;

const AddButton = styled(Button)`
  background-color: #4CAF50;
`;

const CancelButton = styled(Button)`
  background-color: #f44336;
`;

const TrackListButton = styled(Button)`
  background-color: transparent;
  border: 1px solid #3f51b5;
  color: #3f51b5;
  font-size: 1.2em; // increased font size to make the icon larger
  padding: 5px 10px;
`;

const TrackList = styled.ul`
  list-style-type: none;
  padding: 0;
  max-height: 200px;
  overflow: auto;
  border: 1px solid #3f51b5; // add this line for border
  border-radius: 5px; // add this line for border radius
  padding: 10px; // add some padding
`;


const Track = styled.div`
  display: grid;
  grid-template-columns: 2fr 2fr 1fr; // Adjust according to your needs
  gap: 20px; // To give some space between columns
  align-items: center;
  padding: 5px;
  border-bottom: 1px solid #ccc;
`;

const TrackName = styled.span`
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
  text-align: left;
  animation: ${props => props.isLong ? css`${scroll} 10s linear infinite` : 'none'};
`;

const TrackArtist = styled.span`
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
  text-align: left;
`;

const TrackDuration = styled.span`
  text-align: right; // Align the text to the right
`;



function formatDuration(ms) {
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  }
  

function Share() {
  let { provider, id, username } = useParams();
  provider = provider === 'spotify' ? 'Spotify' : provider === 'google-oauth2' ? 'YouTube' : provider;
  const [playlistInfo, setPlaylistInfo] = useState(null);
  const [showTracks, setShowTracks] = useState(false);
  const navigate = useNavigate();  // Use useNavigate instead of useHistory.

  const fetchPlaylistInfo = async () => {
    try {
      const response = await fetch(
        `${process.env.REACT_APP_BACKEND_URL}/music/api/fetch_playlist_info/?playlist_id=${id}&provider=${provider}&username=${username}`,
        {
          credentials: 'include',
        }
      );
      if (response.ok) {
        const data = await response.json();
        console.log('Playlist info data:', data);
        setPlaylistInfo(data);
      } else {
        console.error(`Error fetching playlist info: ${response.statusText}`);
      }
    } catch (error) {
      console.error(`Error fetching playlist info: ${error}`);
    }
  };

  useEffect(() => {
    fetchPlaylistInfo();
  }, []);

  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  const acceptInviteQr = async () => {
    const receiverUsername = localStorage.getItem('user_name');
    let receiverService = localStorage.getItem('provider');
    receiverService = receiverService === 'spotify' ? 'Spotify' : receiverService === 'google-oauth2' ? 'YouTube' : receiverService;
    const url = `${process.env.REACT_APP_BACKEND_URL}/music/api/accept_invite_qr/`;  // Make sure the endpoint has a trailing slash
    const bodyData = {
        master_playlist_id: id,
        playlist_name: playlistInfo.name,
        master_playlist_service: provider,
        sender_username: username,
        receiver_username: receiverUsername,
        receiver_service: receiverService,
    };

    try {
        const response = await fetch(url, {
            method: 'POST',  // Changed from GET to POST
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            body: JSON.stringify(bodyData),  // Added body data
            credentials: 'include',
        });

        if (response.ok) {
            navigate('/music');  // redirect user to success page
        } else {
            console.error(`Error accepting invite: ${response.statusText}`);
        }
    } catch (error) {
        console.error(`Error accepting invite: ${error}`);
    }
};

  const handleAdd = () => {
    acceptInviteQr();
  };

  const handleCancel = () => {
    navigate('/music');
  };

  const toggleTracks = () => {
    setShowTracks(!showTracks);
  };

  return (
    <ProtectedComponent>
      <PlaylistContainer>
        {playlistInfo && (
          <>
            <PlaylistImage src={playlistInfo.imageUrl} alt="Playlist" />
            <PlaylistTitle>
              {playlistInfo.name} ({playlistInfo.trackCount} tracks)
              <TrackListButton onClick={toggleTracks}>
                ☰
              </TrackListButton>
            </PlaylistTitle>
            {showTracks && (
                <TrackList>
                    {playlistInfo.tracks.map((track, index) => (
                        <Track key={index}>
                        <TrackName isLong={track.name.length > 25}>
                            {track.name}
                        </TrackName>
                        <TrackArtist>{track.artist}</TrackArtist>
                        <TrackDuration>{provider === 'Spotify' ? formatDuration(track.duration) : track.duration}</TrackDuration>
                        </Track>
                    ))}
                </TrackList>
                )}
            <PlaylistDescription>{playlistInfo.description}</PlaylistDescription>
            <SharedBy>Shared by: {username} ({provider})</SharedBy>
            <AddButton onClick={handleAdd}>Add to Playlist</AddButton>
            <CancelButton onClick={handleCancel}>Cancel</CancelButton>
          </>
        )}
      </PlaylistContainer>
    </ProtectedComponent>
  );}

export default Share;