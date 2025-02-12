import { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { 
  Home,
  HelpCircle, 
  Play, 
  Pause,
  Loader2,
  ArrowLeft,
  RefreshCw
} from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { motion } from 'framer-motion';
import api from '@/services/api';
import { generateSpotifyWebPlaybackToken } from '@/utils/spotifyToken'
import { useNavigate } from 'react-router-dom';

interface CrosswordCell {
  letter: string;
  solution: string;
  number?: number;
  isActive: boolean;
  isSelected: boolean;
  isCorrect?: boolean;
  x: number;
  y: number;
}

interface CrosswordGameProps {
  sessionId: string;
  initialState: any;
  onGameComplete: () => void;
  onHomeClick: () => void;
}

const CrosswordGame = ({ sessionId, initialState, onGameComplete}: CrosswordGameProps) => {
  const [gameState, setGameState] = useState(initialState);
  const [grid, setGrid] = useState<CrosswordCell[][]>([]);
  const [currentClue, setCurrentClue] = useState<string>('');
  const [selectedCell, setSelectedCell] = useState<{ x: number; y: number } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [direction, setDirection] = useState<'across' | 'down'>('across');
  const [isPlaying, setIsPlaying] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);
  const playerRef = useRef<Spotify.Player |null>(null);
  const playbackTimerRef = useRef<NodeJS.Timeout | null>(null);
  const navigate = useNavigate();
  const handleHomeClick = () => {
    navigate('/games/dashboard');
  };

  // Initialize Spotify Web Playback SDK
  useEffect(() => {
    const script = document.createElement("script");
    script.src = "https://sdk.scdn.co/spotify-player.js";
    script.async = true;
    document.body.appendChild(script);

    window.onSpotifyWebPlaybackSDKReady = async () => {
      try {
        const token = await generateSpotifyWebPlaybackToken();

        const player = new Spotify.Player({
          name: 'Crossword Game Player',
          getOAuthToken: cb => cb(token)
        });

        const success = await player.connect();
        if (success) {
          playerRef.current = player;
        }
        player.addListener('playback_error',({ message }) => {
            setError(`Playback error: ${message}`);
        });
      } catch (err) {
        setError('Failed to initialize Spotify Player');
      }
      };
    return () => {
      // Cleanup
      if (playbackTimerRef.current) {
        clearTimeout(playbackTimerRef.current);
      }
      if (playerRef.current) {
        playerRef.current.disconnect();
      }
      document.body.removeChild(script);
    };
  }, []);

  useEffect(() => {
    if (initialState.puzzle_data?.grid) {
      const transformedGrid = initialState.puzzle_data.grid.map( row =>
        row.map(cell => ({
          letter: '',
          solution: cell.letter || '',
          number: cell.number || undefined,
          isActive: cell.isActive,
          isSelected: false,
          isCorrect: false,
          x: cell.x,
          y: cell.y
        }))
      );
      setGrid(transformedGrid);
    }
  }, [initialState]);

  const handlePlayback = async () => {
    if (!playerRef.current) return;

    if (isPlaying) {
      // Stop playback
      await playerRef.current.pause();
      if (playbackTimerRef.current) {
        clearTimeout(playbackTimerRef.current);
      }
      setIsPlaying(false);
    } else {
      // Start 30-second preview
      try {
        // Use the preview_url from gameState
        const previewUrl = gameState.song_data.preview_url;
        await playerRef.current.resume(); // Resume if paused
        await playerRef.current.seek(30000); // Start at 30 seconds in
        
        setIsPlaying(true);

        // Stop after 30 seconds
        playbackTimerRef.current = setTimeout(() => {
          playerRef.current?.pause();
          setIsPlaying(false);
        }, 30000);
      } catch (err) {
        setError('Failed to play preview');
      }
    }
  };

  const updateCurrentClue = (x: number, y: number) => {
    const number = grid[y][x].number;
    if (!number) return;

    const clue = gameState.puzzle_data.words.find((word: any) => 
      word.position.x === x && 
      word.position.y === y && 
      word.position.direction === direction
    );

    setCurrentClue(clue?.clue || '');
  };

  const moveSelection = (moveDir: 'forward' | 'backward') => {
    if (!selectedCell) return;

    const { x, y } = selectedCell;
    const step = moveDir === 'forward' ? 1 : -1;
    const newGrid = [...grid];

    // Clear previous selection
    newGrid[y][x].isSelected = false;

    if (direction === 'across') {
      const newX = x + step;
      if (newX >= 0 && newX < grid[0].length && grid[y][newX].isActive) {
        newGrid[y][newX].isSelected = true;
        setSelectedCell({ x: newX, y });
      }
    } else {
      const newY = y + step;
      if (newY >= 0 && newY < grid.length && grid[newY][x].isActive) {
        newGrid[newY][x].isSelected = true;
        setSelectedCell({ x, y: newY });
      }
    }

    setGrid(newGrid);
  };

  const handleCellClick = (x: number, y: number) => {
    if (!grid[y][x].isActive) return;

    const newGrid = grid.map(row => 
      row.map(cell => ({
        ...cell,
        isSelected: cell.x === x && cell.y === y
      }))
    );

    if (selectedCell?.x === x && selectedCell?.y === y) {
      setDirection(prev => prev === 'across' ? 'down' : 'across');
    }

    setGrid(newGrid);
    setSelectedCell({ x, y });


    if (gameState.puzzle_data?.words) {
      const word = gameState.puzzle_data.words.find(w =>
        w.position.x === x &&
        w.position.y === y &&
        w.position.direction === direction
      );
      setCurrentClue(word?.clue || '');
    }

  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!selectedCell) return;

    if (e.key === 'Enter') {
      handleSubmit();
      return;
    }

    const { x, y } = selectedCell;
    const newGrid = [...grid];
    
    if (e.key === 'Backspace') {
      newGrid[y][x].letter = '';
      newGrid[y][x].isCorrect = false;
      setGrid(newGrid);
      moveSelection('backward');
    } else if (e.key.match(/^[a-zA-Z]$/)) {
      const inputLetter = e.key.toUpperCase();
      newGrid[y][x].letter = inputLetter;
      newGrid[y][x].isCorrect = inputLetter === newGrid[y][x].solution;
      setGrid(newGrid);
      moveSelection('forward');
    }
  };
 
  const handleSubmit = async () => {
    setLoading(true);
    setError(null);

    try {
      // Build answer string from grid
      const answer = gameState.puzzle_data.words.map((word: any) => {
        let wordStr = '';
        const { x, y, direction } = word.position;
        
        if (direction === 'across') {
          for (let i = 0; i < word.word.length; i++) {
            wordStr += grid[y][x + i].letter || ' ';
          }
        } else {
          for (let i = 0; i < word.word.length; i++) {
            wordStr += grid[y + i][x].letter || ' ';
          }
        }
        return wordStr.trim();
      }).join(',');

      const response = await api.post(`/games/api/sessions/${sessionId}/submitanswer/`, {
        answer
      });

      if (response.data.current_state.completed) {
        setShowSuccess(true);
        // Stop playback if it's playing
        if (isPlaying) {
          handlePlayback();
        }
        setTimeout(() => {
          onGameComplete();
        }, 3000);
      }

      setGameState(response.data.current_state);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to submit answer');
    } finally {
      setLoading(false);
    }
  };

  const HowToPlayContent = () => (
    <div className="space-y-4">
      <p>1. Listen to the song snippet for clues</p>
      <p>2. Click on a cell to select it</p>
      <p>3. Type letters to fill in the crossword</p>
      <p>4. Use arrow keys or click cells to navigate</p>
      <p>5. Toggle between across/down with space or by clicking the direction buttons</p>
      <p>6. Submit when you're ready!</p>
    </div>
  );

  return (
    <div className="max-w-7xl mx-auto p-4">
      <div className="flex justify-between items-center mb-6">
        <Button variant="ghost" onClick={handleHomeClick}>
          <Home className="w-5 h-5 mr-2" />
          Home
        </Button>
        
        <Dialog>
          <DialogTrigger asChild>
            <Button variant="ghost">
              <HelpCircle className="w-5 h-5 mr-2" />
              How to Play
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>How to Play Crossword</DialogTitle>
            </DialogHeader>
            <HowToPlayContent />
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="space-y-6">
          {/* Song Info and Playback */}
          <Card className="bg-black/5">
            <CardContent className="p-6">
              <div className="flex items-center space-x-4">
                <img 
                  src={gameState.song_data?.album_image} 
                  alt="Album Cover"
                  className="w-24 h-24 rounded-lg"
                />
                <div>
                  <h3 className="text-lg font-semibold">{gameState.song_data?.name}</h3>
                  <p className="text-sm text-gray-500">{gameState.song_data?.artist}</p>
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={handlePlayback}
                    className="mt-2"
                  >
                    {isPlaying ? (
                      <Pause className="w-4 h-4 mr-2" />
                    ) : (
                      <Play className="w-4 h-4 mr-2" />
                    )}
                    {isPlaying ? 'Pause' : 'Play Preview'}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Crossword Grid */}
          <div className="bg-white rounded-lg p-4 shadow-md">
            <div 
              className="grid gap-1" 
              style={{ 
                gridTemplateColumns: `repeat(${grid[0]?.length || 0}, 1fr)`
              }}
            >
              {grid.map((row, y) =>
                row.map((cell, x) => (
                  <div
                    key={`${x}-${y}`}
                    className={`
                      aspect-square border
                      ${cell.isActive ? 'bg-white' : 'bg-black'}
                      ${cell.isSelected ? 'ring-2 ring-blue-500' : ''}
                      ${cell.isCorrect ? 'bg-green-100' : ''}
                      relative cursor-pointer
                      transition-all duration-150
                    `}
                    onClick={() => handleCellClick(x, y)}
                  >
                    {cell.number && (
                      <span className="absolute top-0 left-0 text-xs text-black p-0.5">
                        {cell.number}
                      </span>
                    )}
                    {cell.isActive && (
                      <span className="absolute inset-0 flex items-center justify-center text-lg font-bold text-black">
                        {cell.letter}
                      </span>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right Side Controls */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Current Clue</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-lg">{currentClue || 'Select a cell to see the clue'}</p>
            </CardContent>
          </Card>

          <div className="flex gap-2">
            <Button
              variant="secondary"
              onClick={() => setDirection('across')}
              className={direction === 'across' ? 'bg-blue-500 text-white' : ''}
            >
              Across
            </Button>
            <Button
              variant="secondary"
              onClick={() => setDirection('down')}
              className={direction === 'down' ? 'bg-blue-500 text-white' : ''}
            >
              Down
            </Button>
          </div>

          <Input
            className="text-lg text-center"
            onKeyDown={handleKeyPress}
            maxLength={1}
            autoFocus
            disabled={!selectedCell}
            placeholder="Type to fill in selected cell"
          />

          <Button
            className="w-full"
            onClick={handleSubmit}
            disabled={loading}
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
            ) : null}
            Submit Crossword
          </Button>
        </div>
      </div>

      {/* Success Animation */}
      {showSuccess && (
        <motion.div
          initial={{ scale: 0, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0, opacity: 0 }}
          className="fixed inset-0 flex items-center justify-center bg-black/50"
        >
          <div className="bg-white p-8 rounded-lg text-center">
            <h2 className="text-3xl font-bold mb-4">Well Done! 🎉</h2>
            <p className="mb-4">You've completed the crossword!</p>
            <Button onClick={() => window.location.reload()}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Play Again
            </Button>
          </div>
        </motion.div>
      )}

      {error && (
        <Alert variant="destructive" className="mt-4">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
    </div>
  );
};

export default CrosswordGame;