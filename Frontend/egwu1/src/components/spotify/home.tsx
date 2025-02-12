import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Music,
  Mic,
  PenTool,
  Brain,
  Puzzle,
  Headphones,
  ChevronRight,
  Info,
  User,
  Bell,
} from 'lucide-react';
import Particles from '@tsparticles/react';
import { loadFull } from 'tsparticles';
import type { Engine } from '@tsparticles/engine';

interface GameMode {
  title: string;
  icon: React.ElementType; // Alternatively: React.ComponentType<React.SVGProps<SVGSVGElement>>
  description: string;
  bgColor: string;
  mockup: React.ReactNode;
}

// Sound effect for button interactions
const useSound = (url: string): (() => void) => {
  const [audio] = useState<HTMLAudioElement>(new Audio(url));
  return () => {
    audio.currentTime = 0;
    audio.play().catch(() => {});
  };
};

const HomePage: React.FC = () => {
  const [activeGameMode, setActiveGameMode] = useState<number>(0);
  const [isVisible, setIsVisible] = useState<boolean>(false);
  const playHover = useSound('/hover.mp3');
  const playClick = useSound('/click.mp3');

  const particlesInit = useCallback(async (engine: Engine) => {
    await loadFull(engine);
  }, []);

  const gameModes: GameMode[] = useMemo(
    () => [
      {
        title: 'Guess the Artist',
        icon: Headphones,
        description:
          'Listen to song snippets and guess the artist. Test your music recognition skills!',
        bgColor: 'from-purple-500/20 to-blue-500/20',
        mockup: (
          <div className="bg-zinc-800 rounded-lg p-4 transform transition-all duration-500 hover:scale-105">
            <div className="relative mb-4 h-32 bg-zinc-700 rounded-lg overflow-hidden">
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="w-16 h-16 bg-green-500 rounded-full animate-pulse flex items-center justify-center">
                  <Headphones className="w-8 h-8 text-white" />
                </div>
              </div>
              <div className="absolute bottom-0 left-0 right-0 h-1 bg-green-500 animate-[progress_3s_ease-in-out_infinite]" />
            </div>
            <div className="grid grid-cols-2 gap-2">
              {[...Array(4)].map((_, i) => (
                <button
                  key={i}
                  className="bg-zinc-700 hover:bg-zinc-600 p-2 rounded-lg text-sm transform transition-all hover:scale-105 hover:shadow-lg hover:shadow-purple-500/20"
                  onMouseEnter={playHover}
                  onClick={playClick}
                >
                  Artist {i + 1}
                </button>
              ))}
            </div>
          </div>
        ),
      },
      {
        title: 'Complete the Lyrics (Text)',
        icon: PenTool,
        description:
          'Fill in the missing words in your favorite song lyrics. How well do you know the words?',
        bgColor: 'from-green-500/20 to-emerald-500/20',
        mockup: (
          <div className="bg-zinc-800 rounded-lg p-4 transform transition-all hover:scale-105">
            <p className="mb-4 text-gray-300">
              "I've been running through the _____"
            </p>
            <input
              type="text"
              className="bg-zinc-700 p-2 rounded-lg w-full mb-2"
              placeholder="Type missing word..."
            />
            <button className="bg-green-500 hover:bg-green-600 p-2 rounded-lg w-full">
              Check Answer
            </button>
          </div>
        ),
      },
      {
        title: 'Complete the Lyrics (Speech)',
        icon: Mic,
        description:
          'Speak the missing lyrics into your microphone. Perfect your pronunciation!',
        bgColor: 'from-red-500/20 to-orange-500/20',
        mockup: (
          <div className="bg-zinc-800 rounded-lg p-4 transform transition-all hover:scale-105">
            <div className="flex justify-center mb-4">
              <div className="relative">
                <Mic className="w-16 h-16 text-red-500" />
                <div className="absolute inset-0 bg-red-500/20 rounded-full animate-ping" />
              </div>
            </div>
            <div className="text-center">
              <p className="text-gray-300 mb-2">Listening...</p>
              <div className="flex justify-center gap-2">
                {[...Array(5)].map((_, i) => (
                  <div
                    key={i}
                    className="w-1 h-8 bg-red-500 rounded-full animate-bounce"
                    style={{ animationDelay: `${i * 0.1}s` }}
                  />
                ))}
              </div>
            </div>
          </div>
        ),
      },
      {
        title: 'Crossword',
        icon: Puzzle,
        description:
          'Solve music-themed crossword puzzles based on your listening history.',
        bgColor: 'from-blue-500/20 to-cyan-500/20',
        mockup: (
          <div className="bg-zinc-800 rounded-lg p-4 transform transition-all hover:scale-105">
            <div className="grid grid-cols-5 gap-1 mb-4">
              {[...Array(25)].map((_, i) => (
                <div
                  key={i}
                  className={`aspect-square border border-zinc-600 rounded ${
                    Math.random() > 0.5 ? 'bg-zinc-700' : ''
                  }`}
                />
              ))}
            </div>
            <div className="text-sm text-gray-300">
              1. Across: Chart-topping hit by...
            </div>
          </div>
        ),
      },
      {
        title: 'Music Trivia',
        icon: Brain,
        description:
          'Challenge your music knowledge with personalized trivia questions.',
        bgColor: 'from-yellow-500/20 to-orange-500/20',
        mockup: (
          <div className="bg-zinc-800 rounded-lg p-4 transform transition-all hover:scale-105">
            <div className="mb-4">
              <h4 className="text-gray-300 mb-2">
                Which album won Album of the Year?
              </h4>
              <div className="space-y-2">
                {[...Array(4)].map((_, i) => (
                  <button
                    key={i}
                    className="w-full p-2 bg-zinc-700 hover:bg-zinc-600 rounded-lg text-left"
                  >
                    Option {i + 1}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ),
      },
    ],
    [playClick, playHover]
  );

  useEffect(() => {
    setIsVisible(true);
    const interval = setInterval(() => {
      setActiveGameMode((prev) => (prev + 1) % gameModes.length);
    }, 5000);
    return () => clearInterval(interval);
  }, [gameModes.length]);

  return (
    <div className="min-h-screen bg-black text-white overflow-hidden">
      {/* Particles Background */}
      <Particles
        id="tsparticles"
        init={particlesInit}
        options={{
          particles: {
            number: { value: 80, density: { enable: true, area: 800 } },
            color: { value: '#4ade80' },
            shape: { type: 'circle' },
            opacity: { value: 0.5,
                 random: {enable: true}},
            size: { value: 3, 
                random: {enable: true}},
            move: {
              enable: true,
              speed: 1,
              direction: 'none',
              random: {enable: true},
              straight: false,
              outModes: { default: 'bounce' },
            },
            links: {
              enable: true,
              distance: 150,
              color: '#4ade80',
              opacity: 0.2,
              width: 1,
            },
          },
        }}
        className="absolute inset-0"
      />

      {/* Navbar */}
      <nav className="relative flex items-center justify-between p-6 bg-black/50 backdrop-blur-sm">
        <div className="flex items-center gap-2">
          <Music className="w-8 h-8 text-green-500" />
          <span className="text-2xl font-bold">egwu</span>
        </div>
        <div className="flex items-center gap-4">
          <button className="p-2 hover:bg-zinc-800 rounded-full transition">
            <Info className="w-5 h-5" />
          </button>
          <button className="p-2 hover:bg-zinc-800 rounded-full transition">
            <Bell className="w-5 h-5" />
          </button>
          <a
            href="http://localhost:8000/login/"
            className="bg-green-500 hover:bg-green-600 transition px-6 py-3 rounded-full font-medium flex items-center gap-2 group transform hover:scale-105"
            onMouseEnter={playHover}
            onClick={playClick}
          >
            <User className="w-4 h-4" />
            Login with Spotify
            <ChevronRight className="w-4 h-4 group-hover:translate-x-1 transition" />
          </a>
        </div>
      </nav>

      {/* Hero Section */}
      <div className="relative max-w-6xl mx-auto px-6 pt-20 pb-32">
        <div
          className={`transition-all duration-1000 ${
            isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'
          }`}
        >
          <h1 className="text-5xl md:text-7xl font-bold mb-6 text-center">
            The Ultimate
            <span className="text-green-500"> Music Gaming </span>
            Experience
          </h1>
          <p className="text-xl text-gray-400 mb-12 max-w-2xl mx-auto text-center">
            Challenge yourself with five unique game modes, all personalized to
            your Spotify listening history.
          </p>
        </div>
      </div>

      {/* Game Modes Showcase */}
      <div className="relative">
        <div className="max-w-6xl mx-auto px-6 pb-20">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
            {/* Game Mode Info */}
            <div className="space-y-6">
              {gameModes.map((mode, index) => (
                <div
                  key={index}
                  className={`p-6 rounded-xl cursor-pointer transition-all duration-500 ${
                    activeGameMode === index
                      ? `bg-gradient-to-r ${mode.bgColor} scale-105`
                      : 'bg-zinc-900/50 hover:bg-zinc-800/50'
                  }`}
                  onClick={() => setActiveGameMode(index)}
                >
                  <div className="flex items-center gap-4">
                    <mode.icon
                      className={`w-6 h-6 ${
                        activeGameMode === index ? 'text-white' : 'text-gray-400'
                      }`}
                    />
                    <div>
                      <h3 className="text-lg font-bold">{mode.title}</h3>
                      <p className="text-gray-400 text-sm">{mode.description}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Game Mode Preview */}
            <div className="relative">
              {gameModes.map((mode, index) => (
                <div
                  key={index}
                  className={`transition-all duration-500 absolute inset-0 ${
                    activeGameMode === index
                      ? 'opacity-100 translate-y-0'
                      : 'opacity-0 translate-y-10 pointer-events-none'
                  }`}
                >
                  {mode.mockup}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HomePage;
