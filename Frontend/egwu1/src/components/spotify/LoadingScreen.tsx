import React, { useState, useEffect, FC } from 'react';
import { useNavigate } from 'react-router-dom';
import { Music2, Loader2, Volume2, AlertCircle } from 'lucide-react';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { checkAuth, checkProcessingStatus } from '@/services/api';


const LoadingScreen: FC = () => {
  const [progress, setProgress] = useState<number>(0);
  const [messageIndex, setMessageIndex] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);
  const [isRedirecting, setIsRedirecting] = useState<boolean>(false);
  const navigate = useNavigate();

  const loadingMessages: string[] = [
    "Analyzing your musical taste...",
    "Finding your favorite artists...",
    "Discovering your most-played tracks...",
    "Creating your personalized game experience...",
    "Almost there! Preparing your music challenges...",
    "Tuning the perfect gameplay for you...",
    "Getting everything rhythm-ready...",
    "Loading your musical memories...",
  ];

  useEffect(() => { // Extract and store tokens from URL parameters
    const params = new URLSearchParams(window.location.search);
    const accessToken = params.get('access_token');
    const refreshToken = params.get('refresh_token');

    if (accessToken && refreshToken) {
      localStorage.setItem('access_token', accessToken);
      localStorage.setItem('refresh_token', refreshToken);
      
      // Clean up URL parameters
      navigate('/loading', { replace: true });
    }
  }, [navigate]);

  useEffect(() => {
    let isMounted = true;
    let pollInterval: NodeJS.Timeout;

    const checkAuthentication = async () => {
      try {
        const accessToken = localStorage.getItem('access_token');
        if (!accessToken) {
          throw new Error('No access token found');
        }

        const isAuthenticated = await checkAuth();
        console.debug('Authentication check result:', isAuthenticated);

        if (!isAuthenticated) {
          console.debug('Current tokens:', {
            access: localStorage.getItem('access_token')?.substring(0, 10) + '...',
            refresh: localStorage.getItem('refresh_token')?.substring(0, 10) + '...',
          });
          throw new Error('Authentication failed - invalid tokens');
        }
        return true;
      } catch (err) {
        console.error('Authentication check error:', err);
        setError('Authentication failed. Please try logging in again.');
        // Clear tokens on authentication failure
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        return false;
      }
    };

    const pollProcessingStatus = async () => {
      if (!isMounted) return;

      try {
        const isAuthed = await checkAuthentication();
        if (!isAuthed) return;

        const response = await checkProcessingStatus();
        
        if (!isMounted) return;

        if (response.status === 'complete' && response.redirect_url) {
          setProgress(100);
          if (!isRedirecting) {
            setIsRedirecting(true);
            // Small delay to show completion state
            setTimeout(() => {
              if (response.redirect_url?.startsWith('http')) {
                window.location.href = response.redirect_url;
              } else {
                navigate(response.redirect_url);
              }
            }, 1500);
          }
        } else if (response.status === 'error') {
          setError(response.error || 'An error occurred while processing your data');
        }
      } catch (err:any) {
        if (!isMounted) return;
        console.error('Processing status error:', err);
        setError('Unable to check processing status. Please refresh the page.');
      }
    };

    // Initial check
    pollProcessingStatus();

    // Poll every 5 seconds instead of 10 for better responsiveness
    pollInterval = setInterval(pollProcessingStatus, 5000);

    // Simulate progress for user feedback
    const progressInterval = setInterval(() => {
      if (isMounted && !isRedirecting) {
        setProgress((prev) => {
          if (prev >= 95) return 95; // Cap at 95% until actually complete
          return prev + 0.5;
        });
      }
    }, 1000);

    // Rotate messages
    const messageInterval = setInterval(() => {
      if (isMounted && !isRedirecting) {
        setMessageIndex((prev) => (prev + 1) % loadingMessages.length);
      }
    }, 5000);

    // Cleanup
    return () => {
      isMounted = false;
      clearInterval(pollInterval);
      clearInterval(progressInterval);
      clearInterval(messageInterval);
    };
  }, [navigate, isRedirecting]);

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-green-900 to-black flex items-center justify-center p-4">
        <div className="w-full max-w-md">
          <Alert variant="destructive" className="mb-4">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
          <button
            onClick={() => window.location.reload()}
            className="w-full bg-green-500 hover:bg-green-600 text-white font-medium py-2 px-4 rounded-full transition-colors"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-green-900 to-black flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Animated Record Player */}
        <div className="flex justify-center mb-8">
          <div className="relative">
            <div className="w-32 h-32 rounded-full bg-black border-4 border-gray-800 flex items-center justify-center">
              <div
                className={`w-4 h-4 rounded-full bg-green-500 absolute top-4 left-1/2 transform -translate-x-1/2 ${
                  progress < 100 ? 'animate-pulse' : ''
                }`}
              />
              <div className="w-8 h-8 rounded-full bg-gray-800" />
            </div>
            <Music2
              className={`absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 text-green-500 w-16 h-16 ${
                progress < 100 ? 'animate-spin' : ''
              }`}
              style={{ animationDuration: '3s' }}
            />
          </div>
        </div>

        {/* Loading Message */}
        <div className="text-center mb-8">
          <h2 className="text-white text-xl font-bold mb-2">
            {progress >= 100 ? 'All Set!' : 'Getting Your Music Ready'}
          </h2>
          <p className="text-gray-300 min-h-[24px] transition-all duration-500">
            {loadingMessages[messageIndex]}
          </p>
        </div>

        {/* Progress Bar */}
        <div className="space-y-2">
          <Progress value={progress} className="h-2" />
          <div className="flex justify-between text-sm text-gray-400">
            <span>{Math.round(progress)}% complete</span>
            <span>
              {progress < 100 ? (
                <span className="flex items-center gap-1">
                  <Loader2 className="animate-spin w-4 h-4" />
                  Processing
                </span>
              ) : (
                <span className="flex items-center gap-1 text-green-500">
                  <Volume2 className="w-4 h-4" />
                  Complete
                </span>
              )}
            </span>
          </div>
        </div>

        {/* Fun Facts */}
        <div className="mt-8 bg-white/5 rounded-lg p-4">
          <h3 className="text-green-500 font-medium mb-2">Did you know?</h3>
          <div className="text-gray-300 text-sm">
            The average Spotify user listens to around 2.5 hours of music daily, discovering 41 new artists
            yearly! We're using your unique listening patterns to create the perfect game experience.
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoadingScreen;
