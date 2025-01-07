from django.shortcuts import render
from asgiref.sync import sync_to_async
import requests
import logging
from spotipy import Spotify, SpotifyOAuth, SpotifyException
from django.http import JsonResponse
from .models import MostListenedArtist, MostListenedAlbum, User, MostListenedSongs
from django.conf import settings
from django.shortcuts import redirect
import asyncio
import aiohttp
from .constants import SCOPE
from .utils import authenticate_user, error_response, create_or_update_user, process_top_artists, process_top_tracks
from datetime import datetime, timedelta
from django.utils import timezone
import backoff
from .services import GlobalSpotifyService,SpotifyService
from aiohttp import ClientTimeout
# Create your views here.


logger = logging.getLogger("spotify")  # Use the custom logger


@sync_to_async
def get_token_info(request, code):
    return authenticate_user(request, code)

@sync_to_async
def create_update_user(token_info):
    return create_or_update_user(token_info)

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

async def spotify_callback(request):
    try:
        code = request.GET.get("code")
        if not code:
            logger.warning("No authorization code provided")
            return error_response("No ai=uthorization code provided.", 400)
        
        #Retry authentication with backoff
        @backoff.on_exception(
            backoff.expo,
            (SpotifyException,aiohttp.ClientError),
            max_tries=3
        )
        async def authenticate(request, code):
            return await get_token_info(request,code)

        token_info = await authenticate(request,code)
        if not token_info:
            logger.warning("Authentication failed, token info not retrieved")
            return error_response("Authentication failed",401)
        logger.info("Token info retrieved")

        user = await create_update_user(token_info)
        if not user:
            return error_response("Failed to create/update user",500)
        
        #check the last update time
        """ last_updated = await sync_to_async(lambda: user.last_updated)()
        if last_updated and not timezone.is_aware(last_updated):
            last_updated = timezone.make_aware(last_updated)
        
        one_week_ago = timezone.now() - timedelta(weeks=1)
        
        if last_updated and last_updated > one_week_ago:
            logger.info("Data was recently updated; skipping Spotify API calls")
            return JsonResponse({
                "status": "success",
                "message": "Data is already up to date. No sync needed.",
                "user_id": user.spotify_id,
            }, status=200) """
            
        #Increase timeout and add connection pooling
        timeout = ClientTimeout(total=60, connect=20,sock_read=20)
        connector = aiohttp.TCPConnector(limit=10, force_close=True)
        global_spotify_service = GlobalSpotifyService()
        spotify_service = SpotifyService(user.spotify_id)
    
            
        async with aiohttp.ClientSession(
            timeout=timeout,
            connector=connector
            ) as session:
            sp = Spotify(auth=token_info["access_token"],requests_timeout=60)
            
            try:
                #Run these tasks concurrently   
                await asyncio.gather(
                        # Process top tracks
                    process_top_tracks(sp, user),
                        # Process top artists
                    process_top_artists(sp, user),
                    
                    global_spotify_service.get_global_top_tracks(limit=50),
                    spotify_service.get_top_tracks_by_country(limit=50)
                    )
            except Exception as e:
                logger.error(f"Error processing top tracks and artists: {e}", exc_info=True)
                return error_response("Error Processing Spotify data")
            
        return JsonResponse({
            "status": "success",
            "message": "Authentication successful. Data sync started.",
            "user_id": user.spotify_id,
        },status=200)
    
    except Exception as e:
        logger.error(f"Callback error: {e}", exc_info=True)
        return error_response(str(e))

