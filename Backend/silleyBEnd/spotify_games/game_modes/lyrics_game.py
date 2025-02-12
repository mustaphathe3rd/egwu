from .base import BaseGame
from ..services.ai_service import AIService
from ..services.cache_service import GameCacheService
import random
from difflib import SequenceMatcher
from datetime import timezone
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import speech_recognition as sr
from pydub import AudioSegment
import io
from ..exceptions import *
import logging

logger = logging.getLogger("spotify_games")
class SongData:
    name: str
    artist: str
    spotify_id: str
    track_uri: str
    image_url: str
    lyrics: str
class LyricsGame(BaseGame):
    SIMILARITY_THRESHOLDS = {
        'text': 0.9,
        'voice': 0.75, # More lenient for voice input
    }
    
    def __init__(self, session):
        super().__init__(session)
        self.input_type ='voice' if session.game_type == 'lyrics_voice' else 'text'
        self.ai_service = AIService()
        self.cache_service = GameCacheService()
        
        
    def _initialize_game_impl(self, input_type='text'):
        """Initialize the game with multiple challenges from different songs."""
        # Check cache first
        cached_game = self.get_cached_game('lyrics')
        if cached_game:
            return cached_game
        
        # Get valid songs with non-null lyrics
        songs = self._get_valid_songs(4) 
        if not songs:
            raise GameInitializationError("Not enough songs with lyrics available")
        
        # Randomly select initial song for playback
        current_song = random.choice(songs)
        
        #Setup playback for current song
        self.setup_playback(
            current_song.spotify_id,
            current_song.name,
            current_song.artist,
            current_song.image_url,
            current_song.track_uri
        )
        
        # Gnerate challenge from multiple songs
        all_challenges = []
        for song in songs:
            try:
                # Get 2-3 challenges per song
                num_challenges = random.randint(2, 3)
                song_challenges = self.ai_service.generate_lyrics_challenges(song.lyrics, num_challenges)
                
                # Add song information to each challenge
                for challenge in song_challenges:
                    if "error" not in challenge:
                        challenge["song_data"] = {
                            "name": song.name,
                            "artist": song.artist,
                            "album_image": song.image_url,
                            "spotify_id": song.spotify_id,
                            "track_uri": song.track_uri,
                        }
                    all_challenges.append(challenge)
                    
            except Exception as e:
                logger.error(f"Error generating challenges for song {song.name}: {str(e)}")
                continue
            
        # Ensure we have enough challenges or fall back to basic generation
        if len(all_challenges) < 5:
            logger.warning("Not enough AI-generated challenges, falling back to basic generation")
            all_challenges = self._generate_fallback_challenges(songs)
            
        # Shuffle challenges for variety
        random.shuffle(all_challenges)
                
        
        game_state = {
            'challenge': all_challenges,
            'current_challenge_index': 0,
            'input_type': input_type,
            'attempts': 0,
            'max_attempts': 3 if input_type == 'text' else 5 # More attempts for voice
        }
        
        # Cache the game state
        self.cache_game('lyrics', game_state)
        
        return game_state
    
    def _get_valid_songs(self, count: int) -> List[SongData]:
        """Get songs that have non-null lyrics."""
        songs = self.get_random_songs(count * 2)
        
        def is_valid_lyrics(lyrics: str) -> bool:
            return (lyrics and
                    isinstance(lyrics, str) and
                    lyrics.strip() not in ['', 'No lyrics available'] and
                    len(lyrics.split()) >= 20
                    ) # Ensure enough words for a challenge
            
        # Filter manually since it's a list, not a QuerySet
        filtered_songs = [
            song for song in songs 
            if is_valid_lyrics(song.lyrics)
        ]
        
        return filtered_songs[:count]
    def _generate_lyrics_challenge(self, lyrics: str) -> Dict[str, str]:
        
        # First, normalize the lyrics to ensure consistent spacing
        normalized_lyrics = ' '.join(lyrics.split())
        words = normalized_lyrics.split()
        
        total_length = len(words)
        chunk_size = max(min(total_length // 4, 20), 8)
        
        safe_zone = total_length // 6
        start_idx = random.randint(safe_zone, total_length - chunk_size - safe_zone)
        
        # Get the missing portion
        missing_words = words[start_idx:start_idx + chunk_size]
        missing_portion = ' '.join(missing_words)
        
        # Create challenge lyrics by directly splicing the array
        challenge_words = words.copy()
        placeholder = ' _____ ' * (chunk_size // 2)
        challenge_words[start_idx:start_idx + chunk_size] = [placeholder]
        challenge_lyrics = ' '.join(challenge_words)
        
        return {
            'complete_lyrics': normalized_lyrics,
            'challenge_lyrics': challenge_lyrics,
            'missing_portion': missing_portion,
            'word_count': chunk_size,
        }
        
    def _generate_fallback_challenges(self, songs: List[SongData]) -> List[Dict[str, Any]]:
        """Generate basic challenges without AI in case of failure"""
        challenges = []
        for song in songs:
            challenge = self._generate_lyrics_challenge(song.lyrics)
            challenge["song_data"] = {
                "name": song.name,
                "artist": song.artist,
                "album_image": song.image_url,
                "spotify_id": song.spotify_id,
                "track_uri": song.track_uri
            }
            challenges.append(challenge)
        return challenges[:10]  # Limit to 10 challenges
            
    def _calculate_similarity(self, user_answer: str, correct_lyrics: str, input_type: str = 'text') -> float:
        """Calculate similarity with improved text normalization."""
        def normalize_text(text: str) -> str:
            text = ''.join(text.lower().split())
            if input_type == 'voice':
                # Additional normalization for voice input
                text = text.replace('gonna', 'going to')
                text = text.replace('wanna', 'want to')
                text = text.replace('gotta', 'got to')
                # Remove common speech recognition artifacts
                text = text.replace('.', '')
                text = text.replace(',','')
            return text
        
        normalized_user = normalize_text(user_answer)
        normalized_correct = normalize_text(correct_lyrics)
        
        # For voice input, also consider word-by-word matching
        if input_type == 'voice':
            word_match_ratio = self._calculate_word_match_ratio(
                normalized_user.split(),
                normalized_correct.split()
            )
            sequence_ratio = SequenceMatcher(
                None,
                normalized_user,
                normalized_correct,
            ).ratio()
            # Weight both methods
            return (word_match_ratio + sequence_ratio) / 2
        
        return SequenceMatcher(
            None,
            normalize_text(user_answer),
            normalize_text(correct_lyrics)
        ).ratio()
        
    def _calculate_word_match_ratio(self, user_words: List[str], correct_words: List[str]) -> float:
        """Calculate ratio of matching words, allowing for minor variations."""
        matches = 0
        total_words = len(correct_words)
        
        for user_word in user_words:
            for correct_word in correct_words:
                if (user_word == correct_word or
                    SequenceMatcher(None, user_word, correct_word).ratio() > 0.8):
                    mathces += 1
                    break
        
        return matches / total_words if total_words > 0 else 0
    
    def _validate_answer_impl(self, user_answer: str, input_type: str ='text') -> dict:
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
        
        similarity = self._calculate_similarity(user_answer, correct_lyrics)
    
       # Use different thresholds for text vs voice input
        threshold = self.SIMILARITY_THRESHOLDS.get(input_type, 0.9)
        is_correct = similarity >= threshold
        
        # Calculate score based on similarity
        score = int(similarity * 100) if is_correct else 0
        
        # Update session if correct
        if is_correct:
            self.end_game(score=score)
        
        return {
            'is_correct': is_correct,
            'score': score,
            'feedback': self._generate_feedback(similarity, correct_lyrics),
            'correct_lyrics': correct_lyrics if is_correct else None,
            'similarity': round(similarity * 100, 2),
            'game_completed': self.session.completed
        }
        
    def _generate_feedback(self, similarity: float, input_type: str = 'text') -> str:
        """
        Generate appropriate feedback based on similarity and input type.
        
        Args:
            similarity (float): Similarity ratio between 0 and 1
        
        Returns:
            str: Feedback message for the user
        """
        if input_type == 'voice':
            if similarity >= 0.75:
                return "Great pronunciation! You got the lyrics right!"
            elif similarity >= 0.6:
                return "Pretty close! Try speaking a bit more clearly."
            elif similarity >= 0.4:
                return "Some words matched. Try again with clearer pronunciation."
            else:
                return "Try speaking louder and more clearly."
        else:
            if similarity >= 0.9:
                return "Perfect! You got the lyrics exactly right!"
            elif similarity >= 0.8:
                return "Very close! Just a few small differences."
            elif similarity >= 0.6:
                return "You've got some of it right, but there are significant differences."
            elif similarity >= 0.4:
                return "You're on the right track, but quite different from the actual lyrics."
            else:
                return "Keep trying! Listen carefully to the lyrics in this section."
            
    def validate_voice_answer(self, audio_data: bytes) -> Dict:
        """
        Validate answer from voice input (when game is in voice mode).
        
        Args:
            audio_text (str): Transcribed text from voice input
            
        Returns:
            dict: Validation results including score and feedback
        """     
       # Process voice input
        voice_result = self.process_voice_input(audio_data)
       
        if not voice_result['success']:
           return {
               'is_correct': False,
               'error': voice_result['error'],
               'should_retry': True,
           }
           
        # Get transcribed text
        transcribed_text = voice_result['text']
        
        # Validate with more lenient threshold
        result = self._validate_answer_impl(
            transcribed_text,
            input_type='voice',
        )
        
        # Add voice-specific feedback
        result['transcribed_text'] = transcribed_text
        result['confidence'] = voice_result.get('confidence', 0)
        
        return result
    
    def process_voice_input(self, audio_data: bytes) -> Dict:
        """Process voice input and convert tot text."""
        try:
            # Convert audio bytes to AudioSegment
            audio = AudioSegment.from_wav(io.BytesIO(audio_data))
            
            # Normalize audio
            normalized_audio = audio.normalize()
            
            # convert to wav for speech recognition
            wav_data = io.BytesIO()
            normalized_audio.export(wav_data, format="wav")
            wav_data.seek(0)
            
            # Convert to audio data for recognition
            with sr.AudioFile(wav_data) as source:
                audio = self.recognizer.record(source)
                
            # Attempt speech recognition
            text = self.recognizer.recognize_google(audio)
            
            return {
                'success': True,
                'text': text,
            }
        except sr.UnknownValueError:
            return {
                'success': False,
                'error': 'Could not understand audio'
            }   
        except sr.RequestError as e:
            return {
                'success': False,
                'error': f'Recognition service error: {str(e)}'
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': f'Error processing audio: {str(e)}'
            }