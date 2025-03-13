import React, { useEffect, useState } from 'react';

export default function WebPlayback({ token }) {
  const [player, setPlayer] = useState(null);
  const [currentTrack, setCurrentTrack] = useState(null);
  const [isPaused, setIsPaused] = useState(false);
  const [deviceId, setDeviceId] = useState(null);

  useEffect(() => {
    const script = document.createElement('script');
    script.src = 'https://sdk.scdn.co/spotify-player.js';
    script.async = true;
    document.body.appendChild(script);

    window.onSpotifyWebPlaybackSDKReady = () => {
      const newPlayer = new window.Spotify.Player({
        name: 'Vite Spotify Player',
        getOAuthToken: cb => cb(token),
        volume: 0.5
      });

      newPlayer.addListener('ready', ({ device_id }) => {
        console.log('Ready with Device ID', device_id);
        setDeviceId(device_id);
      });

      newPlayer.addListener('player_state_changed', state => {
        if (!state) return;
        setCurrentTrack(state.track_window.current_track);
        setIsPaused(state.paused);
      });

      newPlayer.connect();
      setPlayer(newPlayer);

      return () => {
        newPlayer.disconnect();
        document.body.removeChild(script);
      };
    };
  }, [token]);

  // Helper function to programmatically start playback
  function playTrack(deviceId, token, trackUri) {
    fetch(`https://api.spotify.com/v1/me/player/play?device_id=${deviceId}`, {
      method: 'PUT',
      body: JSON.stringify({
        uris: [trackUri] // For example: "spotify:track:6rqhFgbbKwnb9MLmUQDhG6"
      }),
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + token
      }
    })
      .then(response => {
        if (response.ok) {
          console.log("Playback started successfully");
        } else {
          console.error("Error starting playback", response.statusText);
        }
      })
      .catch(error => console.error("Playback error:", error));
  }

  // Button handler to start a specific track
  const handleStartTrack = () => {
    if (deviceId && token) {
      playTrack(deviceId, token, "spotify:track:5gOfC9UzZQzTyShqPMrpjT");
    }
  };

  const handlePlayPause = () => {
    player.togglePlay();
  };

  return (
    <div className="player-container">
      {currentTrack ? (
        <div className="track-info">
          <img 
            src={currentTrack.album.images[0].url} 
            alt="Album Cover" 
          />
          <h2>{currentTrack.name}</h2>
          <p>{currentTrack.artists[0].name}</p>
          <button onClick={handlePlayPause}>
            {isPaused ? 'Play' : 'Pause'}
          </button>
        </div>
      ) : (
        <p>Player is ready, but no track is available on this device.</p>
      )}
      {deviceId && (
        <button onClick={handleStartTrack}>
          Start Specific Track
        </button>
      )}
    </div>
  );
}
