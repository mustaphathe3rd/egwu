from .base import BaseGame
from ..services.ai_service import AIService
from ..services.cache_service import GameCacheService
from ..models import GamePlayback
import random
from spotify.models import MostListenedSongs, MostListenedArtist
import logging
from django.utils import timezone
class GameInitializationError(Exception):
    pass

class GameError(Exception):
    pass

logger = logging.getLogger("spotify_games")
class TriviaGame(BaseGame):
    def __init__(self, session):
        super().__init__(session)
        self.ai_service = AIService()
        self.cache_service = GameCacheService()
        self.QUESTIONS_PER_GAME = 6
        self.MIN_ARTISTS = 3
        self.QIESTIONS_PER_ARTIST = 3
        
        
    def _initialize_game_impl(self):
        """Initialize a new trivia game or retrieve cached game."""
        cached_game = self.cache_service.get_game_session(self.session.user.id, 'trivia')
        if cached_game:
            logger.debug(f"cached_game: {cached_game}")
            return self._prepare_game_state(cached_game)
        
        try:
            artists = self._get_valid_artists(self.MIN_ARTISTS)
            if not artists:
                raise GameInitializationError(
                    'Not enough artists with biography available. Try refreshing your music data.'
                )
                
            questions = self._generate_questions(artists)
            if len(questions) < self.QUESTIONS_PER_GAME:
                raise GameInitializationError(
                    'Not enough valid questions generated. Please try again.'
                )
            
            original_state = {
            'artists': [{'name': artist.name, 'image_url': artist.image_url} for artist in artists],
            'questions': questions,
            'current_question': 0,
            'score': 0,
            'total_questions': self.QUESTIONS_PER_GAME,
            'status': 'active'
        }
            
            self.cache_service.cache_game_session(self.session.user.id,'trivia',{'full_state': original_state})
            
            frontend_state = self._prepare_game_state(original_state)
            
            logger.debug(f"Game state returned: {frontend_state}")
            return frontend_state
        
        except Exception as e:
            logger.error(f"failed to Initialize trivia game: {str(e)}")
            raise GameInitializationError(str(e))
    
    def _generate_questions(self, artists):
        """Generate andvalidate questions for multiple artists."""
        all_questions = []
        min_required_questions = self.QUESTIONS_PER_GAME
        max_attempts = len(artists) * 2
        attempts = 0
        
        while len(all_questions) < min_required_questions and attempts < max_attempts:
          # Cycle through artists if needed
            artist = artists[attempts % len(artists)]
            attempts += 1
            
            try:
                artist_data = {
                    'biography': artist.biography,
                    'genres': artist.genres or ['Unknown'],
                    'career_highlights': {
                        'debut_year': getattr(artist, 'debut_year', 'Unknown'),
                        'most_popular_song': getattr(artist, 'most_popular_song', 'Unknown'),
                        'albums_count': getattr(artist, 'num_albums', 'Unknown'),
                        'popularity_score': getattr(artist, 'popularity', 'Unknown')
                    }
                }
                
                new_questions = self.ai_service.generate_trivia_questions(artist_data)
                if new_questions:  # Only extend if we got valid questions
                    all_questions.extend(new_questions)
                    logger.info(f"Generated {len(new_questions)} questions for {artist.name}")
                
            except Exception as e:
                logger.warning(f"Failed to generate questions for {artist.name}: {str(e)}")
                continue
                
        # Shuffle and trim questions
        random.shuffle(all_questions)
        return all_questions[:self.QUESTIONS_PER_GAME]
  
        
    def _get_valid_artists(self, count):
        """Get an artist with non-null, valid biography."""
        artists = self.get_random_artists(count * 2) # This is a list
        
        # Filter out invalid biographies using list comprehension
        valid_artists = [
            artist for artist in artists
            if artist.biography and artist.biography not in ['','No biography available','NULL']
        ]
        
        return valid_artists[:count]
        
    def _get_career_highlights(self, artist):
        return {
            'debut_year': artist.debut_year if artist.debut_year else 'Unknown',
            'most_popular_song': artist.most_popular_song if artist.most_popular_song else 'Unknown',
            'albums_count': artist.num_albums if artist.num_albums else 'Unknown',
            'popularity_score': artist.popularity if artist.popularity else 'Unknown',
        }
    
    def _prepare_game_state(self, state):
        """Prepare the current game state for frontend consumption"""
        if not state['questions']:
           return None
       
        current_q_index = state['current_question']
        if current_q_index >= len(state['questions']):
            return None

        current_q = state['questions'][current_q_index]
        return {
            'question': current_q['question'],
            'options': current_q['options'],
            'current_question': state['current_question'],
            'total_questions': len(state['questions']),
            'score': state['score'],
            'completed': self.session.completed
        }
        
    def validate_answer(self, answer_data):
        """Validate an answer submission and update game state."""
        # Get the full game state from cache
        cached_data = self.cache_service.get_game_session(
            self.session.user.id,
            'trivia'
        )
        
        logger.info(f"cached_state: {cached_data}")
        
        
        # if not cached_state or 'current_state' not in cached_state:
        #     logger.error("No cached game state found")
        #     raise GameError("Game state not found")
            
        # current_state = cached_state.get('current_state', {})
        # logger.info(f"current_state cached: {current_state}")
        full_state = cached_data.get('full_state')
        logger.info(f"full_state: {full_state}")
        
        if not full_state or 'questions' not in full_state:
            logger.error("Missing questions in game state")
            raise GameError("Invalid game state structure")

        current_index = full_state.get('current_question', 0)
        if current_index >= len(full_state['questions']):
            raise GameError("All questions already answered")

        current_q = full_state['questions'][current_index]
        submitted_answer = answer_data.get('answer', '').strip()
        
        if not submitted_answer:
            raise GameError("No answer provided")

        # Validate the answer
        is_correct = submitted_answer.lower() == current_q['correct_answer'].lower()
        
        # Update game state
        new_state = {
            **full_state,
            'current_question': current_index + 1,
            'score': full_state.get('score', 0) + (1 if is_correct else 0)
        }

        # Check if game is completed
        if new_state['current_question'] >= len(full_state['questions']):
            self.session.completed = True
            self.session.end_time = timezone.now()
            self.session.score = new_state['score']
            self.session.save()

        # Cache the updated state
        self.cache_service.cache_game_session(
            self.session.user.id,
            'trivia',
            {'full_state': new_state}
        )

        # Return the response for the frontend
        return {
            'question': current_q.get('question'),
            'options': current_q.get('options', []),
            'current_question': new_state['current_question'],
            'total_questions': len(full_state['questions']),
            'score': new_state['score'],
            'is_correct': is_correct,
            'feedback': 'Correct!' if is_correct else 'Incorrect!',
            'explanation': current_q.get('explanation', ''),
            'completed': self.session.completed
        }

    def get_current_state(self):
        """Get the current game state."""
        cached_data = self.cache_service.get_game_session(
            self.session.user.id,
            'trivia'
        )
        
        if not cached_data or 'full_state' not in cached_data:
            return None
            
        full_state = cached_data['full_state']
        if 'questions' not in full_state:
            return None
            
        current_index = full_state.get('current_question', 0)
        if current_index >= len(full_state['questions']):
            return None
            
        current_q = full_state['questions'][current_index]
        
        return {
            'question': current_q.get('question'),
            'options': current_q.get('options', []),
            'current_question': current_index,
            'total_questions': len(full_state['questions']),
            'score': full_state.get('score', 0),
            'completed': self.session.completed
        }
    
    