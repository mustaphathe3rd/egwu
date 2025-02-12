
import { createBrowserRouter } from 'react-router-dom';
import HomePage from '@/components/spotify/Homepage';
import LoadingScreen from '@/components/spotify/LoadingScreen';
import GameDashboard from '../components/spotify_games/GameDashboard';
import GamePlay from '../components/spotify_games/GamePlay';

export const router = createBrowserRouter([
    {
        path: '/',
        element: <HomePage />,
    },
    {
        path: '/loading',
        element: <LoadingScreen />,
    },
     {
         path: '/games/dashboard',
         element: <GameDashboard />
     },
     {
        path: "/games/play/:sessionId",
        element: <GamePlay />
     }
]);
