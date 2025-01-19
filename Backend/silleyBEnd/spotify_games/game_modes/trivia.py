from .base import BaseGame
from ..services.ai_service import AIService
from ..services.cache_service import GameCacheService
from ..models import GamePlayback
import random
from spotify.models import MostListenedSongs, MostListenedArtist

class TriviaGame(BaseGame):
    def __init__(self, session):
        super().__init__(session)
        self.ai_service = AIService()
        self.cache_service = GameCacheService()
        
        
    def initialize_game(self):
        # Check cache first
        cache_key = f"trivia_game_{self.session.id}"
        cached_game = self.cache.service.get_game_session(
            self.session.user.id,
            cache_key
        )
        if cached_game:
            return cached_game
        
        #Get multipl
        artists = self._get_valid_artists(3)
        if not artists:
            return {
                'error': 'Not enough artists with biography available. Try refreshing your music data.'
            }
            
        questions = []
        
        for artist in artists:
            #Generate questions for this artist    
            artist_data = {
                'biography': artist.biography,
                'genres': artist.genres,
                'career_highlights': self._get_career_highlights(artist)
            }
            
            artist_questions = self.ai_service.generate_trivia_questions(artist_data)
            questions.extend(artist_questions)
            
        #shuffle questions
        random.shuffle(questions)
        
        game_state = {
            'artist_data': {
                'name': (artist.name for artist in artists),
                'image_url': (artist.image_url if artist.image_url else '/static/default_artist.png' for artist in artists)
            },
            'questions': questions[:10],
            'current_question': 0,
            'score': 0,
            'total_question' : 5
        }
        
        self.cache_service.cache_game_session(
            self.session.user.id,
            cache_key,
            game_state
        )
        
        return game_state
    
    def _get_valid_artists(self, count):
        """Get an artist with non-null, valid biography."""
        return self.get_random_artists(count * 2).filter(
            biography_isnull = False
        ).exclude(
            biography__in=['', 'No biography available', 'NULL']
        )[:count]
        
    def _get_career_highlights(self, artist):
        return {
            'debut_year': artist.debut_year,
            'most_popular_song': artist.most_popular_song,
            'albums_count': artist.num_albums,
            'popularity_score': artist.popularity
        }
        
    def validate_answer(self, answer):
        current_state = self.state.current_state
        current_question = current_state['questions'][current_state['current_question']]
        
        is_correct = answer.lower() == current_question['correct_answer'].lower()
        if is_correct:
            current_state['score'] += 1
            
        current_state['current_question'] += 1
        self.update_state(current_state)
        
        if current_state['current_question'] >= len(current_state['questions']):
            self.end_game()
            
        return {
            'correct': is_correct,
            'next_question': self._get_current_question()
        }
    
    def get_current_state(self):
        return{
            'current_question': self._get_current_question(),
            'score': self.state.current_state['score'],
            'total_questions': len(self.state.current_state['questions']),
            'completed': self.session.completed
        }
        
    def _get_current_question(self):
        if self.session.completed:
            return None
        
        current_state = self.state.current_state
        if current_state['current_question'] >= len(current_state['questions']):
            return None
        
        question = current_state['questions'][current_state['current_question']]
        return{
            'question': question['question'],
            'options': question['options']
        }
        
    