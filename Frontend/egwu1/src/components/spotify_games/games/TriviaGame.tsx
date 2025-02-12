import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Loader2 } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Progress } from '@/components/ui/progress';
import api from '@/services/api';

const TriviaGame = ({ sessionId, initialState, onGameComplete }) => {
  const [gameState, setGameState] = useState(initialState);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedAnswer, setSelectedAnswer] = useState(null);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (gameState?.current_question !== undefined && gameState?.total_questions) {
      setProgress((gameState.current_question / gameState.total_questions) * 100);
    }
  }, [gameState]);

  const handleAnswer = async (answer) => {
    if (loading || gameState.answered) return;
    
    setLoading(true);
    setError(null);
    setSelectedAnswer(answer);

    try {
      const response = await api.post(`/games/api/sessions/${sessionId}/submitanswer/`, {
        answer
      });

      if (!response.ok) {
        throw new Error('Failed to submit answer');
      }

      const data = await response.json();
      setGameState(prevState => ({
        ...prevState,
        ...data.current_state,
        answered: true,
        is_correct: data.current_state.is_correct,
        feedback: data.current_state.feedback,
        explanation: data.current_state.explanation
      }));

      if (data.current_state.completed) {
        onGameComplete();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const renderOptions = () => {
    if (!gameState?.options) return null;

    return gameState.options.map((option, index) => {
      let buttonVariant = "outline";
      let statusClass = "";

      if (gameState.answered) {
        if (option === gameState.correct_answer) {
          statusClass = "bg-[#1DB954]/20 hover:bg-[#1DB954]/30 text-[#1DB954]";
        } else if (selectedAnswer === option) {
          statusClass = "bg-red-500/20 hover:bg-red-500/30";
        }
      } else if (selectedAnswer === option) {
        buttonVariant = "secondary";
      }

      return (
        <Button
          key={index}
          variant={buttonVariant}
          className={`w-full p-6 text-left justify-start ${statusClass}`}
          onClick={() => handleAnswer(option)}
          disabled={loading || gameState.answered}
        >
          <span className="font-semibold mr-3">
            {String.fromCharCode(65 + index)}.
          </span>
          {option}
        </Button>
      );
    });
  };

  const renderArtistInfo = () => {
    if (!gameState?.currentArtist) return null;
    
    return (
      <div className="flex items-center space-x-4 mb-6 bg-black/5 p-4 rounded-lg">
        <img 
          src={gameState.currentArtist.image_url} 
          alt={gameState.currentArtist.name}
          className="w-16 h-16 rounded-full object-cover"
        />
        <div>
          <p className="text-sm text-gray-500">Current Artist</p>
          <h3 className="font-semibold text-lg">{gameState.currentArtist.name}</h3>
        </div>
      </div>
    );
  };

  if (!gameState) return null;

  return (
    <Card className="w-full max-w-2xl mx-auto bg-gradient-to-b from-black/5 to-transparent">
      <CardHeader>
        <CardTitle className="flex justify-between items-center">
          <span className="text-[#1DB954]">Spotify Music Trivia</span>
          <span className="text-sm font-normal">
            Question {gameState.current_question + 1} of {gameState.total_questions}
          </span>
        </CardTitle>
        <Progress 
          value={progress} 
          className="w-full bg-gray-200" 
          indicatorClassName="bg-[#1DB954]"
        />
      </CardHeader>
      <CardContent className="space-y-6">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {renderArtistInfo()}

        {gameState.question && (
          <div className="bg-black/5 p-6 rounded-lg">
            <p className="text-xl mb-2">{gameState.question}</p>
          </div>
        )}

        <div className="grid grid-cols-1 gap-3">
          {renderOptions()}
        </div>

        {gameState.answered && gameState.feedback && (
          <div className={`p-4 rounded-lg ${
            gameState.is_correct ? 'bg-[#1DB954]/20' : 'bg-red-500/20'
          }`}>
            <p className="font-semibold">{gameState.feedback}</p>
            {gameState.explanation && (
              <p className="mt-2 text-sm opacity-90">{gameState.explanation}</p>
            )}
          </div>
        )}

        {loading && (
          <div className="flex justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-[#1DB954]" />
          </div>
        )}

        {gameState.score !== undefined && (
          <div className="text-center">
            <p className="text-lg font-semibold">Score: {gameState.score}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default TriviaGame;