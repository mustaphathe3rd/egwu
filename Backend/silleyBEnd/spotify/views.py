from rest_framework import status, views
from rest_framework.decorators import api_view, permission_classes, action
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
from django.core.cache import cache
from django.http import JsonResponse,HttpResponse, HttpResponseRedirect
from rest_framework_simplejwt.settings import api_settings as SIMPLE_JWT
from django.urls import NoReverseMatch, reverse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from spotipy import Spotify, SpotifyException, SpotifyOAuth

from .constants import SCOPE
from .models import (MostListenedAlbum, MostListenedArtist, MostListenedSongs,
                     User, SpotifyToken, SpotifyPlaybackToken)
from .utils import (authenticate_user, create_or_update_user, error_response,
                    process_top_artists, process_top_tracks)
from .exceptions import SpotifyException
import json
from django.views.generic import View

# Create your views here.


logger = logging.getLogger("spotify")  # Use the custom logger

class HomeView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        return Response({"message": "Welcome to the Django Spotify Integration!"}, status=status.HTTP_200_OK)

class SpotifyLoginView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request):
        try:
            sp_ouath = SpotifyOAuth(
                client_id=settings.SPOTIFY_CLIENT_ID,
                client_secret=settings.SPOTIFY_CLIENT_SECRET,
                redirect_uri=settings.SPOTIFY_REDIRECT_URI,
                scope=SCOPE
            )
            auth_url = sp_ouath.get_authorize_url()
            return redirect(auth_url)
        except SpotifyException as e:
            logger.error(f"Error during Spotify login: {e}")
            return Response(
                {"error":str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

@method_decorator(csrf_exempt, name='dispatch')
class SpotifyCallbackView(View):
    permission_classes = [AllowAny]
    
    @sync_to_async
    def get_token_info(self, request, code):
        return authenticate_user(request, code)
    
    @sync_to_async
    def create_update_user(self, token_info):
        @backoff.on_exception(
            backoff.expo,
           (requests.exceptions.ConnectionError, requests.exceptions.Timeout),
            max_tries = 3,
            max_time=30
            )
        def create_user_with_retry():
            return create_or_update_user(token_info)
        
        return create_user_with_retry()
    
    async def handle_authentication(self, request, code: str) -> Optional[Dict]:
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
                    token_info = await self.get_token_info(request, code)
                    if not token_info:
                        raise SpotifyException(
                            msg="Failed to get token info",
                            code = 401
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
        
    async def process_user_data(self, token_info: Dict, user: User) -> None:
        timeout = ClientTimeout(total=60, connect=20, sock_read=20)
        connector = aiohttp.TCPConnector(limit=10, force_close=True)
        
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            sp = Spotify(auth=token_info["access_token"], requests_timeout=60)
            
            tasks = [
                process_top_tracks(sp, user),
                process_top_artists(sp, user)
            ]
            
            await asyncio.gather(*tasks)
    
    async def process_user_data_and_redirect(self, token_info, user):
        logger.info(f"Starting process_user_data_and_redirect for user {user.id}")
        cache_key = f"spotify_processing_{user.id}"
        
        try:
            last_updated = await sync_to_async(lambda: user.last_updated)()
            logger.info(f"User {user.id} last updated: {last_updated}")
            if last_updated and not timezone.is_aware(last_updated):
                last_updated = timezone.make_aware(last_updated)
            
            one_week_ago = timezone.now() - timedelta(weeks=1)
            
            # Check if data is fresh
            if last_updated and last_updated > one_week_ago:
                logger.info(f"User {user.id} data is fresh, skipping processing.")
                
                # =======================================================
                # THE FIX IS HERE: Only save if the flag needs changing
                # =======================================================
                if not user.is_data_processed:
                    user.is_data_processed = True
                    await sync_to_async(user.save)()
                
                # Set cache to complete immediately
                cache.set(cache_key, {
                    'status': 'complete',
                    'redirect_url': 'http://localhost:5173/games/dashboard',
                }, timeout=3600)
                logger.info(f"Cache set to complete for user {user.id} (skipped processing).")
                return

            # If data is old or doesn't exist, process it
            logger.info(f"User {user.id} data is old or missing, starting processing...")
            cache.set(cache_key, {'status': 'processing'}, timeout=3600)
            
            # Process the data
            await self.process_user_data(token_info, user)
            
            # Update user status after successful processing
            user.is_data_processed = True
            user.last_updated = timezone.now() # This explicitly sets the new timestamp
            await sync_to_async(user.save)()
            
            # Update cache with completion status
            cache.set(cache_key, {
                'status': 'complete',
                'redirect_url': 'http://localhost:5173/games/dashboard',
            }, timeout=3600)
            logger.info(f"Data processing completed for user {user.id}")
            
        except Exception as e:
            logger.error(f"Error processing user data: {e}", exc_info=True)
            cache.set(cache_key, {'status': 'error', 'error': str(e)}, timeout=3600)
            raise
    async def get(self, request):
        try:
            # Extract code from query parameters
            code = request.GET.get("code")
            if not code:
                return JsonResponse(
                    {"error": "Authorization code required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Authenticate user and get token info
            token_info = await self.handle_authentication(request, code)
            if not token_info:
                return JsonResponse(
                    {"error": "Authentication failed"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            logger.info(f"Spotify token info: {token_info}")
            
            # Create or update user
            user = await self.create_update_user(token_info)
            if not user:
                return JsonResponse(
                    {"error": "Failed to create/update user"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Store token for games app
            await sync_to_async(SpotifyToken.objects.update_or_create)(
                user=user,
                defaults={
                    'access_token': token_info['access_token'],
                    'refresh_token': token_info.get('refresh_token'),
                    'expires_at': timezone.now() + timedelta(seconds=token_info['expires_in'])
                }
            )
            
            # Generate JWT token for API authentication
            refresh = await sync_to_async(RefreshToken.for_user)(user)
            tokens = {
                'access': str(refresh.access_token),
                'refresh': str(refresh)
            }
            
            # Redirect to loading screen with tokens as URL parameters
            frontend_url = (
                f'http://localhost:5173/loading'
                f'?access_token={tokens["access"]}'
                f'&refresh_token={tokens["refresh"]}'
            )
            logger.debug(f"Redirecting to frontend: {frontend_url}")
            logger.debug(f"Settings tokens: {tokens}")
            
            # Start data processing task
            task = asyncio.create_task(self.process_user_data_and_redirect(token_info, user))
            logger.debug(f"Data processing task created for user {user.id}")
            
            return HttpResponseRedirect(frontend_url)
        
        except Exception as e:
            logger.error(f"Callback error: {e}", exc_info=True)
            return JsonResponse(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class TokenVerifyView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            logger.debug(f"Verify request received. User: {request.user.id if request.user else 'None'}")
            logger.debug(f"Authorization header: {request.headers.get('Authorization', 'None')}")
            # This checks Spotify token validity
            spotify_token = SpotifyToken.objects.get(user=request.user)
            if spotify_token.is_expired():
                logger.debug("Spotify token is expired")
                return Response(
                    {"error": "Token expired"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            response_data = {
                "valid": True,
                "spotify_valid": True,
                "jwt_exp": request.auth.payload['exp'],
                "spotify_exp": spotify_token.expires_at.timestamp()
            }
            logger.debug(f"Verify successful: {response_data}")
            return Response(response_data)
            
        except SpotifyToken.DoesNotExist:
            logger.debug("No Spotify token found for user")
            return Response({
                "valid": True,
                "spotify_valid": False,
                "message": "No spotify token found"
            },
            status = status.HTTP_206_PARTIAL_CONTENT)
        except Exception as e:
            logger.error(f"Verify error: {str(e)}")
            return Response({
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class ProcessingStatusView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            logger.debug(f"Processing status check for user {request.user.id}")
            logger.debug(f"Authorization header: {request.headers.get('Authorization')}")
            user = request.user
            cache_key = f"spotify_processing_{user.id}"
            status_data = cache.get(cache_key)
            
            if not status_data:
                return Response({
                    'status': 'processing'
                })

            logger.debug(f"Cache data found: {status_data}")
            
            # If we have a redirect URL, ensure it's absolute
            if status_data.get('redirect_url'):
                try:
                    status_data['redirect_url'] = 'http://localhost:5173/games/dashboard'
                except NoReverseMatch:
                    # Fallback to hardcoded URL if reverse fails
                    status_data['redirect_url'] = 'http://localhost:5173/games/dashboard'
            
            logger.debug(f"Returning status data: {status_data}")
            return Response(status_data)
            
        except Exception as e:
            logger.error(f"Error checking processing status: {e}")
            return Response(
                {
                    'status': 'error',
                    'error': str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
class PlaybackTokenView(APIView):
    """
    APIView to retrieve a fresh Spotify access token for playback.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            logger.debug(f"SPOTIFY_AUTH_HEADER: Basic {settings.SPOTIFY_AUTH_HEADER}")
            # Add temporary debug logging
            logger.debug(f"Client ID length: {len(settings.EGWU_CLIENT_ID)}")
            logger.debug(f"Client Secret length: {len(settings.EGWU_CLIENT_SECRET)}")
            # Check for existing valid playback token
            playback_token = SpotifyPlaybackToken.objects.filter(
                user=request.user,
                expires_at__gt=timezone.now()
            ).first()
            
            if playback_token:
                return Response({'access_token': playback_token.access_token})
            
            auth_response = requests.post(
                'https://accounts.spotify.com/api/token',
                data={
                    'grant_type': 'refresh_token',
                    'refresh_token': request.user.spotify_token.refresh_token,
                    'scope': 'streaming user-read-playback-state user-modify-playback-state'
                },
                headers={
                    'Authorization': f'Basic {settings.SPOTIFY_AUTH_HEADER}'
                }
            )
            
            if auth_response.status_code != 200:
                logger.error(f"Spotify token refresh failed: {auth_response.text}")
                return Response(
                    {'error': 'Failed to obtain playback token'},
                    status=400
                )
                
            token_data = auth_response.json()
            
            SpotifyPlaybackToken.objects.filter(user=request.user).delete()
            
            SpotifyPlaybackToken.objects.create(
                user=request.user,
                access_token=token_data['access_token'],
                expires_at=timezone.now() + timedelta(seconds=token_data['expires_in'])
            )
            
            return Response({'access_token': token_data['access_token']})
        
        except requests.RequestException as e:
            logger.error(f"Network error during token refresh: {str(e)}")
            return Response(
                {'error': 'Network error during token refresh'},
                status=503
            )
        
        except Exception as e:
            logger.error(f"Unexpected error in PlaybackTokenView: {str(e)}")
            return Response({'error': str(e)}, status=500)
        
class User_Profile(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        return Response({
            'display_name': user.display_name,
            'display_image': user.display_image,
        })
