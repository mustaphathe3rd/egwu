from .base import BaseGame
from ..services.ai_service import AIService
from ..services.cache_service import GameCacheService
from spotify.models import MostListenedSongs
import random
from ..exceptions import *

class CrosswordGame(BaseGame):
    def __init__(self, session):
        super().__init__(session)
        self.ai_service = AIService()
        self.cache_service = GameCacheService()
        
    def _initialize_game_impl(self):
        
        # check cache first
        cached_game = self.get_cached_game('crossword')
        if cached_game:
            return cached_game
        
        song = self._get_valid_song()
        if not song:
                raise GameInitializationError("No song with lyrics available")           
        
        # Setup playback for the song
        self.setup_playback(
            song.spotify_id,
            song.name,
            song.artist,
            song.image_url,
            song.track_uri
        )
        
        # Generate crossword puzzle using AI
        puzzle_data = self.ai_service.generate_crossword(song.lyrics)
        
        game_state = {
            'song_data': {
                'name': song.name,
                'artist': song.artist,
                'album_image': song.image_url,
                'spotify_id': song.spotify_id,
                'preview_url': song.track_uri
            },
            'puzzle_data': puzzle_data,
            'solved_words': []
        }
        
        # Cache the game state
        self.cache_game('crossword', game_state)
            
        
        return game_state
    
    def _get_valid_song(self):
        """Get a song with non-null, valid lyrics."""
        return self.get_random_songs(1).filter(
            lyrics_isnull=False
        ).exclude(
            lyrics_in=['', 'No lyrics available']
        ).first()
    
    def _validate_answer_impl(self, answer_data):
      
        word = answer_data.get('word')
        position = answer_data.get('position')
      
        if not all([word, position]):
            raise GameError("invalid answer data")
        
        current_state = self.state.current_state
          
        if self._check_word(word, position):
            current_state['solved_words'].append(word)
            self.update_state(current_state)
            
            if len(current_state['solved_words']) == len(current_state['puzzle_data']['words']):
                self.end_game(score = 100)
            return True
        return False
    
    def get_current_state(self):
        return {
            'puzzle_data': self.state.current_state['puzzle_data'],
            'solved_words': self.state.current_state['solved_words'],
            'completed': self.session.completed
        }
    
    def _check_word(self, word, position):
        puzzle_data = self.state.current_state['puzzle_data']
        return word.lower() == puzzle_data['words'][position].lower()
    