import asyncio
from .services import ArtistDetailsService, LyricsService 
import time
import logging
from datetime import datetime, timedelta
from functools import partial, wraps
from typing import List, Dict, Tuple, Optional, Any, Callable
from channels.db import database_sync_to_async
import aiohttp
import backoff
import requests
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.http import JsonResponse
from aiohttp import ClientTimeout
from django.utils import timezone
from requests_oauthlib import OAuth1Session
from spotipy import Spotify, SpotifyException, SpotifyOAuth
from requests.exceptions import RequestException, Timeout
from .constants import SCOPE
from .models import (MostListenedAlbum, MostListenedArtist, MostListenedSongs,
                      User)
from .token_manager import TokenManager

from tenacity import retry, stop_after_attempt, wait_exponential
import ssl
import certifi

logger = logging.getLogger("spotify")

token_manager = TokenManager()

ssl_context = ssl.create_default_context(cafile=certifi.where())
class SpotifyBackoffHandler:
    """Handles backoff configuration for spotify API calls"""
    
    @staticmethod
    def get_backoff_decorator():
        return backoff.on_exception(
            backoff.expo,
            (SpotifyException, ConnectionError, TimeoutError),
            max_tries = 5,
            max_time = 60,
            giveup = lambda e: (
                isinstance(e, SpotifyException) and
                e.http_status in [400,401,403,404]
            )
        )
        
async def safe_spotify_request(func: Callable, *args:Any, **kwargs: Any) -> Any:
    """Safely execute Spotify API requests with proper error handling"""
    try:
        return await asyncio.to_thread(func, *args, **kwargs)
    except SpotifyException as e:
        if e.http_status == 429:
            retry_after = int(e.headers.get('Retry-After',5))
            logger.warning(f"Rate limited by Spotify. Waiting {retry_after} seconds")
            await asyncio.sleep(retry_after)
            return await safe_spotify_request(func, *args, **kwargs)
        elif e.http_status in [500, 502, 503, 504]:
            logger.error(f"Spotify server error: {e}")
            raise
        else:
            logger.error(f"Spotify API error: {e}")
            raise
    except ConnectionError as e:
        logger.error(f"Connection error during Spotify request: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during  Spotify request: {e}")
        raise

def authenticate_user(request, code):
    sp_oauth = SpotifyOAuth(
        client_id=settings.SPOTIFY_CLIENT_ID,
        client_secret=settings.SPOTIFY_CLIENT_SECRET,
        redirect_uri=settings.SPOTIFY_REDIRECT_URI,
        scope=SCOPE,
    )

    try:
        # Get token from Redis first
        token_info = token_manager.get_token(request.session.get('user_id'))
        
        if token_info and sp_oauth.is_token_expired(token_info):
            token_info = sp_oauth.refresh_access_token(token_info["refresh_token"])
            if (token_info):
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
        sp = Spotify(auth=token_info["access_token"], requests_timeout=60)
        user_info = sp.current_user()
        spotify_id = user_info['id']
        email = user_info.get('email')
        images = user_info.get('images', [])
        display_image_url = images[0]['url'] if images else None
        logger.debug(f"image url: {display_image_url}")

        # Try to find the user by spotify_id first
        try:
            user = User.objects.get(spotify_id=spotify_id)
            # Update existing user with spotify_id
            updated = False
            for attr in ['display_name', 'email', 'country']:
                new_value = user_info.get(attr, getattr(user, attr))
                if getattr(user, attr) != new_value:
                    setattr(user, attr, new_value)
                    updated = True
                    
            if user.display_image != display_image_url:
                user.display_image = display_image_url
                updated = True
                
            if updated:
                user.save()
            return user
        except User.DoesNotExist:
            # If user not found by spotify_id, check by email
            if email:
                try:
                    user = User.objects.get(email=email)
                    # Update existing user's spotify_id and other fields
                    user.spotify_id = spotify_id
                    user.display_name = user_info.get('display_name', user.display_name)
                    user.country = user_info.get('country', user.country)
                    user.display_image = display_image_url
                    user.save()
                    return user
                except User.DoesNotExist:
                    # Email doesn't exist; create new user
                    pass
            # Create new user
            user = User.objects.create(
                spotify_id=spotify_id,
                display_name=user_info.get('display_name', ''),
                email=email,
                country=user_info.get('country', 'US'),
                display_image=display_image_url
            ),
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
def bulk_create_albums(album_id,user,album_data):
    return MostListenedAlbum.objects.update_or_create(
        spotify_id=album_id,
        user=user,
        defaults=album_data,
         ) 

@sync_to_async
def create_or_update_track(tracks_data: Dict) -> Tuple[MostListenedSongs, bool]:
    return MostListenedSongs.objects.update_or_create(
        spotify_id=tracks_data['spotify_id'],
        user=tracks_data['user'],
        defaults=tracks_data['defaults']
    )

@SpotifyBackoffHandler.get_backoff_decorator()
async def process_top_tracks(sp, user):
    try:
        top_tracks = await safe_spotify_request(sp.current_user_top_tracks, limit=50, time_range="medium_term")
        if not top_tracks or "items" not in top_tracks:
            logger.error("No top tracks data received")
            return
        
        unique_albums = {}
        lyrics_service = LyricsService()
        
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
            
            url = await lyrics_service.search_song(track["name"],
                                                   artist_names[0] if artist_names else None
                                        )
            lyrics = await lyrics_service.get_lyrics(url) if url else None
            
            if album_id not in unique_albums:
                unique_albums[album_id] = {
                    "spotify_id": album_id,
                    "name": album["name"],
                    "artists": ", ".join(artist["name"] for artist in album["artists"]),
                    "release_date": release_date,
                    "total_tracks": album["total_tracks"],
                    "image_url": (
                        album.get("images", [{}])[1].get("url") 
                        if album.get("images") 
                        else None
                    )
                }

            track_data = {
                'spotify_id': track_id,
                'user': user,
                'defaults': {
                    "name": track["name"],
                    "artist": artist_names_list,
                    "album": album["name"],
                    "release_date": release_date,
                    "duration_seconds": convert_ms_to_seconds(track.get("duration_ms", 0)),
                    "popularity": track["popularity"],
                    "genres": genres_list,
                    "lyrics": lyrics,
                    "image_url": (album.get("images", [{}])[1].get("url") 
                        if album.get("images") 
                        else None 
                    ),
                    "track_uri": f"spotify:track:{track_id}"
                }
            }
         
            await create_or_update_track(track_data)

        for album_id, album_data in unique_albums.items():
            await bulk_create_albums(album_id, user, album_data)
            
    except Exception as e:
        logger.error(f"Error processing tracks: {e}", exc_info=True)
        raise
@backoff.on_exception(
    backoff.expo,
    (RequestException,Timeout),
    max_tries=3,
    max_time=30
)
async def fetch_musicbrainz_data(artist_name: str) -> dict:
    """Fetch artist data from MusicBrainz with caching and retries"""
    if not artist_name:
        return None
        
    headers = {
        'User-Agent': 'SilleyApp/1.0 (your@email.com)',
        'Accept': 'application/json'
    }
    
    url = "https://musicbrainz.org/ws/2/artist/"
    params = {
        'query': f'artist:{artist_name}',
        'fmt': 'json',
        'limit': 1,  # Only need first result
        'inc': 'aliases+tags'  # Include essential data only
    }
    
    try:
        async with aiohttp.ClientSession(
            headers=headers,
            timeout=ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(ssl=ssl_context)
        )as session:
            async with session.get(url, params=params)as response:
                response.raise_for_status()
                data = await response.json()
                return data.get("artists",[{}])[0] if data.get("artists") else None
            
    except asyncio.TimeoutError as e:
        logger.error(f"MusicBrainz API timeout for {artist_name}: {e}")
    except Exception as e:
        logger.error(f"MusicBrainz API error for {artist_name}: {e}")
        
    return None

@SpotifyBackoffHandler.get_backoff_decorator()
async def fetch_most_popular_song(sp, artist_id: str) -> Optional[Tuple[str, str]]:
    """Fetch artist's most popular song details.
    
    Args: 
        sp: Spotify client instance
        artist_id: Spotify artist ID
        
    Returns:
        Tuple containing:
        - Song name (str)
        - Song ID (str)
        or None if fetching fails
    """

    try:
        top_tracks = await safe_spotify_request(sp.artist_top_tracks, artist_id)
        
        if top_tracks and top_tracks.get("tracks"):
            top_track = top_tracks["tracks"][0]
            return (
                top_track["name"],
                top_track["id"],
            )
        
        logger.warning(f"No tracks found for artist {artist_id}")
        return None
    
    except Exception as e:
        logger.error(f"Error fetching popular song for {artist_id}: {e}")
    return None


@SpotifyBackoffHandler.get_backoff_decorator()
async def get_artist_album_count(sp, artist_name: str) -> int:
    """Get total album count for artist with caching"""
         
    try:
        results = await safe_spotify_request(
            sp.search, q=artist_name, type='artist', limit=1
        )
        
        if not results['artists']['items']:
            return 0
            
        artist_id = results['artists']['items'][0]['id']
        albums = await asyncio.to_thread(
            sp.artist_albums, artist_id,album_type='album', limit=1
        )
        logger.debug(f"Albums response for {artist_name}: {albums}")
        count = albums['total']
        
        return count
    except Exception as e:
        logger.error(f"Error fetching album count for {artist_name}: {e}")
        return 0

async def fetch_artist_metadata(
    sp: Spotify,
    artist_name: str,
    artist_id: str
) -> Optional[Tuple[Dict, Tuple[int, Optional[str]], Tuple[str, str], int]]:
    """
    Fetch all metadata for an artist concurrently from multiple sources.
    
    Returns:
        Tuple containing:
        - MusicBrainz artist data (Dict)
        - Discogs artist data (Tuple[int, Optional[str]]) - (member_count, debut_year)
        - Song details (Tuple[str, str, str, str]) - (name, id, preview_url, spotify_url)
        - Total album count (int)
        Or None if fetching fails
    """
    try:
        # Create and execute tasks
        musicbrainz_task = fetch_musicbrainz_data(artist_name)
        discogs_task = get_artist_info(artist_name)
        popular_song_task = fetch_most_popular_song(sp, artist_id)
        album_count_task = get_artist_album_count(sp, artist_name)
        
        results = await asyncio.gather(
            musicbrainz_task,
            discogs_task,
            popular_song_task,
            album_count_task,
            return_exceptions=True
        )
        
        # Check for exceptions in results
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Task {idx} failed with error: {result}")
                return None
        
        # Unpack results
        musicbrainz_data, discogs_tuple, song_details, album_count = results
        
        # Verify discogs_tuple structure
        if not isinstance(discogs_tuple, tuple) or len(discogs_tuple) != 2:
            logger.error(f"Invalid discogs data structure for {artist_name}")
            return None
        
        # Verify song_details structure
        if song_details and not isinstance(song_details, tuple):
            logger.error(f"Invalid song details structure for {artist_name}")
            return None
            
        return (
            musicbrainz_data,
            discogs_tuple,  # Keep as tuple, will unpack later
            song_details,
            album_count
        )
        
    except Exception as e:
        logger.error(f"Error in fetch_artist_metadata for {artist_name}: {e}", exc_info=True)
        return None
async def process_artist_years(musicbrainz_data):
    """Fix coroutine issue by awaiting musicbrainz_data if it's a coroutine"""
    if asyncio.iscoroutine(musicbrainz_data):
        musicbrainz_data = await musicbrainz_data
        
    birth_year = None

    if musicbrainz_data:
        if musicbrainz_data.get("type") == "Person":
            birth_year = (musicbrainz_data.get("life-span", {})
                         .get("begin", "")[:4] or None)
    
    return birth_year

@sync_to_async
def create_or_update_artist(artist_data: Dict):
    """Create or update artist with sync_to_async wrapper."""
    logger.debug("Entering create_or_update_artist")
    logger.debug(f"Artist data:{artist_data['spotify_id']}")
    
    return MostListenedArtist.objects.update_or_create(
            spotify_id = artist_data['spotify_id'],
            user = artist_data['user'],
            defaults=artist_data['defaults'],
        )
           
@SpotifyBackoffHandler.get_backoff_decorator()
async def process_top_artists(sp, user):
    try:
        top_artists = await safe_spotify_request(
            sp.current_user_top_artists,
            limit=50,
            time_range="medium_term"
        )
        
        if not top_artists or "items" not in top_artists:
            logger.error("No top artists data received")
            return
        
        for artist in top_artists["items"]:
            try:
                artist_id = artist["id"]
                logger.debug(f"Processing artist: {artist_id}")
                
                metadata = await fetch_artist_metadata(sp, artist["name"], artist_id)

                if not metadata or not isinstance(metadata, tuple) or len(metadata) < 4:
                        logger.error(f"Invalid metadata for artist {artist['name']}: {metadata}")
                        continue
                logger.debug(f"fetch_artist_metadata returned: {metadata}")

                
                try:
                    musicbrainz_data, discogs_data, song_details, album_count = metadata
                    
                    # if not isinstance(discogs_data, (tuple, list)) or len(discogs_data) != 2:
                    #     raise ValueError(f"Invalid discogs_data: {discogs_data}")
                    # logger.debug(f"fetch returned:{musicbrainz_data}|| {discogs_data}|| {most_popular_song}|| {album_count}")
                    
                    members_count, debut_year = discogs_data
                    
                     # Initialize song variables with defaults
                    most_popular_song = None
                    most_popular_song_id = None

                     # Unpack song details
                    if song_details and isinstance(song_details, tuple):
                        most_popular_song = song_details[0]
                        most_popular_song_id = song_details[1]
                        
                        logger.debug(f"Song details unpacked: {most_popular_song} (ID: {most_popular_song_id})")    
                    else:
                        logger.warning(f"Invalid song details for artist {artist['name']: {song_details}}")
                        most_popular_song = most_popular_song_id = None
                    
                    logger.debug(f"fetch returned: musicbrainz={musicbrainz_data}, discogs={discogs_data}, song={most_popular_song}, albums={album_count}")                   
                
                except ValueError as e:
                    logger.error(f"Error unpacking metadata for artist {artist['name']}: {e}")
                    continue
                
                birth_year = await process_artist_years(musicbrainz_data) 
                logger.debug(f"birth_year: {birth_year}")
                
                try:
                    biography = await get_artist_bio(artist["name"])
                    logger.debug(f"biography type:{type(biography)}")
                    logger.debug(f"Biography fetched: {biography}")
                except Exception as e:
                    logger.error(f"Error getting biography for {artist['name']}: {e}")
                    biography = None

                most_popular_track_uri = f"spotify:track:{most_popular_song_id}" if most_popular_song_id else None
                
                artist_data = {
                    'spotify_id': artist_id,
                    'user': user,
                    'defaults': {
                        "name": artist["name"],
                        "popularity": artist["popularity"],
                        "genres": ", ".join(artist["genres"]),
                        "followers": artist["followers"]["total"],
                        "debut_year": debut_year,
                        "birth_year": birth_year,
                        "num_albums": album_count,
                        "members": members_count,
                        "country": musicbrainz_data.get("country") if musicbrainz_data else None,
                        "gender": musicbrainz_data.get("gender") if musicbrainz_data else None,
                        "most_popular_song": most_popular_song,
                        "most_popular_song_id": most_popular_song_id,
                        "most_popular_track_uri": most_popular_track_uri,
                        "biography":biography,
                        "image_url": (
                        artist.get("images", [{}])[1].get("url") 
                        if artist.get("images") 
                        else None
                    )   
                    }
                }
                try:
                    logger.debug(f"Before create_or_update_artist call for {artist_id}")
                    logger.debug(f"Type of create_or_update_artist: {type(create_or_update_artist)}")
                    
                    
                    await create_or_update_artist(artist_data)
                    
                except Exception as e:
                    logger.error(
                        f"Database error for artist {artist_id}: {str(e)}",
                        exc_info=True,
                        stack_info=True
                    )
                    continue
                
            except Exception as e:
                logger.error(f"Error updating artist {artist.get('id', 'unknown')}: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Error processing top artists: {e}", exc_info=True)
        raise
    
async def fetch_discogs_data(url: str, headers: Dict, params: Optional[Dict] = None) -> Optional[Dict]:
    """Async helper function to fetch data from Discogs API with SSL verification."""
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    conn = aiohttp.TCPConnector(ssl=ssl_context)
    
    async with aiohttp.ClientSession(connector=conn) as session:
        try:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    return await response.json()
                logger.error(f"Error fetching data from {url}: {response.status}")
                return None
        except Exception as e:
            logger.error(f"Request error for {url}: {e}")
            return None

@backoff.on_exception(backoff.expo, Exception, max_tries=3)
async def get_artist_info(artist_name: str) -> Tuple[Optional[int], Optional[str]]:
    """Async function to fetch artist members count and debut year."""
    BASE_URL = "https://api.discogs.com/"
    headers = {
        "Authorization": f"Discogs token={settings.DISCOGS_TOKEN}",
        "User-Agent": "stats_mine/1.0",
    }
    
    try:
        search_data = await fetch_discogs_data(
            f"{BASE_URL}database/search",
            headers=headers,
            params={"q": artist_name, "type": "artist"}
        )
        
        if not search_data or not search_data.get("results"):
            return 0, None
            
        specific_artist = next(
            (r for r in search_data["results"] 
             if r.get("title", "").lower() == artist_name.lower()),
            None
        )
        
        if not specific_artist:
            return 0, None
            
        artist_data = await fetch_discogs_data(
            specific_artist["resource_url"],
            headers
        )
        
        if not artist_data:
            return 0, None
            
        member_count = len(artist_data.get("members", []))
        
        releases_data = await fetch_discogs_data(
            artist_data.get("releases_url"),
            headers,
            params={"sort": "year", "sort_order": "asc"}
        )
        
        debut_year = None
        if releases_data and releases_data.get("releases"):
            debut_year = releases_data["releases"][0].get("year")
            
        return member_count, debut_year
        
    except Exception as e:
        logger.error(f"Error getting artist info for {artist_name}: {e}")
        return 0, None

def convert_ms_to_seconds(ms: int) -> float:
    if not isinstance(ms, (int, float)):
        raise ValueError("Duration must be a number")
    return round(float(ms)/1000, 2)

def rate_limit_handler() -> Callable:
    """Decorator to handle rate limiting for Discogs API."""
    def decorator(func: Callable) -> Callable:
        last_request_time = 0
        min_request_interval = 1.0  # 1 second between requests
        
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            nonlocal last_request_time
            
            # Check if we need to wait
            now = time.time()
            time_since_last = now - last_request_time
            if time_since_last < min_request_interval:
                await asyncio.sleep(min_request_interval - time_since_last)
            
            try:
                response = await func(*args, **kwargs)
                last_request_time = time.time()
                return response
                
            except Exception as e:
                if '429' in str(e):
                    retry_after = int(e.response.headers.get('Retry-After', 10))
                    logger.warning(f"Rate limited. Waiting {retry_after} seconds")
                    await asyncio.sleep(retry_after)
                    return await wrapper(*args, **kwargs)
                raise
                
        return wrapper
    return decorator

async def get_artist_bio(artist_name: str) -> str:
    service = ArtistDetailsService()
    biography = await service.get_artist_details(artist_name)
    return biography