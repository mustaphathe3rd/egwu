from .base import BaseGame
from ..services.ai_service import AIService
from ..services.cache_service import GameCacheService
from spotify.models import MostListenedSongs
import random
from ..exceptions import *
import logging

logger = logging.getLogger("spotify_games")
class CrosswordGame(BaseGame):
    def __init__(self, session):
        super().__init__(session)
        self.ai_service = AIService()
        self.cache_service = GameCacheService()
        
    def _initialize_game_impl(self):
        
        #check cache first
        cached_game = self.get_cached_game('crossword')
        if cached_game:
            return cached_game
        
        song = self._get_valid_song(1)
        if not song:
                raise GameInitializationError("No song with lyrics available")           
            
        song = song[0]
        
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
        
        logger.debug(f"Initial State: {game_state}")
        
        # Cache the game
        self.cache_game('crossword', game_state)
            
        return game_state
    
    def _get_valid_song(self, count):
        """Get a song with non-null, valid lyrics."""
        songs = self.get_random_songs(count * 4)
        # Use list comprehension with the correct if statement
        valid_songs = [
            song for song in songs
            if song.lyrics is not None and song.lyrics not in ['', 'No lyrics available']
        ]

        return valid_songs[:count]

    
    def _validate_answer_impl(self, answer_data):
        """
        Validates answers for crossword puzzle.
        Expects answer_data to contain a comma-seperated string of words.
        """
        try:
          # Split the incoming comma-separated answer string
            submitted_words = answer_data.get('answer','').split(',')
          
            if not submitted_words:
                raise GameError("No answers provided")
          
            current_state = self.state.current_state
            puzzle_data = current_state['puzzle_data']
          
            # Check each word against the solution
            correct_words = []
            for i, submitted_word in enumerate(submitted_words):
                if i >= len(puzzle_data['words']):
                    break
              
                if submitted_word.strip().lower() == puzzle_data['words'][i]['word'].lower():
                    correct_words.append(submitted_word.strip())
                  
            # Update solved words
            current_state = self.get_current_state()
            current_state['solved_words'] = correct_words
            
            # Update the GameState model
            game_state = self.session.gamestate.first()
            if game_state:
                game_state.update_state(current_state)
        
            if len(correct_words) == len(puzzle_data['words']):
                self.end_game(score=100)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error validating crossword answer: {str(e)}")
            raise GameError("Invalid answer format")
        #Check if
    def get_current_state(self):
        return {
            'song_data': self.state.current_state['song_data'],
            'puzzle_data': self.state.current_state['puzzle_data'],
            'solved_words': self.state.current_state['solved_words'],
            'completed': self.session.completed
        }
    
    def _check_word(self, word, position):
        puzzle_data = self.state.current_state['puzzle_data']
        return word.lower() == puzzle_data['words'][position].lower()
    