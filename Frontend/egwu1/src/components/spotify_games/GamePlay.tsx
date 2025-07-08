import React, { useEffect, useState } from 'react';
import { useParams, useLocation, useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import LyricsGame from './games/LyricsGame';
import CrosswordGame from './games/CrosswordGame';
import ArtistGuessGame from './games/ArtistGuessGame';
import TriviaGame from './games/TriviaGame';
import { Alert, AlertDescription } from '@/components/ui/alert';
import api from '@/services/api';

const GamePlay = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  
  // Try to get the gameData from location state first
  const initialGameDataFromState = location.state?.gameData || null;
  const [gameData, setGameData] = useState<any>(initialGameDataFromState);
  const [loading, setLoading] = useState<boolean>(!initialGameDataFromState);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchGameData = async () => {
      setLoading(true);
      try {
        // First try to get the full session data
        const response = await api.get(`/games/api/sessions/${sessionId}/`);
        console.log('Full API response:', response.data);
        
        setGameData({ session: response.data });

        console.log('Processed Game Data:', processedGameData);
        
        setGameData(processedGameData);
      } catch (err: any) {
        console.error('Error fetching game data:', err);
        setError('Failed to load game data.');
      } finally {
        setLoading(false);
      }
    };

    if (!initialGameDataFromState && sessionId) {
      fetchGameData();
    }
  }, [sessionId, initialGameDataFromState]);

  if (loading) {
    return (
      <div className="flex justify-center items-center h-screen text-white">
        Loading...
      </div>
    );
  }

  if (error || !gameData) {
    return (
      <div className="p-4 text-center text-red-500">
        {error || 'No game data found.'}
        <div className="mt-4">
          <Button variant="outline" onClick={() => navigate('/games/dashboard')}>
            Back to Dashboard
          </Button>
        </div>
      </div>
    );
  }

  // Debug logging
  console.log('Full game data object:', JSON.stringify(gameData));
  console.log('Game type:', gameData.session.game_type);
  console.log('Game state:', gameData.session.state);

  // Check if we have valid state
  if (!gameData?.session?.state) {
    return (
      <Alert>
        <AlertDescription>
          No game state found.
          <Button variant="link" onClick={() => window.location.reload()}>
            Retry
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  // For artist guess game, verify the data structure more carefully
  if (gameData.game_type === 'guess_artist') {
    console.log('Artist game data:', gameData.state.game_data);
    // Detailed check for the required data
    const hasGameData = !!gameData.state.game_data;
    const hasRevealedInfo = hasGameData && !!gameData.state.game_data.revealed_info;
    console.log('Has game data:', hasGameData);
    console.log('Has revealed info:', hasRevealedInfo);
    
    if (!hasGameData || !hasRevealedInfo) {
      return (
        <Alert variant="destructive">
          <AlertDescription>
            Missing game data - try restarting
            <div className="mt-2">
              <Button variant="outline" onClick={() => window.location.reload()}>
                Reload
              </Button>
              <Button 
                variant="outline" 
                className="ml-2" 
                onClick={() => navigate('/games/dashboard')}
              >
                Back to Dashboard
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      );
    }
  }

  // Determine which game component to render based on the session's game type.
  const GameComponent = {
    lyrics_text: LyricsGame,
    lyrics_voice: LyricsGame,
    guess_artist: ArtistGuessGame,
    trivia: TriviaGame,
    crossword: CrosswordGame,
  }[gameData.session.game_type];

  if (!GameComponent) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Invalid game type</AlertDescription>
      </Alert>
    );
  }

return (
    <div className="min-h-screen bg-gradient-to-b from-green-900 to-black p-6">
      <div className="max-w-7xl mx-auto">
        {/* =======================================================
            THE FIX IS HERE: Pass specific props for the crossword game
            =======================================================
        */}
        {gameData.session.game_type === 'crossword' ? (
          <CrosswordGame
            sessionId={sessionId!}
            // Pass the data a's explicit props
            songData={gameData.session.state.song_data}
            puzzleData={gameData.session.state.puzzle_data}
          />
        ) : (
          // Other games can still use the initialState prop
          <GameComponent
            sessionId={sessionId!}
            initialState={gameData.session.state}
            onGameComplete={() => {
              setTimeout(() => navigate('/games/dashboard'), 3000);
            }}
            onHomeClick={() => navigate('/games/dashboard')}
          />
        )}
      </div>
    </div>
  );
};

export default GamePlay;