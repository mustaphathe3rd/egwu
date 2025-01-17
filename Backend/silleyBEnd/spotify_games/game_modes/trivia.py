from .base import BaseGame
from ..services.ai_service import AIService
from ..models import GamePlayback
import random
from spotify.models import MostListenedSongs, MostListenedArtist

class TriviaGame(BaseGame):
    def __init__(self, session):
        super().__init__(session)
        self.ai_service = AIService()
        
        
    def initialize_game(self):
    
        #Get multiple artists for varied questiosn
        artists = self.get_random_artists(3)
        questions = []
        
        for artist in artists:
            #Get a random song for each artist
            song = self.get_artist_song(artist)
            if song:
                self.setup_playback(
                    song.spotify_id,
                    song.name,
                    artist.name,
                    song.album_image,
                    song.preview_url
                )
            
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
        
        return {
            'questions': questions[:10], #Pick top 10 questions
            'current_question': 0,
            'score': 0,
            'total_question': 5
        }
        
    def _get_career_highlights(self, artist):
        return {
            'debut_year': artist.debut_year,
            'most_popular_song': artist.most_popular_song,
            'albums_count': artist.num_albums,
            'popularity_score': artist.popularity
        }
        
    def get_artist_song(self, artist):
        return MostListenedSongs.objects.filter(
            user = self.session.user,
            artist=artist.name
        ).order_by('?').first()
            
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
        