from abc import ABC, abstractmethod
from ..models import GameSession, GamePlayback, GameState
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
        self.state = GameState.objects.get_or_create(
            session=session,
            defaults={
                'current_state': {},
                'metadata': {}
            }                                         
                                                     
            )[0]
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
            self.session.user.id,game_type)
        
    def cache_game(self, game_type: str, state:dict) -> None:
        """Centralized cache settings for all game modes"""
        self.cache_service.cache_game_session(
            self.session.user.id,
            game_type,
            state
        )
        
    def end_game(self, score: int = 0) -> None:
        """Centralized game ending logic"""
        self.session.score = score
        self.session.completed = True
        self.session.end_time = timezone.now()
        self.session.save()
        self.cache_service.clear_game_session(self.session.user.id, game_type=self.session.game_type)
        
        self.monitoring.track_game_completion(self.session)
        
    def update_game_state(self, state:dict, status: str = None) -> None:
        """Centralized state update method"""
        self.state.update_state(state, status)
        
    def validate_answer(self, answer):
        try:
            result = self._validate_answer_impl(answer)
            self.state.update_state(result, 'answer_validated')
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