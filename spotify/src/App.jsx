import React, { useState, useEffect } from 'react';
import WebPlayback from './WebPlayback';
import Login from './Login';
import './App.css';

function App() {
  const [token, setToken] = useState('');
  const [tokenError, setTokenError] = useState(null);

  useEffect(() => {
    async function fetchToken() {
      try {
        const response = await fetch('/auth/token');
        const { access_token } = await response.json();
        if (access_token) {
          console.log("Access token fetched: ", access_token);
          setToken(access_token);
        } else {
          setTokenError("No access token returned");
          console.error("No access token returned:", access_token);
        }
      } catch (error) {
        console.error("Error fetching token:", error);
        setTokenError("Error fetching token: " + error.message);
      }
    }
    fetchToken();
  }, []);

  return (
    <div className="app">
      {token ? (
        <WebPlayback token={token} />
      ) : (
        <div>
          <p>{tokenError || "Fetching access token..."}</p>
          <Login />
        </div>
      )}
    </div>
  );
}

export default App

