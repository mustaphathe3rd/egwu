
import React, { useState, useCallback, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, Mic, Volume2, Play, Pause } from 'lucide-react';
import api from '@/services/api';

interface SongData {
  name: string;
  artist: string;
  album_image: string;
  spotify_id: string;
  track_uri: string;
}

interface Challenge {
  song_data: SongData;
  complete_lyrics: string;
  challenge_lyrics: string;
  missing_portion: string;
}

interface GameState {
  challenge: Challenge[];
  currentChallengeIndex: number;
  inputType: 'text' | 'voice';
  attempts: number
  maxAttempts: number;
  songPreview: string | null;
  lyricsContext: string;
  lyricsPrompt: string;
  feedback: string | null;
  isCorrect: boolean | null;
  completed: boolean;
}

interface LyricsGameProps {
  sessionId: string;
  initialState: GameState;
  onGameComplete: () => void;
  inputType?: 'text' | 'voice';
}

const LyricsGame = ({ 
  sessionId, 
  initialState, 
  onGameComplete, 
  inputType = 'text' 
}: LyricsGameProps) => {
  const [gameState, setGameState] = useState<GameState>(initialState);
  const [answer, setAnswer] = useState('');
  const [loading, setLoading] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [player, setPlayer] = useState<Spotify.Player | null>(null);
  const currentChallenge = gameState.challenge[gameState.currentChallengeIndex] || {
    song_data: {
      name: 'Unknown Song',
      artist: 'Unknown Artist',
      album_image: '',
      spotify_id: '',
      track_uri: ''
    },
    complete_lyrics: '',
    challenge_lyrics: '',
    missing_portion: ''
  };

  useEffect(() => {
    console.log('Initial State:', initialState);
  }, [initialState]);
  // Initialize Spotify Web Playback SDK
  React.useEffect(() => {
    if (!window.Spotify) {
      const script = document.createElement('script');
      script.src = 'https://sdk.scdn.co/spotify-player.js';
      script.async = true;
      document.body.appendChild(script);

      window.onSpotifyWebPlaybackSDKReady = () => {
        const spotifyPlayer = new window.Spotify.Player({
          name: 'Lyrics Game Player',
          getOAuthToken: cb => {
            // Get token from your backend
            api.get('/auth/spotify/token/').then(response => {
              cb(response.data.token);
            });
          }
        });

        spotifyPlayer.connect();
        setPlayer(spotifyPlayer);
      };
    }
  }, []);

  const togglePlayback = useCallback(async () => {
    if (!player) return;

    const currentSong = gameState.challenge[gameState.currentChallengeIndex].song_data;

    if (!isPlaying) {
      await player.resume();
      // Start playing from current song's URI
      await player.play({
        uris: [currentSong.track_uri],
        position_ms: 0
      });
      // Stop after 30 seconds (preview length)
      setTimeout(() => {
        player.pause();
        setIsPlaying(false);
      }, 30000);
    } else {
      await player.pause();
    }
    setIsPlaying(!isPlaying);
  }, [player, isPlaying,gameState.challenge, gameState.currentChallengeIndex]);

  const handleSubmit = useCallback(async () => {
    if (!answer.trim()) return;
    
    setLoading(true);
    setError(null);

    try {
      const response = await api.post(`/games/api/sessions/${sessionId}/submitanswer/`, {
       answer
      });

      if (!response.ok) {
        throw new Error('Failed to submit answer');
      }

      const data = await response.json();
      setGameState(data.current_state);
      
      if (data.current_state.completed) {
        onGameComplete();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
      setAnswer('');
    }
  }, [answer, sessionId, onGameComplete]);

  const handleVoiceRecord = useCallback(async () => {
    try {
      setIsRecording(true);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      const audioChunks: BlobPart[] = [];

      mediaRecorder.ondataavailable = (event) => {
        audioChunks.push(event.data);
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
        const formData = new FormData();
        formData.append('audio', audioBlob);

        try {
          const response = await api.post(`/games/api/sessions/${sessionId}/submit_voice_answer/`, {
            body: formData
          });

          if (!response.ok) {
            throw new Error('Failed to process voice input');
          }

          const data = await response.json();
          setGameState(data.current_state);
        } catch (err) {
          setError(err instanceof Error ? err.message : 'Failed to process voice input');
        }
      };

      mediaRecorder.start();
      setTimeout(() => {
        mediaRecorder.stop();
        stream.getTracks().forEach(track => track.stop());
        setIsRecording(false);
      }, 5000);
    } catch (err) {
      setError('Failed to access microphone');
      setIsRecording(false);
    }
  }, [sessionId]);

  

  return (
    <Card className="w-full max-w-2xl mx-auto bg-white/10 border-0">
      <CardHeader className="flex flex-row justify-between items-start">
        <CardTitle className="text-2xl font-bold text-white flex items-center gap-2">
          <Volume2 className="h-6 w-6" />
          Lyrics Challenge
        </CardTitle>
        <div className="flex flex-col items-end">
          <div className="flex items-center gap-4">
            <div className="text-right">
              <h3 className="font-semibold text-white">{currentChallenge?.song_data?.name || 'Unknown Song'}</h3>
              <p className="text-sm text-gray-300">{currentChallenge?.song_data?.artist || 'Unknown Artist'}</p>
            </div>
            <img 
              src={currentChallenge?.song_data?.album_image} 
              alt="Album Cover"
              className="w-16 h-16 rounded-lg shadow-lg"
            />
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={togglePlayback}
            className="mt-2"
          >
            {isPlaying ? (
              <Pause className="h-4 w-4 mr-2" />
            ) : (
              <Play className="h-4 w-4 mr-2" />
            )}
            {isPlaying ? 'Pause Preview' : 'Play Preview'}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="text-lg text-white space-y-4">
          <p>{gameState.lyricsContext}</p>
          <p className="font-bold">Complete the lyrics:</p>
          <p>{gameState.lyricsPrompt}</p>
        </div>

        <div className="flex gap-4">
          <Input
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            placeholder="Type the next line..."
            className="flex-1"
            disabled={loading || isRecording}
          />
          
          {inputType === 'voice' && (
            <Button
              variant="outline"
              onClick={handleVoiceRecord}
              disabled={loading || isRecording}
              className={isRecording ? 'bg-red-500/20' : ''}
            >
              <Mic className={`h-4 w-4 ${isRecording ? 'text-red-500' : ''}`} />
            </Button>
          )}
          
          <Button 
            onClick={handleSubmit}
            disabled={loading || isRecording || !answer.trim()}
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Submit'}
          </Button>
        </div>

        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {gameState.feedback && (
          <Alert variant={gameState.isCorrect ? 'success' : 'error'}>
            <AlertDescription>{gameState.feedback}</AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
};


export default LyricsGame;