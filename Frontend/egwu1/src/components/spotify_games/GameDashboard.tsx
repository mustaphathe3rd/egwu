import React, { useState, useEffect } from 'react';
import { Trophy, Users, LineChart, Play, Loader2, AlertCircle, Wrench, HardHat } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarImage, AvatarFallback } from 
'@/components/ui/avatar';
import api from '@/services/api';
import { useNavigate } from 'react-router-dom';

const GameDashboard = () => {
  const [loading, setLoading] = useState<{ [key: string]: boolean }>({});
  const [error, setError] = useState<string | null>(null);
  const [userProfile, setUserProfile] = useState<{ displayName: string; imageUrl: string | null}>({
    displayName: '',
    imageUrl: null
  });
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
      description: 'Test your knowledge of song lyrics with personalized challenges',
      icon: <span className="text-4xl">🎵</span>,
      players: '1.2k',
      rating: '4.8',
      gradient: 'from-green-400 to-emerald-500'
    },
    {
      name: 'Artist Guess',
      type: 'guess_artist',
      description: 'Identify artists from hints and clues based on your music taste',
      icon: <span className="text-4xl">🎤</span>,
      players: '1.5k',
      rating: '4.9',
      gradient: 'from-emerald-500 to-green-600'
    },
    {
      name: 'Music Trivia',
      type: 'trivia',
      description: 'Challenge yourself with questions about your favorite genres',
      icon: <span className="text-4xl">❓</span>,
      players: '1.1k',
      rating: '4.7',
      gradient: 'from-green-600 to-emerald-700'
    },
    {
      name: 'Lyrics Voice Game',
      type: 'lyrics_voice',
      description: 'Test your knowledge of song lyrics with voice interactions',
      icon: <span className="text-4xl">🎙️</span>,
      players: '800',
      rating: '4.6',
      gradient: 'from-emerald-500 to-green-500',
      underConstruction: true
    },
    {
      name: 'Music Crossword',
      type: 'crossword',
      description: 'Solve crossword puzzles featuring your favorite songs and artists',
      icon: <span className="text-4xl">📝</span>,
      players: '950',
      rating: '4.5',
      gradient: 'from-green-500 to-emerald-600'
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

  const UnderConstructionOverlay = () => (
    <div className="absolute inset-0 bg-black/80 backdrop-blur-sm z-10 flex items-center justify-center rounded-2xl">
      <div className="text-center">
        <div className="relative mb-4">
          <div className="w-24 h-24 bg-gradient-to-br from-yellow-400 to-orange-500 rounded-full flex items-center justify-center mx-auto transform rotate-12 shadow-2xl">
            <div className="w-20 h-20 bg-yellow-300 rounded-full flex items-center justify-center transform -rotate-12">
              <HardHat className="w-10 h-10 text-yellow-800" />
            </div>
          </div>
          <div className="absolute -top-2 -right-2 w-8 h-8 bg-orange-500 rounded-full flex items-center justify-center">
            <Wrench className="w-4 h-4 text-white transform rotate-45" />
          </div>
        </div>
        <div className="bg-gradient-to-r from-yellow-400 to-orange-500 text-black px-4 py-2 rounded-lg font-bold text-sm mb-2 transform -rotate-2 shadow-lg">
          UNDER CONSTRUCTION
        </div>
        <p className="text-white text-sm opacity-90">Coming Soon!</p>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-900 via-emerald-900 to-black relative overflow-hidden">
      {/* Animated background elements */}
      <div className="absolute inset-0">
        <div className="absolute top-20 left-20 w-32 h-32 bg-green-500/10 rounded-full blur-xl animate-pulse"></div>
        <div className="absolute top-40 right-40 w-48 h-48 bg-emerald-500/10 rounded-full blur-xl animate-pulse delay-1000"></div>
        <div className="absolute bottom-20 left-40 w-40 h-40 bg-green-600/10 rounded-full blur-xl animate-pulse delay-500"></div>
      </div>

      <div className="relative z-10 p-6">
        <div className="max-w-7xl mx-auto">
          {/* User Profile Section */}
          <div className="absolute top-6 right-6 flex items-center space-x-3 bg-white/10 backdrop-blur-md p-3 rounded-2xl border border-white/20 shadow-xl">
            <div className="text-right">
              <p className="text-xs text-gray-300">Welcome back,</p>
              <p className="text-white font-semibold">{userProfile.displayName}</p>
            </div>
            <Avatar className="h-12 w-12 border-2 border-white/30">
              <AvatarImage src={userProfile.imageUrl || ''} alt={userProfile.displayName} />
              <AvatarFallback className="bg-gradient-to-br from-green-500 to-emerald-600 text-white font-bold">
                {userProfile.displayName.charAt(0)}
              </AvatarFallback>
            </Avatar>
          </div>

          {/* Header Section */}
          <div className="text-center mb-16 pt-20">
            <div className="relative">
              <h1 className="text-6xl font-bold bg-gradient-to-r from-white via-green-200 to-green-400 bg-clip-text text-transparent mb-6 leading-tight">
                Spotify Music Games
              </h1>
              <div className="absolute -top-4 left-1/2 transform -translate-x-1/2 w-32 h-2 bg-gradient-to-r from-green-400 to-emerald-500 rounded-full blur-sm"></div>
            </div>
            <p className="text-xl text-gray-300 max-w-3xl mx-auto leading-relaxed">
              Challenge yourself with personalized music games crafted from your unique Spotify listening history
            </p>
          </div>

          {/* Stats Section */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-16">
            {[
              { icon: Trophy, title: 'Your Library', desc: 'Games tailored to your music taste', color: 'from-green-400 to-emerald-500' },
              { icon: Users, title: 'Leaderboards', desc: 'Compete with music enthusiasts worldwide', color: 'from-green-500 to-emerald-600' },
              { icon: LineChart, title: 'Track Progress', desc: 'Monitor achievements and improvements', color: 'from-emerald-400 to-green-500' }
            ].map((stat, index) => (
              <Card key={index} className="bg-white/5 backdrop-blur-md border-white/10 hover:bg-white/10 transition-all duration-300 hover:scale-105 shadow-2xl">
                <CardContent className="p-8 text-center">
                  <div className={`w-16 h-16 bg-gradient-to-br ${stat.color} rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg`}>
                    <stat.icon className="w-8 h-8 text-white" />
                  </div>
                  <h3 className="text-2xl font-bold text-white mb-2">{stat.title}</h3>
                  <p className="text-gray-300 leading-relaxed">{stat.desc}</p>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Error Alert */}
          {error && (
            <Alert variant="destructive" className="mb-8 bg-red-500/20 border-red-500/50 backdrop-blur-md">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription className="text-red-100">{error}</AlertDescription>
            </Alert>
          )}

          {/* Games Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {games.map((game) => (
              <Card key={game.type} className="bg-white/5 backdrop-blur-md border-white/10 overflow-hidden transition-all duration-500 hover:scale-105 hover:bg-white/10 shadow-2xl hover:shadow-3xl relative group">
                {game.underConstruction && <UnderConstructionOverlay />}
                
                <CardContent className="p-8">
                  <div className="flex items-center justify-between mb-6">
                    <div className={`w-16 h-16 bg-gradient-to-br ${game.gradient} rounded-2xl flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform duration-300`}>
                      {game.icon}
                    </div>
                    <Badge variant="secondary" className="bg-green-500/20 text-green-300 border-green-500/30 hover:bg-green-500/30 transition-colors">
                      New
                    </Badge>
                  </div>
                  
                  <CardTitle className="text-2xl font-bold text-white mb-3 group-hover:text-green-300 transition-colors">
                    {game.name}
                  </CardTitle>
                  
                  <p className="text-gray-300 mb-8 leading-relaxed">{game.description}</p>
                  
                  <Button
                    className={`w-full bg-gradient-to-r ${game.gradient} hover:shadow-lg text-white font-semibold py-3 rounded-xl transition-all duration-300 hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed`}
                    onClick={() => handleGameStart(game.type)}
                    disabled={loading[game.type] || game.underConstruction}
                  >
                    {loading[game.type] ? (
                      <>
                        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                        Loading...
                      </>
                    ) : game.underConstruction ? (
                      <>
                        <HardHat className="mr-2 h-5 w-5" />
                        Coming Soon
                      </>
                    ) : (
                      <>
                        <Play className="mr-2 h-5 w-5" />
                        Play Now
                      </>
                    )}
                  </Button>
                </CardContent>
                
                <div className="px-8 py-4 bg-white/5 border-t border-white/10 backdrop-blur-sm">
                  <div className="flex items-center justify-between text-sm text-gray-300">
                    <span className="flex items-center">
                      <Users className="mr-2 h-4 w-4" />
                      {game.players} players
                    </span>
                    <span className="flex items-center">
                      <Trophy className="mr-2 h-4 w-4" />
                      {game.rating}/5
                    </span>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default GameDashboard;