from rest_framework import status, views
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
import aiohttp
import backoff
import requests
from aiohttp import ClientTimeout, TCPConnector, ClientSession
from asgiref.sync import sync_to_async
from django.conf import settings
from django.http import JsonResponse,HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from spotipy import Spotify, SpotifyException, SpotifyOAuth

from .constants import SCOPE
from .models import (MostListenedAlbum, MostListenedArtist, MostListenedSongs,
                     User)
from .utils import (authenticate_user, create_or_update_user, error_response,
                    process_top_artists, process_top_tracks)
from .exceptions import SpotifyException

# Create your views here.


logger = logging.getLogger("spotify")  # Use the custom logger

def home(request):
    return HttpResponse("Welcome to the Django Spotify Integration!")

def spotify_login(request):
    try:
        sp_ouath = SpotifyOAuth(
            client_id = settings.SPOTIFY_CLIENT_ID,
            client_secret= settings.SPOTIFY_CLIENT_SECRET,
            redirect_uri=settings.SPOTIFY_REDIRECT_URI,
            scope= SCOPE
        )
        auth_url = sp_ouath.get_authorize_url()
        return redirect(auth_url)
    except SpotifyException as e:
        logger.error(f"Error during Spotify login: {e}")
        return JsonResponse({"error": str(e)}, status=500)

@sync_to_async
def get_token_info(request, code):
    return authenticate_user(request, code)

@sync_to_async
def create_update_user(token_info):
    """Create or update user with retries."""
    
    @backoff.on_exception(
        backoff.expo,
        (requests.exceptions.ConnectionError, requests.exceptions.Timeout),
        max_tries=3,
        max_time=30
    )
    def create_user_with_retry():
        return create_or_update_user(token_info)
        
    return create_user_with_retry()

async def handle_authentication(request, code: str) -> Optional[Dict]:
    """Handle Spotify OAuth authentication with connection pooling."""
    timeout = ClientTimeout(total=60, connect=20, sock_read=20)
    connector = TCPConnector(
        limit=10,
        force_close=True,
        enable_cleanup_closed=True,
        ssl=False
    )
    
    @backoff.on_exception(
        backoff.expo,
        (SpotifyException, aiohttp.ClientError),
        max_tries=3,
        max_time=60
    )
    async def authenticate(code: str) -> Optional[Dict]:
        try:
            async with aiohttp.ClientSession(
                timeout=timeout,
                connector=connector
            ) as session:
                token_info = await get_token_info(request, code)
                if not token_info:
                    raise SpotifyException(
                        msg="Failed to get token info",
                        code=401
                    )
                return token_info
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise SpotifyException(
                msg=str(e),
                code=500
            )
    
    try:
        return await authenticate(code)
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        return None

async def process_user_data(token_info: Dict, user: User) -> None:
    """Process user's LastFM and Spotify data concurrently."""
    timeout = ClientTimeout(total=60, connect=20, sock_read=20)
    connector = aiohttp.TCPConnector(limit=10, force_close=True)
    
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        sp = Spotify(auth=token_info["access_token"], requests_timeout=60)
        
        # Create tasks
        tasks = [
            process_top_tracks(sp, user),
            process_top_artists(sp, user)
        ]
        
        # Run all tasks concurrently
        await asyncio.gather(*tasks)

async def spotify_callback(request):
    try:
        # Validate request
        code = request.GET.get("code")
        if not code:
            logger.warning("No authorization code provided")
            return error_response("Authorization code required", 400)
            
        # Handle authentication
        token_info = await handle_authentication(request, code)
        if not token_info:
            return error_response("Authentication failed", 401)
            
        # Create/update user
        user = await create_update_user(token_info)
        if not user:
            return error_response("Failed to create/update user", 500)
        
        #check the last update time
        last_updated = await sync_to_async(lambda: user.last_updated)()
        if last_updated and not timezone.is_aware(last_updated):
            last_updated = timezone.make_aware(last_updated)
        
        one_week_ago = timezone.now() - timedelta(weeks=1)
        
        if last_updated and last_updated > one_week_ago:
            logger.info("Data was recently updated; skipping Spotify API calls")
            return JsonResponse({
                 "status": "success",
                 "message": "Data is already up to date. No sync needed.",
                 "user_id": user.spotify_id,
            }, status=200)
            
        # Process user data
        try:
            await process_user_data(token_info, user)
        except Exception as e:
            logger.error(f"Error processing user data: {e}", exc_info=True)
            return error_response("Error processing data")
            
        return JsonResponse({
            "status": "success",
            "message": "Authentication successful. Data fetch completed.",
            "user_id": user.spotify_id,
        }, status=200)
        
    except Exception as e:
        logger.error(f"Callback error: {e}", exc_info=True)
        return error_response(str(e))

