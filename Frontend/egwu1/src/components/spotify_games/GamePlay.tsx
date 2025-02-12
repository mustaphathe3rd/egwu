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
    // If no gameData was passed via location, fetch it using the sessionId.
    if (!gameData && sessionId) {
      const fetchGameData = async () => {
        try {
          console.log('Fetching game data for session:', sessionId);
          const response = await api.get(`/games/api/sessions/${sessionId}/`);
          console.log('Received game data:', response.data);
          setGameData(response.data);
        } catch (err: any) {
          console.error('Error fetching game data:', err);
          setError('Failed to load game data.');
        } finally {
          setLoading(false);
                }
            };
            fetchGameData();
            }
        }, [gameData, sessionId]);

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
        </div>
        );
    }

    // Add this before returning the GameComponent
    console.log('Current game state:', gameData.current_state);
    if (!gameData.current_state) {
    return (
        <Alert>
        <AlertDescription>No game state available</AlertDescription>
        </Alert>
    );
    }

    if (gameData.session.game_type === 'guess_artist' && !gameData?.current_state?.revealed_info) {
      return (
        <Alert variant="destructive">
          <AlertDescription>Missing game data - try restarting</AlertDescription>
        </Alert>
      );
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
        <div className="max-w-4xl mx-auto">
            <Button
            variant="ghost"
            className="mb-6 text-white"
            onClick={() => navigate('/games')}
            >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Games
            </Button>

            <GameComponent
            sessionId={sessionId!}
            initialState={{
              ...gameData.current_state,
            revealedInfo: gameData.current_state.revealed_info
            }}
            onGameComplete={() => {
                setTimeout(() => navigate('/games/dashboard'), 30000);
            }}
            />
        </div>
        </div>
  );
};

export default GamePlay;
