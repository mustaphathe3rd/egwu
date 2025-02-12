import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Loader2, Home, RefreshCw, Info, Play, Pause } from 'lucide-react';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import api from '@/services/api';
import { generateSpotifyWebPlaybackToken } from '@/utils/spotifyToken';
import { useNavigate } from 'react-router-dom';

// Define Spotify Player type
declare global {
  interface Window {
    Spotify: {
      Player: any;
    };
    onSpotifyWebPlaybackSDKReady: () => void;
  }
}

interface ArtistGuessProps {
  sessionId: string;
  initialState: {
    revealed_info: any;
    session_state: {
      tries_left: number;
      is_complete: boolean;
      score: number;
    };
  };
  onGameComplete: () => void;
  onHomeClick: () => void;
}

interface TargetArtist {
  name: string;
  image_url: string;
  favorite_song: {
    name: string;
    preview_url: string;
  };
}

interface GuessFeedback {
  attributes: {
    [key: string]: {
      status: 'exact' | 'close' | 'wrong';
      guessed_value: any;
    };
  };
  artist_info: {
    name: string;
    image_url: string;
  };
  is_correct: boolean;
  target_artist?: TargetArtist;
}

const ArtistGuessGame: React.FC<ArtistGuessProps> = ({ sessionId, initialState, onGameComplete}) => {
  const [gameState, setGameState] = useState({
    revealed_info: initialState.revealed_info || {},
    session_state: initialState.session_state || {
      tries_left: 10,
      is_complete: false,
      score: 0
    },
    guesses: []
  });
  const [guesses, setGuesses] = useState<GuessFeedback[]>([]);
  const [guess, setGuess] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [targetArtist, setTargetArtist] = useState<TargetArtist | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [showRules, setShowRules] = useState(false);
  const [player, setPlayer] = useState<any>(null);
  const navigate = useNavigate();
  const handleHomeClick = () => {
    navigate('/games/dashboard');
  }

  useEffect(() => {
    const script = document.createElement("script");
    script.src = "https://sdk.scdn.co/spotify-player.js";
    script.async = true;
    document.body.appendChild(script);

    window.onSpotifyWebPlaybackSDKReady = () => {
      const spotifyPlayer = new window.Spotify.Player({
        name: 'Artist Guess Game Player',
        getOAuthToken: async (cb: (token: string) => void) => {
          try {
            const token = await generateSpotifyWebPlaybackToken();
            cb(token);
          } catch (error) {
            console.error('Failed to get Spotify token:', error);
          }
        }
      });

      spotifyPlayer.connect().then((success: boolean) => {
        if (success) {
          setPlayer(spotifyPlayer);
        }
      });
    };

    return () => {
      script.remove();
      if (player) {
        player.disconnect();
      }
    };
  }, []);

  useEffect(() => {
    if (gameState.session_state?.is_complete) {
      onGameComplete();
    }
  }, [gameState.session_state?.is_complete, onGameComplete]);

  const searchArtists = async (query: string) => {
    if (query.length < 2) {
      setSuggestions([]);
      return;
    }

    try {
      const response = await api.get(`/games/api/sessions/${sessionId}/search_artists/`, {
        params: { q: query }
      });
      setSuggestions(response.data.map((a: any) => a.name));
    } catch (err) {
      console.error('Failed to fetch artist suggestions');
      setSuggestions([]);
    }
  };

  const handleGuess = async () => {
    if (!guess) return;

    setLoading(true);
    setError(null);

    try {
      const response = await api.post(`/games/api/sessions/${sessionId}/submit_guess/`, {
        artist_name: guess
      });

      setGameState(prevState => ({
        ...prevState,
        session_state: response.data.session_state,
        revealed_info: response.data.revealed_info || prevState.revealed_info
      }));

      if (response.data.feedback) {
        setGuesses(prev => [...prev, response.data.feedback]);

        if (response.data.feedback.target_artist) {
          setTargetArtist(response.data.feedback.target_artist);
          if (response.data.feedback.target_artist.favorite_song?.preview_url && player) {
            player.resume();
            setIsPlaying(true);
          }
        }
      }
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to submit guess');
    } finally {
      setLoading(false);
      setGuess('');
      setSuggestions([]);
    }
  };

  const togglePlayback = () => {
    if (!player) return;

    if (isPlaying) {
      player.pause();
    } else {
      player.resume();
    }
    setIsPlaying(!isPlaying);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'exact': return 'bg-green-500/50';
      case 'close': return 'bg-yellow-500/50';
      default: return 'bg-red-500/50';
    }
  };

  const handleRestart = async () => {
    try {
      const response = await api.post(`/games/api/sessions/${sessionId}/restart/`);
      setGameState({
        revealed_info: response.data.revealed_info,
        session_state: response.data.session_state,
        guesses: []
      });
      setGuesses([]);
      setTargetArtist(null);
      setError(null);
    } catch (err) {
      console.error('Failed to restart game');
    }
  };

  return (
    <div className="space-y-6">
      <Card className="bg-white/10 border-0">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-2xl font-bold text-white">Guess the Artist</CardTitle>
          <div className="flex gap-2">
            <Button 
              variant="outline" 
              size="icon"
              onClick={() => setShowRules(true)}
            >
              <Info className="h-4 w-4" />
            </Button>
            <Button 
              variant="outline" 
              size="icon"
              onClick={handleHomeClick}
            >
              <Home className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-6">
            {/* Initial Hints */}
            <div className="bg-black/30 p-4 rounded-lg">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-white/70 mb-1">Genre</p>
                  <p className="text-white">{gameState.revealed_info?.genres}</p>
                </div>
                <div>
                  <p className="text-white/70 mb-1">Country</p>
                  <p className="text-white">{gameState.revealed_info?.country}</p>
                </div>
              </div>
            </div>

            {/* Previous Guesses */}
            {guesses.map((guess, index) => (
              <div key={index} className="bg-black/30 p-4 rounded-lg">
                <div className="flex items-center gap-3 mb-4">
                  <img 
                    src={guess.artist_info.image_url} 
                    className="w-10 h-10 rounded-full"
                    alt={guess.artist_info.name}
                  />
                  <h3 className="text-white font-semibold">{guess.artist_info.name}</h3>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  {/* Attributes Tables */}
                  <table className="w-full">
                    <tbody>
                      <tr>
                        {['debut_year', 'members', 'popularity', 'birth_year'].map((attr) => (
                          <td
                            key={attr}
                            className={`p-2 text-center ${getStatusColor(guess.attributes[attr]?.status)}`}
                          >
                            {attr === 'popularity' ? '#' : ''}{guess.attributes[attr]?.guessed_value}
                            {guess.attributes[attr]?.status === 'exact' && ' ✓'}
                          </td>
                        ))}
                      </tr>
                      <tr>
                        <th className="text-white/70 p-2 text-center text-sm">Debut Year</th>
                        <th className="text-white/70 p-2 text-center text-sm">Members</th>
                        <th className="text-white/70 p-2 text-center text-sm">Popularity</th>
                        <th className="text-white/70 p-2 text-center text-sm">Birth Year</th>
                      </tr>
                    </tbody>
                  </table>

                  <table className="w-full">
                    <tbody>
                      <tr>
                        {['gender', 'genres', 'country', 'num_albums'].map((attr) => (
                          <td
                            key={attr}
                            className={`p-2 text-center ${getStatusColor(guess.attributes[attr]?.status)}`}
                          >
                            {guess.attributes[attr]?.guessed_value}
                            {guess.attributes[attr]?.status === 'exact' && ' ✓'}
                          </td>
                        ))}
                      </tr>
                      <tr>
                        <th className="text-white/70 p-2 text-center text-sm">Gender</th>
                        <th className="text-white/70 p-2 text-center text-sm">Genre</th>
                        <th className="text-white/70 p-2 text-center text-sm">Country</th>
                        <th className="text-white/70 p-2 text-center text-sm">Albums</th>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            ))}

            {/* Game Completion Display */}
            {targetArtist && (
              <div className="bg-green-500/20 p-6 rounded-lg">
                <div className="flex items-center gap-6">
                  <img
                    src={targetArtist.image_url}
                    className="w-24 h-24 rounded-full"
                    alt={targetArtist.name}
                  />
                  <div className="flex-1">
                    <h3 className="text-white font-bold text-2xl mb-2">
                      {targetArtist.name}
                    </h3>
                    <div className="flex items-center gap-4">
                      <p className="text-white/80">
                        Most Popular Song: {targetArtist.favorite_song.name}
                      </p>
                    </div>
                  </div>

                  <div className="flex gap-4 justify-center">
                    <Button 
                      onClick={handleRestart}
                      className="bg-blue-600 hover:bg-blue-700"
                    >
                      <RefreshCw className="h-4 w-4 mr-2" />
                      Play Again
                    </Button>
                    {targetArtist.favorite_song.preview_url && (
                      <Button
                        onClick={togglePlayback}
                        variant="ghost"
                        size="sm"
                        className="hover:bg-white/10"
                      >
                        {isPlaying ? (
                          <Pause className="h-6 w-6 text-white" />
                        ) : (
                          <Play className="h-6 w-6 text-white" />
                        )}
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Input Section */}
            {!gameState.session_state?.is_complete && (
              <div className="relative">
                <div className="flex gap-4">
                  <Input
                    value={guess}
                    onChange={(e) => {
                      setGuess(e.target.value);
                      searchArtists(e.target.value);
                    }}
                    placeholder="Search artist..."
                    className="flex-1 bg-white/5 border-none text-white"
                  />
                  <Button 
                    onClick={handleGuess} 
                    disabled={loading || !guess}
                    className="bg-green-600 hover:bg-green-700"
                  >
                    {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Submit Guess'}
                  </Button>
                </div>

                {suggestions.length > 0 && (
                  <div className="absolute z-10 w-full mt-2 bg-gray-800 rounded-lg overflow-hidden">
                    {suggestions.map((artist, index) => (
                      <button
                        key={index}
                        className="w-full px-4 py-2 text-left text-white hover:bg-gray-700"
                        onClick={() => {
                          setGuess(artist);
                          setSuggestions([]);
                        }}
                      >
                        {artist}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Tries Counter */}
            {!gameState.session_state?.is_complete && (
              <div className="text-center text-white/80">
                Tries remaining: {gameState.session_state?.tries_left ?? 10}
              </div>
            )}

            {error && (
              <div className="text-red-400 text-center">
                {error}
              </div>
            )}
          </div>

          {/* Rules Dialog */}
          <AlertDialog open={showRules} onOpenChange={setShowRules}>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>How to Play</AlertDialogTitle>
                <AlertDialogDescription className="space-y-2">
                
                   <p>Welcome to the Artist Guess Game! Here's how to play:</p>
                   <ul className="list-disc pl-4">
                     <li>You start with initial hints about the artist's genre and country</li>
                     <li>Each guess reveals more information about the target artist</li>
                     <li>Green boxes indicate exact matches</li>
                    <li>Yellow boxes indicate close matches</li>
                    <li>Red boxes indicate incorrect values</li>
                   <li>You have 10 tries to guess the correct artist</li>
                 </ul>
               </AlertDialogDescription>
             </AlertDialogHeader>
            </AlertDialogContent>
          </AlertDialog>
        </CardContent>
      </Card>
    </div>
  );
};
 
export default ArtistGuessGame;
