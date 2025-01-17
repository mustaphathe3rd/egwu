from abc import ABC, abstractmethod
from ..models import GameSession, GamePlayback
from spotify.models import MostListenedSongs, MostListenedArtist
import random   

class BaseGame(ABC):
    def __init__(self, session: GameSession):
        self.session = session
    
    def setup_playback(self, track_id: str, track_name: str,
                       artist_name: str, album_image: str, preview_url:str):
        return GamePlayback.objects.create(
            session=self.session,
            spotify_track_id=track_id,
            track_name=track_name,
            artist_name=artist_name,
            album_image_url = album_image,
            preview_url = preview_url
        )
        
    def get_random_songs(self, count=1):
        songs = MostListenedSongs.objects.filter(
            user = self.session.user
        ).order_by('?')[:count]
        return list(songs)
    
    def get_random_artists(self, count=1):
        artists = MostListenedArtist.objects.filter(
            user=self.session.user
        ).order_by('?')[:count]
        return list(artists)