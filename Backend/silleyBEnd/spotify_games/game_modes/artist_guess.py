from .base import BaseGame
from spotify.models import MostListenedSongs, MostListenedArtist
from difflib import SequenceMatcher

class ArtistGuessGame(BaseGame):
    def __init__(self, session):
        super().__init__(session)
        
    def initialize_game(self):
        artist = self.get_random_artists(1)[0]
        song = MostListenedSongs.objects.filter(
            user=self.session.user,
            artist=artist.name
        ).first()
        
        if song:
            self.setup_playback(
                song.spotify_id,
                song.name,
                artist.name,
                artist.image_url,
                song.preview_url   
            )
            
        #Initial hints are genres and debut year
        return{
            'artist_id': artist.id,
            'revealed_hints': {
                'genres': artist.genres,
                'debut_year': artist.debut_year
            },
            'available_hints': [
                'birth_year',
                'num_albums',
                'members',
                'gender',
                'popularity',
                'most_popular_song'
            ]
        }
        
    def validate_guess(self, guess:str, artist_name: str):
        similarity = SequenceMatcher(None, guess.lower(), artist_name.lower().ratio())
       
        result = {
            'correct': similarity > 0.9,
            'similarity': similarity,
            'feedback': self._get_similarity_feedback(similarity)
        }
        
        if result['correct'] or self.session.current_tries >= self.session.max_tries:
            result['artist_data'] = {
                'name': artist_name,
                'image_url': artist.image_url,
                'preview_url': self.playback.preview_url if hasattr(self, 'playback') else None
            }
            
        return result
    
    def _get_similarity_feedback(self, similarity):
        if similarity > 0.9:
            return "Correct!"
        elif similarity > 0.7:
            return "Very Close!"
        elif similarity > 0.5:
            return "Getting warmer..."
        elif similarity > 0.3:
            return "on the right track..."
        else:
            return "Not quite...."