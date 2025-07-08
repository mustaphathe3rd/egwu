# In Backend/silleyBEnd/spotify_games/game_modes/base.py

from abc import ABC, abstractmethod
from ..models import GameSession, GamePlayback, GameState, GameStatistics, GameLeaderboard
from spotify.models import MostListenedSongs, MostListenedArtist
import random   
from ..exceptions import *
import logging
from ..services.cache_service import GameCacheService
from django.utils import timezone
from ..monitoring import *

logger = logging.getLogger('spotify_games')

class BaseGame(ABC):
    def __init__(self, session: GameSession):
        self.session = session
        self.state, created = GameState.objects.get_or_create(
            session=session,
            defaults={
                'current_state': {},
                'metadata': {}
            }                                         
        )
        self.cache_service = GameCacheService()
        self.monitoring = GameAnalytics()
        
    def track_game_event(self, event_type: str, metadata: dict = None):
        """Track game events"""
        event = GameEvent(
            event_type=event_type,
            user_id=self.session.user.id,
            game_type=self.session.game_type,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )
        self.monitoring.track_event(event)
        
    def initialize_game(self, input_type=None):
        try:
            game_state = self._initialize_game_impl()
            self.state.update_state(game_state, 'initialized')
            
            self.track_game_event('initialization',{
                'status': 'success',
                'game_type': self.session.game_type
            })
            return game_state
        except Exception as e:
            logger.error(f"Game initialization failed: {str(e)}", exc_info=True)
            raise GameInitializationError(f"Failed to initialize game: {str(e)}")
    
    @abstractmethod
    def _initialize_game_impl(self):
        pass
    
    def get_cached_game(self, game_type: str) -> dict:
        """Centralized cache checking for all game modes"""
        return self.cache_service.get_game_session(
            self.session.id,game_type)
        
    def cache_game(self, game_type: str, state:dict) -> None:
        """Centralized cache settings for all game modes"""
        self.cache_service.cache_game_session(
            self.session.id,
            game_type,
            state
        )
        
    def update_game_state(self, state:dict, status: str = None) -> None:
        """Centralized state update method"""
        self.state.update_state(state, status)
        
    def validate_answer(self, answer):
        try:
            result = self._validate_answer_impl(answer)
            return result
        except Exception as e:
            logger.error(f"Answer validation failed: {str(e)}", exc_info=True)
            raise GameError(f"Failed to validate answer: {str(e)}")                    
            
    def setup_playback(self, track_id: str, track_name: str,
                       artist_name: str, album_image: str, spotify_uri:str):
        return GamePlayback.objects.create(
            session=self.session,
            spotify_track_id=track_id,
            track_name=track_name,
            artist_name=artist_name,
            album_image_url = album_image,
            spotify_uri = spotify_uri 
        )
        
    def get_random_songs(self, count=1):
        songs = MostListenedSongs.objects.filter(
            user = self.session.user
        ).order_by('?')[:count]
        return list(songs)
    
    def get_random_artists(self, count=1):
        artists = MostListenedArtist.objects.filter(
            user=self.session.user
        ).order_by('?')[:count]
        return list(artists)
    
    def restart_game(self):
        """
        Properly restart the game by clearing caches and creating a new game state
        """
        logger.debug(f"Restarting game for user {self.session.id}")
        
        self.cache_service.clear_game_session(self.session.id,self.session.game_type,)
        
        self.session.current_tries = 0
        self.session.completed = False
        self.session.score = 0
        self.session.save()
        
        new_game_state = self._initialize_game_impl()
        
        self.state.current_state = new_game_state
        self.state.save()
        
        return new_game_state
    
    def end_game(self, score=0):
        """
        End the game and update all relevant state
        """
        logger.debug(f"Ending game for session {self.session.id} with score {score}")
        
        self.session.completed = True
        self.session.score = score
        self.session.end_time = timezone.now() # Make sure end_time is set
        self.session.save()
        
        if self.state.current_state:
            if "session_state" not in self.state.current_state:
                 self.state.current_state["session_state"] = {}
            self.state.current_state["session_state"]["is_complete"] = True
            self.state.current_state["session_state"]["score"] = score
            self.state.save()
        
        self._update_game_statistics(score)
        
        return self.state.current_state

    # =======================================================
    # THIS IS THE METHOD THAT WAS MISSING OR INDENTED INCORRECTLY
    # =======================================================
    def _update_game_statistics(self, score: int):
        """Update user's game statistics after a game ends."""
        try:
            stats, created = GameStatistics.objects.get_or_create(
                user=self.session.user,
                game_type=self.session.game_type,
                defaults={
                    'total_games': 1,
                    'total_score': score,
                    'highest_score': score,
                }
            )

            if not created:
                stats.total_games += 1
                stats.total_score += score
                if score > stats.highest_score:
                    stats.highest_score = score
            
            if stats.total_games > 0:
                stats.average_score = stats.total_score / stats.total_games
            else:
                stats.average_score = 0
                
            if self.session.end_time and self.session.start_time:
                duration = self.session.end_time - self.session.start_time
                stats.total_time_played += duration
            
            stats.save()
            
            GameLeaderboard.objects.create(
                user=self.session.user,
                game_type=self.session.game_type,
                score=score
            )
            logger.info(f"Statistics updated for user {self.session.user.id}")

        except Exception as e:
            logger.error(f"Failed to update statistics for user {self.session.user.id}: {str(e)}", exc_info=True)