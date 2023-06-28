import React from 'react';
import { useParams } from 'react-router-dom';
import ProtectedComponent from './ProtectedComponent';


function Share() {
  const { provider, id } = useParams();

  // Now you can use 'provider' and 'id' in your component.

  return (
    <ProtectedComponent>
    <div>
      <h1>Sharing playlist</h1>
      <p>Provider: {provider}</p>
      <p>Playlist ID: {id}</p>
    </div>
    </ProtectedComponent>
  );
}

export default Share;
