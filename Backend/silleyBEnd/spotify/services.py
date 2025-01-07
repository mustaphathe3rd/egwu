import asyncio
from functools import partial
import logging
from datetime import timedelta
from django.core.cache import cache
from django.conf import settings
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
from .models import User, TopTracksCountry, GlobalTopTracks
import backoff
from django.db import transaction

logger = logging.getLogger(__name__)

class SpotifyService:
    def __init__(self, user_id=None):
        self.client_credentials_manager = SpotifyClientCredentials(
            client_id=settings.SPOTIFY_CLIENT_ID,
            client_secret=settings.SPOTIFY_CLIENT_SECRET
        )
        self.spotify = Spotify(
            client_credentials_manager=self.client_credentials_manager,
            requests_timeout=60
        )
        self.user_id = user_id

    async def get_user_country(self):
        try:
            user = await User.objects.aget(spotify_id=self.user_id)
            return user.country or 'US'  # Default to US if no country set
        except User.DoesNotExist:
            logger.warning(f"User {self.user_id} not found, using default country")
            return 'US'

    @backoff.on_exception(backoff.expo, Exception, max_tries=3)
    async def get_top_tracks_by_country(self, limit=50):
        country_code = await self.get_user_country()
        logger.info(f"Fetching top tracks for country: {country_code}")

        cache_key = f"top_tracks_{country_code}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data

        try:
            tracks = await asyncio.to_thread(
                partial(
                    self.spotify.search,
                    q=f"tag:new market:{country_code}",
                    type='track',
                    limit=limit,
                    market=country_code
                )
            )

            tracks_data = []
            for track in tracks['tracks']['items']:
                # Get artist genres
                artist_id = track['artists'][0]['id']
                artist_info = await asyncio.to_thread(
                    self.spotify.artist, artist_id
                )

                track_data = {
                    'spotify_id': track['id'],
                    'name': track['name'],
                    'artist': track['artists'][0]['name'],
                    'album': track['album']['name'],
                    'genres': ', '.join(artist_info['genres']),
                    'duration_seconds': round(track['duration_ms'] / 1000),
                    'release_date': track['album']['release_date'],
                    'popularity': track['popularity'],
                    'country_code': country_code
                }
                tracks_data.append(track_data)

            # Cache for 1 hour
            cache.set(cache_key, tracks_data, timeout=3600)
            
            # Save to database
            await self._save_tracks(tracks_data)
            
            return tracks_data

        except Exception as e:
            logger.error(f"Error fetching top tracks for {country_code}: {e}")
            raise

    @staticmethod
    async def _save_tracks(tracks_data):
        for track in tracks_data:
            await TopTracksCountry.objects.update_or_create(
                spotify_id=track['spotify_id'],
                defaults=track
            )
            
class GlobalSpotifyService:
    GLOBAL_TOP_50_ID = "37i9dQZEVXbMDoHDwVN2tF"  # Spotify's Global Top 50 playlist ID

    def __init__(self):
        self.client_credentials_manager = SpotifyClientCredentials(
            client_id=settings.SPOTIFY_CLIENT_ID,
            client_secret=settings.SPOTIFY_CLIENT_SECRET
        )
        self.spotify = Spotify(
            client_credentials_manager=self.client_credentials_manager,
            requests_timeout=60
        )
        
    @backoff.on_exception(backoff.expo, Exception, max_tries=3)
    async def get_global_top_tracks(self, limit=50):
        """Fix playlist search error handling"""
        cache_key = "global_top_tracks"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data

        try:
            playlist_id = self.GLOBAL_TOP_50_ID  # Default fallback
            
            playlist_results = await asyncio.to_thread(
                self.spotify.search,
                q="Top 50 - Global",
                type="playlist",
                limit=1
            )
            
            if playlist_results and playlist_results.get('playlists', {}).get('items'):
                playlist_id = playlist_results['playlists']['items'][0]['id']
                
            logger.info(f"Using playlist ID: {playlist_id}")
            
            tracks = await asyncio.to_thread(
                self.spotify.playlist_tracks,
                playlist_id,
                limit=limit
            )
            
            if not tracks or 'items' not in tracks:
                raise ValueError("No tracks found in playlist")
                
            tracks_data = []
            for idx, item in enumerate(tracks['items'], 1):
                track = item['track']
                
                # Get artist genres
                artist_id = track['artists'][0]['id']
                artist_info = await asyncio.to_thread(
                    self.spotify.artist, artist_id
                )

                track_data = {
                    'spotify_id': track['id'],
                    'name': f"{idx}. {track['name']}",
                    'artist': track['artists'][0]['name'],
                    'album': track['album']['name'],
                    'genres': ', '.join(artist_info['genres']),
                    'duration_seconds': round(track['duration_ms'] / 1000),
                    'release_date': track['album']['release_date'],
                    'popularity': track['popularity'],
                }
                tracks_data.append(track_data)
                
            # Cache for 1 hour
            cache.set(cache_key, tracks_data, timeout=3600)
            
            await self._save_tracks(tracks_data)
            
            return tracks_data
        
        except Exception as e:
            logger.error(f"Error fetching global top tracks: {e}")
            raise
        
    @staticmethod
    async def _save_tracks(tracks_data):
        async with transaction.atomic():
            #Clear existing tracks
            await GlobalTopTracks.objects.all().delete()
            
            #Create new entries
            await GlobalTopTracks.objects.bulk_create(
                [GlobalTopTracks(**track) for track in tracks_data]
            )