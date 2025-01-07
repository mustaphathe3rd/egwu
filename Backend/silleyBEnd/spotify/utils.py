import asyncio
import logging
from datetime import datetime, timedelta
from functools import partial, wraps
from typing import List, Dict, Tuple, Optional

import aiohttp
import backoff
import requests
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from requests_oauthlib import OAuth1Session
from spotipy import Spotify, SpotifyException, SpotifyOAuth

from .constants import SCOPE
from .models import (MostListenedAlbum, MostListenedArtist, MostListenedSongs,
                     RelatedArtist, User)
from .token_manager import TokenManager

logger = logging.getLogger("spotify")

token_manager = TokenManager()

def should_update_data(last_updated):
    # Check if last_updated is more than 7 days ago
    return timezone.now() - last_updated > timedelta(weeks=1)
def authenticate_user(request, code):
    sp_oauth = SpotifyOAuth(
        client_id=settings.SPOTIFY_CLIENT_ID,
        client_secret=settings.SPOTIFY_CLIENT_SECRET,
        redirect_uri=settings.SPOTIFY_REDIRECT_URI,
        scope=SCOPE,
    )

    try:
        # Get token from Redisu first
        token_info = token_manager.get_token(request.session.get('user_id'))
        
        if token_info and sp_oauth.is_token_expired(token_info):
            token_info = sp_oauth.refresh_access_token(token_info["refresh_token"])
            if token_info:
                token_manager.store_token(request.session['user_id'], token_info)
        
        if not token_info:
            token_info = sp_oauth.get_access_token(code)
            if token_info and "access_token" in token_info:
                # Store in Redis and session
                user_info = Spotify(auth=token_info["access_token"]).current_user()
                request.session['user_id'] = user_info['id']
                token_manager.store_token(user_info['id'], token_info)

        return token_info

    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return None
    
def create_or_update_user(token_info):
    try:
        sp = Spotify(auth=token_info["access_token"],requests_timeout=60)
        user_info = sp.current_user()
        user, created = User.objects.update_or_create(
            spotify_id=user_info['id'],
            defaults={
                'display_name': user_info.get('display_name', ''),
                'email': user_info.get('email'),
                'country': user_info.get('country', 'US')
            }
        )
        return user
    except Exception as e:
        logger.error(f"Error creating/updating user: {e}")
        raise

def error_response(message, status=500):
    return JsonResponse({
        "error": message,
        "timestamp": datetime.now().isoformat()
    }, status=status)
@sync_to_async
def get_last_updated1(track_id,user):
    return MostListenedSongs.objects.filter(
        spotify_id=track_id,
        user=user
    ).values('last_updated').first()
    
@sync_to_async
def bulk_create_tracks(track_updates):
    """Fix field name from release_data to release_date"""
    return MostListenedSongs.objects.bulk_create(
        track_updates,
        update_fields=[
            "name", "artist", "album", "release_date",
            "duration_seconds", "popularity", "genres"
        ]
    )

@sync_to_async
def get_last_updated2(album_id,user):
    return MostListenedAlbum.objects.filter(
        spotify_id=album_id,
        user=user
    ).values('last_updated').first()
    
@sync_to_async
def bulk_create_albums(album_id,user,album_data):
    return MostListenedAlbum.objects.update_or_create(
        spotify_id=album_id,
        user=user,
        defaults=album_data,
         ) 

async def process_top_tracks(sp, user):
    try:
        top_tracks = await asyncio.to_thread(sp.current_user_top_tracks, limit=50, time_range="medium_term")
        unique_albums = {}
        track_updates = []

        for track in top_tracks["items"]:
            track_id = track["id"]
            album = track["album"]
            release_date = album["release_date"]
            
            if len(release_date) == 4:
                release_date += "-01-01"
            elif len(release_date) == 7:
                release_date += "-01"
            
            album_id = album["id"]
            genres = set()
            artist_names = []
            
            for artist in track["artists"]:
                artist_names.append(artist["name"])
                try:
                    artist_info = await asyncio.to_thread(sp.artist, artist["id"])
                    genres.update(artist_info.get("genres", []))
                except Exception as e:
                    logger.warning(f"Error fetching artistk info for {artist['id']}: {e}")
                    
            genres_list = ", ".join(genres) if genres else "Unknown"
            artist_names_list = ", ".join(artist_names)
            
            if album_id not in unique_albums:
                unique_albums[album_id] = {
                    "spotify_id": album_id,
                    "name": album["name"],
                    "artists": ", ".join(artist["name"] for artist in album["artists"]),
                    "release_date": release_date,
                    "total_tracks": album["total_tracks"],
                }

            track_data = MostListenedSongs(
                spotify_id=track_id,
                user=user,
                name=track["name"],
                artist=artist_names_list,
                album=album["name"],
                release_date=release_date,
                duration_seconds=round(track["duration_ms"]/1000, 2),
                popularity=track["popularity"],
                genres=genres_list,  
            )
            track_updates.append(track_data)
            
        if track_updates:
            await bulk_create_tracks(track_updates)

        for album_id, album_data in unique_albums.items():
            await bulk_create_albums(album_id, user, album_data)
            
    except Exception as e:
        logger.error(f"Error processing tracks: {e}", exc_info=True)
        raise
        
@backoff.on_exception(backoff.expo, requests.RequestException, max_tries=3)
async def fetch_musicbrainz_data(artist_name: str) -> dict:
    """Fetch artist data from MusicBrainz with caching and retries"""
    cache_key = f"musicbrainz_artist_{artist_name}"
    cached_data = cache.get(cache_key)
    if (cached_data):
        return cached_data

    headers = {
        'User-Agent': 'SilleyApp/1.0 (your@email.com)',
        'Accept': 'application/json'
    }
    
    url = "https://musicbrainz.org/ws/2/artist/"
    params = {
        'query': f'artist:{artist_name}',
        'fmt': 'json'
    }
    
    try:
        response = await asyncio.to_thread(
            requests.get,
            url,
            params=params,
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        
        data = response.json()
        if data.get("artists"):
            result = data["artists"][0]
            cache.set(cache_key, result, timeout=3600)
            return result
            
    except requests.RequestException as e:
        logger.error(f"MusicBrainz API error for {artist_name}: {e}")
        
    return None

class DiscogsClient:
    def __init__(self):
        self.oauth = OAuth1Session(
            settings.DISCOGS_CONSUMER_KEY,
            client_secret=settings.DISCOGS_CONSUMER_SECRET,
            resource_owner_key=settings.DISCOGS_ACCESS_TOKEN,
            resource_owner_secret=settings.DISCOGS_ACCESS_TOKEN_SECRET
        )
        self.base_url = "https://api.discogs.com"

    @backoff.on_exception(backoff.expo, requests.RequestException, max_tries=3)
    async def fetch_artist_data(self, artist_name: str) -> dict:
        cache_key = f"discogs_artist_{artist_name}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data

        url = f"{self.base_url}/database/search"
        params = {"q": artist_name, "type": "artist"}
        headers = {"User-Agent": "YourApp/1.0"}

        try:
            response = await asyncio.to_thread(
                self.oauth.get,
                url,
                params=params,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            if data.get("results"):
                result = data["results"][0]
                cache.set(cache_key, result, timeout=3600)
                return result
            logger.info(f"No results found for artist: {artist_name}")
            
        except requests.RequestException as e:
            logger.error(f"Discogs API error: {e}", exc_info=True)
            
        return None

discogs_client = DiscogsClient()

async def fetch_discogs_data(artist_name: str) -> dict:
    return await discogs_client.fetch_artist_data(artist_name)

@backoff.on_exception(backoff.expo, Exception, max_tries=3)
async def fetch_most_popular_song(sp, artist_id: str) -> str:
    """Fetch artist's most popular song with caching"""
    cache_key = f"popular_song_{artist_id}"
    cached_song = cache.get(cache_key)
    if cached_song:
        return cached_song
        
    try:
        top_tracks = await asyncio.to_thread(sp.artist_top_tracks, artist_id)
        if top_tracks and top_tracks.get("tracks"):
            song = top_tracks["tracks"][0]["name"]
            cache.set(cache_key, song, timeout=3600)
            return song
    except Exception as e:
        logger.error(f"Error fetching popular song for {artist_id}: {e}")
    return None

@backoff.on_exception(backoff.expo, Exception, max_tries=3)
async def fetch_related_artists(sp, artist_id: str) -> list:
    """Fetch related artists with caching"""
    cache_key = f"related_artists_{artist_id}"
    cached_artists = cache.get(cache_key)
    if cached_artists:
        return cached_artists
        
    try:
        related = await asyncio.to_thread(sp.artist_related_artists, artist_id)
        if related and related.get("artists"):
            artists = related["artists"]
            cache.set(cache_key, artists, timeout=3600)
            return artists
    except Exception as e:
        logger.error(f"Error fetching related artists for {artist_id}: {e}")
    return []

@backoff.on_exception(backoff.expo, Exception, max_tries=3)
async def get_artist_album_count(sp, artist_name: str) -> int:
    """Get total album count for artist with caching"""
    cache_key = f"album_count_{artist_name}"
    cached_count = cache.get(cache_key)
    if cached_count is not None:
        return cached_count
        
    try:
        results = await asyncio.to_thread(
            sp.search, q=artist_name, type='artist', limit=1
        )
        
        if not results['artists']['items']:
            return 0
            
        artist_id = results['artists']['items'][0]['id']
        albums = await asyncio.to_thread(
            sp.artist_albums, artist_id, limit=1
        )
        count = albums['total']
        cache.set(cache_key, count, timeout=3600)
        return count
    except Exception as e:
        logger.error(f"Error fetching album count for {artist_name}: {e}")
        return 0

@sync_to_async
def get_last_updated(artist_id, user):
    return MostListenedArtist.objects.filter(
        spotify_id=artist_id, 
        user=user
    ).values('last_updated').first()

@sync_to_async
def bulk_create_artists(artists: List[MostListenedArtist]) -> List[MostListenedArtist]:
    """Bulk create or update multiple artist records.
    
    Args:
        artists: List of MostListenedArtist instances to create/update
        
    Returns:
        List of created/updated MostListenedArtist instances
        
    Note:
        Only updates specific fields to avoid overwriting other data
    """
    return MostListenedArtist.objects.bulk_create(
        artists,
        update_fields=["name", "popularity", "genres", "followers"]
    )

async def fetch_artist_metadata(
    sp: Spotify, 
    artist_name: str, 
    artist_id: str
) -> Tuple[Dict, Dict, str, List, int]:
    """Fetch all metadata for an artist concurrently from multiple sources.
    
    Args:
        sp: Authenticated Spotify client instance
        artist_name: Name of the artist to fetch metadata for
        artist_id: Spotify ID of the artist
        
    Returns:
        Tuple containing:
        - MusicBrainz artist data (Dict)
        - Discogs artist data (Dict)  
        - Most popular song name (str)
        - Related artists list (List)
        - Total album count (int)
        
    Note:
        Uses asyncio.gather to fetch data concurrently for better performance
    """
    tasks = [
        # MusicBrainz data for biographical info
        asyncio.to_thread(fetch_musicbrainz_data, artist_name),
        
        # Discogs data for member count and additional metadata
        discogs_client.fetch_artist_data(artist_name),  # Already async
        
        # Spotify data for popularity metrics
        fetch_most_popular_song(sp, artist_id),
        fetch_related_artists(sp, artist_id),
        get_artist_album_count(sp, artist_name)
    ]
    return await asyncio.gather(*tasks)

async def process_artist_years(musicbrainz_data):
    """Fix coroutine issue by awaiting musicbrainz_data if it's a coroutine"""
    if asyncio.iscoroutine(musicbrainz_data):
        musicbrainz_data = await musicbrainz_data
        
    birth_year = None
    debut_year = None
    
    if musicbrainz_data:
        if musicbrainz_data.get("type") == "Person":
            birth_year = (musicbrainz_data.get("life-span", {})
                         .get("begin", "")[:4] or None)
        
        first_release = musicbrainz_data.get("first-release-date", "")[:4]
        first_recording = musicbrainz_data.get("first-recording-date", "")[:4]
        debut_year = first_release or first_recording or None
    
    return birth_year, debut_year

@backoff.on_exception(backoff.expo, Exception, max_tries=3)
async def process_top_artists(sp, user):
    try:
        sp.requests_timeout = 20
        top_artists = await asyncio.to_thread(
            partial(sp.current_user_top_artists, limit=50, time_range="medium_term")
        )
        
        artist_updates = []
        related_artists_to_create = []

        for artist in top_artists["items"]:
            artist_id = artist["id"]
            metadata = await fetch_artist_metadata(sp, artist["name"], artist_id)
            musicbrainz_data, discogs_data, most_popular_song, related_artists, album_count = metadata
            birth_year, debut_year = await process_artist_years(musicbrainz_data)
            
            artist_data = MostListenedArtist(
                spotify_id=artist_id,
                user=user,
                name=artist["name"],
                popularity=artist["popularity"],
                genres=", ".join(artist["genres"]),
                followers=artist["followers"]["total"],
                debut_year=debut_year,
                birth_year=birth_year,
                num_albums=album_count,
                members=len(discogs_data.get("members", [])) if discogs_data else 0,
                country=musicbrainz_data.get("country") if musicbrainz_data else None,
                gender=musicbrainz_data.get("gender") if musicbrainz_data else None,
                most_popular_song=most_popular_song,
            )
            artist_updates.append(artist_data)
            
            if related_artists:
                related_artists_to_create.extend([
                    RelatedArtist(
                        artist=artist_data,
                        related_artist_id=ra["id"],
                        related_artist_name=ra["name"]
                    )
                    for ra in related_artists
                ])

        if artist_updates:
            async with transaction.atomic():
                await bulk_create_artists(artist_updates)
                if related_artists_to_create:
                    await sync_to_async(RelatedArtist.objects.bulk_create)(
                        related_artists_to_create
                    )
                    
    except Exception as e:
        logger.error(f"Error processing artists: {e}", exc_info=True)
        raise