import React, { useState, useEffect } from 'react';
import { Trophy, Users, LineChart, Play, Loader2, AlertCircle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useNavigate } from 'react-router-dom';
import { Avatar, AvatarImage, AvatarFallback } from '@/components/ui/avatar';
import api from '@/services/api';

const GameDashboard = () => {
  const [loading, setLoading] = useState<{ [key: string]: boolean }>({});
  const [error, setError] = useState<string | null>(null);
  const[userProfile, setUserProfile] = useState<{ displayName: string; imageUrl: string | null}>({
    displayName: '',
    imageUrl: null
  })
  const navigate = useNavigate();

  useEffect(() => {
    const fetchUserProfile = async () => {
      try {
        const response = await api.get('/user-profile/');
        setUserProfile({
          displayName: response.data.display_name || 'User',
          imageUrl: response.data.display_image
        });
      } catch (err) {
        console.error('Failed to fetch user profile:', err);
      }
    };

    fetchUserProfile();
  }, []);

  const games = [
    {
      name: 'Lyrics Game',
      type: 'lyrics_text',
      description: 'Test your knowledge of song lyrics',
      icon: <span className="text-4xl">🎵</span>,
      players: '1.2k',
      rating: '4.8'
    },
    {
      name: 'Artist Guess',
      type: 'guess_artist',
      description: 'Guess the artist based on hints',
      icon: <span className="text-4xl">🎤</span>,
      players: '1.5k',
      rating: '4.9'
    },
    {
      name: 'Music Trivia',
      type: 'trivia',
      description: 'Test your music knowledge',
      icon: <span className="text-4xl">❓</span>,
      players: '1.1k',
      rating: '4.7'
    },
    {
      name: 'Lyrics Voice Game',
      type: 'lyrics_voice',
      description: 'Test your knowledge of song lyrics with an extra touch',
      icon: <span className="text-4xl">🎙️</span>,
      players: '800',
      rating: '4.6'
    },
    {
      name: 'Music Crossword',
      type: 'crossword',
      description: 'Test your knowledge of your favorite songs on a board',
      icon: <span className="text-4xl">📝</span>,
      players: '950',
      rating: '4.5'
    }
  ];

  const handleGameStart = async (gameType: string) => {
    setLoading(prev => ({ ...prev, [gameType]: true }));
    setError(null);

    try {
      const response = await api.post('/games/api/sessions/start_game/', {
        game_type: gameType
      });

      if (response.data.session?.id) {
        navigate(`/games/play/${response.data.session.id}`, {
          state: { gameData: response.data }
        });
      }
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to start game. Please try again.');
    } finally {
      setLoading(prev => ({ ...prev, [gameType]: false }));
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-green-900 to-black p-6">
      <div className="max-w-7xl mx-auto relative">
        {/* User Profile Section */}
        <div className="absolute top-0 right-0 flex items-center space-x-3 bg-white/10 p-2 rounded-lg">
          <div className="text-right">
            <p className="text-sm text-gray-300">Welcome,</p>
            <p className="text-white font-semibold">{userProfile.displayName}</p>
          </div>
          <Avatar className="h-10 w-10">
            <AvatarImage src={userProfile.imageUrl || ''} alt={userProfile.displayName} />
            <AvatarFallback className="bg-green-500">
              {userProfile.displayName.charAt(0)}
            </AvatarFallback>
          </Avatar>
        </div>

        {/* Header Section */}
        <div className="text-center mb-12 pt-16">
          <h1 className="text-4xl font-bold text-white mb-4">
            Welcome to Spotify Music Games
          </h1>
          <p className="text-xl text-gray-300 max-w-3xl mx-auto">
            Challenge yourself with personalized music games based on your Spotify listening history
          </p>
        </div>

        {/* Stats Section */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
          <Card className="bg-white/10 border-0">
            <CardContent className="p-6 text-center">
              <Trophy className="w-8 h-8 text-green-500 mx-auto mb-2" />
              <h3 className="text-xl font-bold text-white">Your Library</h3>
              <p className="text-gray-300 mt-2">Games tailored to your music taste</p>
            </CardContent>
          </Card>
          <Card className="bg-white/10 border-0">
            <CardContent className="p-6 text-center">
              <Users className="w-8 h-8 text-green-500 mx-auto mb-2" />
              <h3 className="text-xl font-bold text-white">Leaderboards</h3>
              <p className="text-gray-300 mt-2">Compete with other music lovers</p>
            </CardContent>
          </Card>
          <Card className="bg-white/10 border-0">
            <CardContent className="p-6 text-center">
              <LineChart className="w-8 h-8 text-green-500 mx-auto mb-2" />
              <h3 className="text-xl font-bold text-white">Track Progress</h3>
              <p className="text-gray-300 mt-2">Monitor your gaming achievements</p>
            </CardContent>
          </Card>
        </div>

        {/* Error Alert */}
        {error && (
          <Alert variant="destructive" className="mb-6">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Games Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {games.map((game) => (
            <Card key={game.type} className="bg-white/10 border-0 overflow-hidden transition-transform duration-300 hover:scale-105">
              <CardContent className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="game-icon text-green-500">
                    {game.icon}
                  </div>
                  <Badge variant="secondary">New</Badge>
                </div>
                <CardTitle className="text-xl font-bold text-white mb-2">
                  {game.name}
                </CardTitle>
                <p className="text-gray-300 mb-6">{game.description}</p>
                <Button
                  className="w-full bg-green-500 hover:bg-green-600 text-white"
                  onClick={() => handleGameStart(game.type)}
                  disabled={loading[game.type]}
                >
                  {loading[game.type] ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Loading...
                    </>
                  ) : (
                    <>
                      <Play className="mr-2 h-4 w-4" />
                      Play Now
                    </>
                  )}
                </Button>
              </CardContent>
              <div className="px-6 py-4 bg-white/5 border-t border-white/10">
                <div className="flex items-center justify-between text-sm text-gray-300">
                  <span className="flex items-center">
                    <Users className="mr-1 h-4 w-4" />
                    {game.players} players
                  </span>
                  <span className="flex items-center">
                    <Trophy className="mr-1 h-4 w-4" />
                    {game.rating}/5
                  </span>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
};

export default GameDashboard;