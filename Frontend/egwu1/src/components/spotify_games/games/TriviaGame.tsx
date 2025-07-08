import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Loader2, Home } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Progress } from '@/components/ui/progress';
import api from '@/services/api';
import { useNavigate } from 'react-router-dom'; 

const TriviaGame = ({ sessionId, initialState, onGameComplete }) => {
  const [gameState, setGameState] = useState(initialState);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedAnswer, setSelectedAnswer] = useState<string | null>(null);
  const [isAnswered, setIsAnswered] = useState(false); // Tracks if the current question has been answered
  const[isGameOver, setIsGameOver] = useState(false); // New state for the game over screen
  const navigate = useNavigate();

  const progress = ((gameState.current_question) / gameState.total_questions) * 100;

  
  const handleAnswer = async (answer: string) => {
    if (loading || isAnswered) return;

    setLoading(true);
    setError(null);
    setSelectedAnswer(answer);

    try {
        const response = await api.post(`/games/api/sessions/${sessionId}/submit-answer/`, {
            answer
        });
        
        const result = response.data;

        // Phase 1: Show feedback for the current answer
        setIsAnswered(true);
        setGameState(prevState => ({
            ...prevState,
            score: result.score,
            is_correct: result.is_correct,
            feedback: result.feedback,
            explanation: result.explanation,
        }));
        
        // Phase 2: After a delay, check for game completion or move to next question
        setTimeout(() => {
            if (result.completed) {
                // =======================================================
                // THE FIX IS HERE: Immediately show the game over screen
                // =======================================================
                setIsGameOver(true);
            } else {
                setGameState({ ...result }); // Load next question
                setSelectedAnswer(null);
                setIsAnswered(false);
            }
        }, 2500); // 2.5-second delay
        
    } catch (err: any) {
        setError(err.response?.data?.error || "Failed to submit answer");
        setIsAnswered(false); // Allow user to try again on error
        setSelectedAnswer(null);
    } finally {
        setLoading(false);
    }
};
  const renderOptions = () => {
    if (!gameState?.options) return null;

    return gameState.options.map((option: string, index: number) => {
      let buttonClass = "";

      if (isAnswered) {
        if (option === gameState.correct_answer) {
          buttonClass = "bg-green-500/30 border-green-500 hover:bg-green-500/40 text-white";
        } else if (selectedAnswer === option) {
          buttonClass = "bg-red-500/30 border-red-500 hover:bg-red-500/40 text-white";
        }
      }

      return (
        <Button
          key={index}
          variant="outline"
          className={`w-full p-6 text-left justify-start text-lg h-auto transition-all duration-300 ${buttonClass}`}
          onClick={() => handleAnswer(option)}
          disabled={loading || isAnswered}
        >
          <span className="font-semibold mr-4 text-gray-400">
            {String.fromCharCode(65 + index)}
          </span>
          {option}
        </Button>
      );
    });
  };

  if (!gameState) return <div className="text-white">Loading game...</div>;

  if (isGameOver) {
    return (
        <Card className="w-full max-w-2xl mx-auto bg-white/10 border-0 text-white text-center shadow-2xl p-8">
            <CardTitle className="text-3xl font-bold mb-4">Game Over!</CardTitle>
            <CardContent className="space-y-6">
                <p className="text-xl text-gray-300">You completed the trivia challenge.</p>
                <div className="bg-black/20 p-6 rounded-lg">
                    <p className="text-lg text-gray-400 mb-2">Final Score</p>
                    <p className="text-5xl font-bold text-green-400">{gameState.score}</p>
                </div>
                <Button onClick={() => navigate('/games/dashboard')} size="lg">
                    <Home className="mr-2 h-5 w-5" />
                    Back to Dashboard
                </Button>
            </CardContent>
        </Card>
    );
  }

  return (
    <Card className="w-full max-w-3xl mx-auto bg-white/5 border-0 text-white shadow-2xl">
      <CardHeader>
        <div className="flex justify-between items-center mb-2">
          <CardTitle className="text-2xl font-bold text-green-400">Spotify Music Trivia</CardTitle>
          <span className="text-sm font-medium text-gray-400">
            Question {gameState.current_question + 1} of {gameState.total_questions}
          </span>
        </div>
        <Progress value={progress} className="h-2 bg-black/20" />
      </CardHeader>
      <CardContent className="space-y-6 px-6 pb-6">
        {error && (
          <Alert variant="destructive">
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="bg-black/20 p-6 rounded-lg min-h-[100px] flex items-center justify-center">
          <p className="text-xl text-center">{gameState.question}</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {renderOptions()}
        </div>

        {isAnswered && gameState.feedback && (
          <div className={`p-4 rounded-lg text-center ${
            gameState.is_correct ? 'bg-green-500/20' : 'bg-red-500/20'
          }`}>
            <p className="font-bold text-xl">{gameState.feedback}</p>
            {gameState.explanation && (
              <p className="mt-2 text-sm opacity-80">{gameState.explanation}</p>
            )}
          </div>
        )}

        {loading && !isAnswered && (
          <div className="flex justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-green-400" />
          </div>
        )}

        <div className="text-center pt-4 border-t border-white/10">
          <p className="text-2xl font-bold">Score: {gameState.score}</p>
        </div>
      </CardContent>
    </Card>
  );
};

export default TriviaGame;