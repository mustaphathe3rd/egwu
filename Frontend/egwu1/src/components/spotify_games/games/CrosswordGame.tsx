import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Home, HelpCircle, Play, Pause, Loader2 } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import api from '@/services/api';
import { useNavigate } from 'react-router-dom';

// This is the new component for the game over screen
const GameOverComponent = ({ score, onRestart, onDashboard }) => {
    return (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
            <Card className="w-full max-w-md text-center p-6 bg-gray-900 text-white border-green-500 shadow-lg">
                <CardHeader>
                    <Trophy className="mx-auto h-16 w-16 text-yellow-400" />
                    <CardTitle className="text-3xl font-bold mt-4">Game Over!</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    <p className="text-lg text-gray-300">You've successfully completed the puzzle.</p>
                    <div className="bg-black/30 p-4 rounded-lg">
                        <p className="text-md text-gray-400">Final Score</p>
                        <p className="text-5xl font-bold text-green-400">{score}%</p>
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

const CrosswordGame = ({ sessionId, songData, puzzleData }) => {
    const [grid, setGrid] = useState([]);
    const [clues, setClues] = useState([]);
    const [currentClue, setCurrentClue] = useState(null);
    const [direction, setDirection] = useState('across');
    const [loading, setLoading] = useState(false);
    const [isGameOver, setIsGameOver] = useState(false); // State to control the Game Over screen
    const [finalScore, setFinalScore] = useState(0);
    const [error, setError] = useState(null);
    const inputRef = useRef(null);
    const navigate = useNavigate();

    useEffect(() => {
        if (puzzleData?.grid && puzzleData?.words) {
            const transformedGrid = puzzleData.grid.map((row, y) =>
                row.map((cell, x) => ({
                    ...cell,
                    userInput: '',
                    isSelected: false,
                    x,
                    y,
                }))
            );
            setGrid(transformedGrid);
            setClues(puzzleData.words);
        }
    }, [puzzleData]);

    const moveSelection = (currentX, currentY, dir) => {
        const step = dir === 'forward' ? 1 : -1;
        let nextX = direction === 'across' ? currentX + step : currentX;
        let nextY = direction === 'down' ? currentY + step : currentY;

        if (grid[nextY]?.[nextX] && !grid[nextY][nextX].isBlack) {
            handleCellClick(nextX, nextY);
        }
    };
    
    // =======================================================
    // THE FINAL FIX IS HERE: A smarter function to find clues
    // =======================================================
    const handleCellClick = (x, y) => {
        if (grid[y][x].isBlack) return;

        let currentDirection = direction;
        const isSameCell = grid.some(row => row.some(cell => cell.isSelected && cell.x === x && cell.y === y));

        if (isSameCell) {
            currentDirection = direction === 'across' ? 'down' : 'across';
        }

        const findWord = (dir) => clues.find((w) =>
            w.position.direction === dir &&
            (dir === 'across'
                ? w.position.y === y && x >= w.position.x && x < w.position.x + w.word.length
                : w.position.x === x && y >= w.position.y && y < w.position.y + w.word.length)
        );

        let wordInfo = findWord(currentDirection);

        if (!wordInfo) {
            const otherDirection = currentDirection === 'across' ? 'down' : 'across';
            wordInfo = findWord(otherDirection);
            if (wordInfo) {
                currentDirection = otherDirection;
            }
        }
        
        setDirection(currentDirection);
        setCurrentClue(wordInfo || null);

        setGrid(prevGrid =>
            prevGrid.map(row =>
                row.map(cell => ({ ...cell, isSelected: cell.x === x && cell.y === y }))
            )
        );
        inputRef.current?.focus();
    };

    const handleKeyPress = (e) => {
        e.preventDefault();
        const key = e.key;
        const selectedCell = grid.flat().find(c => c.isSelected);
        if (!selectedCell) return;

        const { x, y } = selectedCell;

        if (key === 'Backspace') {
            setGrid(prev => {
                const newGrid = prev.map(r => r.map(c => ({...c})));
                newGrid[y][x].userInput = '';
                return newGrid;
            });
            moveSelection(x, y, 'backward');
        } else if (key.match(/^[a-zA-Z]$/)) {
            const newLetter = key.toUpperCase();
            setGrid(prev => {
                const newGrid = prev.map(r => r.map(c => ({...c})));
                newGrid[y][x].userInput = newLetter;
                return newGrid;
            });
            moveSelection(x, y, 'forward');
        }
    };

    const handleSubmit = async () => {
        setLoading(true);
        setError(null);
        try {
            const answerPayload = grid.map(row => row.map(cell => cell.userInput || ' ').join('')).join('\n');
            const response = await api.post(`/games/api/sessions/${sessionId}/submit-answer/`, {
                answer: answerPayload,
            });

            const result = response.data;
            if (result.completed) {
                setIsGameOver(true);
            } else {
                setError(`You got ${result.score}% correct. Keep trying!`);
            }
        } catch (err) {
            setError(err.response?.data?.error || "Failed to submit answer");
        } finally {
            setLoading(false);
        }
    };
    
    if (!puzzleData || puzzleData.error) {
        return (
            <Alert variant="destructive">
                <AlertDescription>{puzzleData?.error || "Failed to load crossword puzzle."}</AlertDescription>
            </Alert>
        );
    }
    
    return (
         <div className="max-w-7xl mx-auto p-4 text-white">
            {/* Conditionally render the Game Over screen */}
            {isGameOver && (
                <GameOverComponent
                    score={finalScore}
                    onRestart={() => window.location.reload()} // Simple restart via refresh
                    onDashboard={() => navigate('/games/dashboard')}
                />
            )}
            <div className="flex justify-between items-center mb-6">
                <Button variant="ghost" onClick={() => navigate('/games/dashboard')}><Home className="w-5 h-5 mr-2" /> Home</Button>
            </div>
            <div className="grid md:grid-cols-2 gap-6 items-start">
                <div className="space-y-6">
                    <Card className="bg-black/20 border-white/10">
                        <CardContent className="p-4 flex items-center space-x-4">
                            <img src={songData?.album_image} alt="Album Cover" className="w-24 h-24 rounded-lg" />
                            <div>
                                <h3 className="text-lg font-semibold">{songData?.name}</h3>
                                <p className="text-sm text-gray-400">{songData?.artist}</p>
                                <Button variant="outline" size="sm" className="mt-2"><Play className="w-4 h-4 mr-2" /> Play Preview</Button>
                            </div>
                        </CardContent>
                    </Card>
                    <div className="bg-white p-2 rounded-lg shadow-md w-full">
                        <div className="grid gap-px" style={{ gridTemplateColumns: `repeat(${puzzleData?.dimensions?.width || 15}, 1fr)` }}>
                            {grid.map((row, y) =>
                                row.map((cell, x) => (
                                    <div
                                        key={`${x}-${y}`}
                                        className={`aspect-square flex items-center justify-center text-black font-bold uppercase text-lg relative cursor-pointer transition-colors ${
                                            cell.isBlack ? 'bg-black' : 'bg-white'
                                        } ${cell.isSelected ? 'ring-2 ring-blue-500' : ''}`}
                                        onClick={() => handleCellClick(x, y)}
                                    >
                                        {cell.number && <span className="absolute top-0 left-0.5 text-xs font-normal">{cell.number}</span>}
                                        {cell.userInput}
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                </div>
                <div className="space-y-6">
                    <Card className="bg-black/20 border-white/10 min-h-[100px]">
                        <CardHeader><CardTitle>Current Clue</CardTitle></CardHeader>
                        <CardContent><p className="text-lg">{currentClue?.clue || 'Select a cell to see the clue.'}</p></CardContent>
                    </Card>
                    <div className="flex gap-2">
                        <Button variant={direction === 'across' ? 'secondary' : 'outline'} onClick={() => setDirection('across')}>Across</Button>
                        <Button variant={direction === 'down' ? 'secondary' : 'outline'} onClick={() => setDirection('down')}>Down</Button>
                    </div>
                    <Input ref={inputRef} onKeyDown={handleKeyPress} className="absolute -top-96" />
                    <Button onClick={handleSubmit} disabled={loading} className="w-full bg-green-600 hover:bg-green-700">
                        {loading && <Loader2 className="h-4 w-4 animate-spin mr-2" />} Submit Crossword
                    </Button>
                    {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
                </div>
            </div>
        </div>
    );
};

export default CrosswordGame;