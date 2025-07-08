import React, { useState, useCallback, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Loader2, Home, RefreshCw, Trophy } from 'lucide-react';
import api from '@/services/api';
import { useNavigate } from 'react-router-dom';

// New, dedicated component for the Game Over screen
const LyricsGameOver = ({ score, onRestart, onDashboard }) => {
    return (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
            <Card className="w-full max-w-md text-center p-6 bg-gray-900 text-white border-green-500 shadow-lg">
                <CardHeader>
                    <Trophy className="mx-auto h-16 w-16 text-yellow-400" />
                    <CardTitle className="text-3xl font-bold mt-4">Challenge Complete!</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="bg-black/30 p-4 rounded-lg">
                        <p className="text-md text-gray-400">Final Score</p>
                        <p className="text-5xl font-bold text-green-400">{score}</p>
                    </div>
                    <div className="flex justify-center gap-4 pt-4">
                        <Button onClick={onRestart} variant="outline" size="lg">
                            <RefreshCw className="mr-2 h-5 w-5" />
                            Play Again
                        </Button>
                        <Button onClick={onDashboard} size="lg" className="bg-green-600 hover:bg-green-700">
                            <Home className="mr-2 h-5 w-5" />
                            Dashboard
                        </Button>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
};


const LyricsGame = ({ sessionId, initialState }) => {
    const [gameState, setGameState] = useState(initialState);
    const [answer, setAnswer] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [feedback, setFeedback] = useState<{ message: string; isCorrect: boolean } | null>(null);
    const [isGameOver, setIsGameOver] = useState(false); // State to control the Game Over screen
    const navigate = useNavigate();

    const currentChallenge = useMemo(() => {
        if (!gameState || !gameState.challenge) return null;
        return gameState.challenge[gameState.current_challenge_index];
    }, [gameState]);

    const handleSubmit = useCallback(async () => {
        if (!answer.trim()) return;
        setLoading(true);
        setError(null);
        setFeedback(null);

        try {
            const response = await api.post(`/games/api/sessions/${sessionId}/submit-answer/`, {
                answer
            });
            const result = response.data;
            setFeedback({ message: result.feedback, isCorrect: result.is_correct });

            setTimeout(() => {
                if (result.completed) {
                    // =======================================================
                    // THE FIX IS HERE: Show the Game Over component
                    // =======================================================
                    setGameState(prev => ({...prev, score: result.score})); // Set final score
                    setIsGameOver(true);
                } else {
                    setGameState(result.new_state);
                    setAnswer('');
                    setFeedback(null);
                }
            }, 2500); // 2.5 second delay

        } catch (err: any) {
            setError(err.response?.data?.error || 'Failed to submit answer.');
        } finally {
            setLoading(false);
        }
    }, [answer, sessionId, navigate]);

    if (!currentChallenge) {
        return <div className="text-white p-8">Loading Lyrics Challenge...</div>;
    }

    if (isGameOver) {
        return (
            <LyricsGameOver
                score={gameState.score}
                onRestart={() => window.location.reload()} // Simple refresh to start a new game
                onDashboard={() => navigate('/games/dashboard')}
            />
        );
    }

    return (
        <Card className="w-full max-w-3xl mx-auto bg-black/20 border-white/10 text-white shadow-xl">
            <CardHeader className="flex flex-row justify-between items-start p-6">
                <CardTitle className="text-2xl font-bold flex items-center gap-3">
                    <span className="text-green-400 text-3xl">🎤</span> Lyrics Challenge
                </CardTitle>
                <div className="flex items-center gap-4 text-right">
                    <div>
                        <h3 className="font-semibold">{currentChallenge.song_data.name}</h3>
                        <p className="text-sm text-gray-400">{currentChallenge.song_data.artist}</p>
                    </div>
                    <img
                        src={currentChallenge.song_data.album_image}
                        alt="Album Cover"
                        className="w-16 h-16 rounded-lg"
                    />
                </div>
            </CardHeader>
            <CardContent className="space-y-6 p-6">
                <div className="bg-black/30 p-6 rounded-lg text-center space-y-3">
                    <p className="text-lg text-gray-400 italic">"{currentChallenge.context_before}"</p>
                    
                    <div className="py-4">
                        <Input
                            value={answer}
                            onChange={(e) => setAnswer(e.target.value)}
                            placeholder="Type the missing line..."
                            className="flex-1 bg-gray-800 border-gray-700 text-white text-center text-xl h-14"
                            disabled={loading || !!feedback}
                            onKeyPress={(e) => e.key === 'Enter' && handleSubmit()}
                        />
                    </div>

                    <p className="text-lg text-gray-400 italic">"{currentChallenge.context_after || '...'}"</p>
                </div>

                <Button onClick={handleSubmit} disabled={loading || !answer.trim() || !!feedback} className="w-full h-12 text-lg bg-green-600 hover:bg-green-700">
                    {loading ? <Loader2 className="h-6 w-6 animate-spin" /> : 'Submit'}
                </Button>

                {error && (
                    <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>
                )}

                {feedback && (
                    <Alert variant={feedback.isCorrect ? "default" : "destructive"} className={feedback.isCorrect ? "bg-green-500/20 border-green-500" : ""}>
                         <AlertTitle className="font-bold">{feedback.isCorrect ? "Correct!" : "Not Quite!"}</AlertTitle>
                        <AlertDescription>{feedback.message}</AlertDescription>
                    </Alert>
                )}
            </CardContent>
        </Card>
    );
};

export default LyricsGame;