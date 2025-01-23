from .base import BaseGame
from ..services.ai_service import AIService
from ..services.cache_service import GameCacheService
import random
from difflib import SequenceMatcher
from datetime import timezone

from ..exceptions import *
class LyricsGame(BaseGame):
    def __init__(self, session):
        super().__init__(session)
        self.ai_service = AIService()
        self.cache_service = GameCacheService()
        
        
    def _initialize_game_impl(self, input_type='text'):
        #check cache first
        cached_game = self.get_cached_game('lyrics')
        if cached_game:
            return cached_game
        
        # Get valid songs with non-null lyrics
        songs = self._get_valid_songs(7) 
        if not songs:
            raise GameInitializationError("Not enough songs with lyrics available")
            
        current_song = songs[0]
        
        #Setup playback for current song
        self.setup_playback(
            current_song.spotify_id,
            current_song.name,
            current_song.artist,
            current_song.image_url,
            current_song.track_uri
        )
        
        #Generate lyrics challenge
        challenge = self._generate_lyrics_challenge(current_song.lyrics)
        
        game_state = {
            'song_data': {
                'name': current_song.name,
                'artist': current_song.artist,
                'album_image': current_song.image_url,
                'spotify_id': current_song.spotify_id,
                'track_uri': current_song.track_uri
            },
            'challenge': challenge,
            'input_type': input_type
        }
        
        # Cache the game state
        self.cache_game('lyrics', game_state)
        
        return game_state
    
    def _get_valid_songs(self, count):
        """Get songs that have non-null lyrics."""
        return self.get_random_songs(count * 2).filter(
            lyrics_isnull = False
        ).exclude(
            lyrics_in=['', 'No lyrics available']
        )[:count]
        
    def _generate_lyrics_challenge(self, lyrics):
        words = lyrics.split()
        chunk_size = len(words) // 4
        start_idx = random.randint(0, len(words) - chunk_size)
        
        missing_portion = ' '.join(words[start_idx:start_idx + chunk_size])
        challenge_lyrics = lyrics.replace(missing_portion,'_____')
        
        return{
            'complete_lyrics': lyrics,
            'challenge_lyrics': challenge_lyrics,
            'missing_portion': missing_portion
        }
        
    def _validate_answer_impl(self, user_answer: str) -> dict:
        """
        Validate the user's answer against the correct lyrics.
        
        Args:
            user_answer (str): The user's submitted answer
            
        Returns:
            dict: Validation results including score, feedback, and game state
        """
        
        #Get current gamr state from cache
        current_game = self.get_cached_game('lyrics')
        if not current_game:
           raise GameError("Game Session not found")
            
        correct_lyrics = current_game['challenge']['missing_portion']
        
        # Calculate similarity ratio between user answer and correct lyrics
        similarity = SequenceMatcher(
            None,
            user_answer.lower().strip(),
            correct_lyrics.lower().strip()
        ).ratio()
        
        # Determine if answer is correct (90% similarity threshold)
        is_correct = similarity >= 0.9
        
        # Calculate score based on similarity
        score = int(similarity * 100) if is_correct else 0
        
        # Update session if correct
        if is_correct:
            self.end_game(score=self.session.score)
            
        # Prepare feedback based on similarity
        feedback = self._generate_feedback(similarity, correct_lyrics)
        
        return {
            'is_correct': is_correct,
            'score': score,
            'feedback': feedback,
            'correct_lyrics': correct_lyrics if is_correct else None,
            'similarity': round(similarity * 100, 2),
            'game_completed': self.session.completed
        }
        
    def _generate_feedback(self, similarity: float, correct_lyrics: str) -> str:
        """
        Generate appropriate feedback based on answer similarity.
        
        Args:
            similarity (float): Similarity ratio between 0 and 1
            correct_lyrics (str): The correct lyrics
        
        Returns:
            str: Feedback message for the user
        """
        if similarity >= 0.9:
            return "Perfect! You got the lyrics exactly right!"
        elif similarity >= 0.8:
            return "Very close! Just a few small differences."
        elif similarity >= 0.6:
            return "You've got some of it right, but there are significant differences."
        elif similarity >= 0.4:
            return "You're on the right track, but quite different from the actual lyrics."
        else:
            return "These lyrics are quite different from the correct ones. Try again!"
        
    def validate_voice_answer(self, audio_text: str) -> dict:
        """
        Validate answer from voice input (when game is in voice mode).
        
        Args:
            audio_text (str): Transcribed text from voice input
            
        Returns:
            dict: Validation results including score and feedback
        """     
        # Voice input might have more variation, so we use a lower threshold
        result = self.validate_answer(audio_text)
        
        # Adjust similarity threshold for voice input
        if not result['is_correct'] and result['similarity'] >= 75: # More lenient for voice
            result['is_correct'] = True
            result['score'] = int(result['similarity'])
            
        return result
    
   