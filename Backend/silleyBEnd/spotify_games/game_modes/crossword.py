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
        Validates the user's submitted crossword answers by parsing the grid state.
        """
        try:
            submitted_grid_str = answer_data.get('answer', '')
            if not submitted_grid_str:
                raise GameError("No answer grid provided.")

            # Parse the submitted grid string into a 2D list of characters
            submitted_grid = [list(row) for row in submitted_grid_str.split('\n')]

            current_state = self.state.current_state
            solution_words = current_state['puzzle_data']['words']
            
            if not solution_words:
                raise GameError("No solution words found in game state.")

            correct_count = 0
            total_words = len(solution_words)

            # Iterate through each solution word and check it against the user's grid
            for word_info in solution_words:
                solution_word = word_info['word']
                pos = word_info['position']
                x, y, direction = pos['x'], pos['y'], pos['direction']
                
                user_word = ""
                # Extract the user's word from their submitted grid based on position
                for i in range(len(solution_word)):
                    if direction == 'across':
                        user_word += submitted_grid[y][x + i]
                    else: # down
                        user_word += submitted_grid[y + i][x]
                
                # Compare the user's word with the solution
                if user_word.strip().upper() == solution_word:
                    correct_count += 1

            score = int((correct_count / total_words) * 100) if total_words > 0 else 0
            is_complete = correct_count == total_words
            
            if is_complete:
                self.end_game(score=score)

            return {
                'is_correct': is_complete,
                'score': score,
                'feedback': f'You got {correct_count} out of {total_words} words correct!',
                'completed': is_complete,
            }

        except (IndexError, KeyError) as e:
            logger.error(f"Error parsing crossword answer grid: {e}", exc_info=True)
            raise GameError("Invalid answer format for crossword grid.")
        except Exception as e:
            logger.error(f"Error validating crossword answer: {e}", exc_info=True)
            raise GameError("An unexpected error occurred during validation.")
        
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
    