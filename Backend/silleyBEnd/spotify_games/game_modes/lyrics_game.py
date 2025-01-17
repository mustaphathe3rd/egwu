from .base import BaseGame
from ..services.ai_service import AIService
import random


class LyricsGame(BaseGame):
    def __init__(self, session):
        super().__init__(session)
        self.ai_service = AIService()
        
        
    def initialize_game(self, input_type='text'):
        songs = self.get_random_songs(7) #Get 5 random songs for the session
        current_song = songs[0]
        
        #Setup playback for current song
        self.setup_playback(
            current_song.spotify_id,
            current_song.name,
            current_song.artist,
            current_song.album_image,
            current_song.preview_url
        )
        
        #Generate lyrics challenge
        challenge = self._generate_lyrics_challenge(current_song.lyrics)
        
        return{
            'song_data': {
                'name': current_song.name,
                'artist': current_song.artist,
                'album_image': current_song.album_image,
                'spotify_id': current_song.spotify_id,
                'preview_url': current_song.preview_url
            },
            'challenge': challenge,
            'input_type': input_type
        }
        
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