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
from django.http import JsonResponse,HttpResponse, HttpResponseRedirect
from django.urls import NoReverseMatch, reverse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from spotipy import Spotify, SpotifyException, SpotifyOAuth

from .constants import SCOPE
from .models import (MostListenedAlbum, MostListenedArtist, MostListenedSongs,
                     User, SpotifyToken)
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
            
    async def get(self, request):
        try:
            # Extract code from query parameters
            code = request.GET.get("code")
            if not code:
                return JsonResponse(
                    {"error": "Authorization code required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            token_info = await self.handle_authentication(request, code)
            if not token_info:
                return JsonResponse(
                    {"error": "Authentication failed"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
                
            user = await self.create_update_user(token_info)
            if not user:
                return JsonResponse(
                    {"error": "Failed to create/update user"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
            # Store token for games app
            await sync_to_async(SpotifyToken.objects.update_or_create)(
                user=user,
                defaults = {
                'access_token':token_info['access_token'],
                'refresh_token':token_info.get('refresh_token'),
                'expires_at':timezone.now() + timedelta(seconds=token_info['expires_in'])
                }            
            )
            
            # Generate JWT token for API authentication
            refresh = await sync_to_async(RefreshToken.for_user)(user)
            access_token = str(refresh.access_token)
            refresh_token = str(refresh)
            
            # Redirect to the game dashboard
            #redirect_url = reverse('spotify_games:dashboard')
            redirect_url = await sync_to_async(reverse)('spotify_games:dashboard') # Ensure correct URL name
            response = HttpResponseRedirect(redirect_url)
            
            # Set JWT tokens in HTTP-only cookies
            response.set_cookie(
                'access_token',
                access_token,
                max_age=3600,
                httponly=True,
                secure=settings.SESSION_COOKIE_SECURE,
                samesite='Lax',
                domain=settings.SESSION_COOKIE_DOMAIN,
                path='/'
            )
            response.set_cookie(
               'refresh_token',
                refresh_token,
                max_age=86400,
                httponly=True,
                secure=settings.SESSION_COOKIE_SECURE,
                samesite='Lax',
                domain=settings.SESSION_COOKIE_DOMAIN,
                path = '/'
            )
            
            last_updated = await sync_to_async(lambda: user.last_updated)()
            if last_updated and not timezone.is_aware(last_updated):
                last_updated = timezone.make_aware(last_updated)
                
            one_week_ago = timezone.now() - timedelta(weeks=1)
            
            if last_updated and last_updated <= one_week_ago:
                try:
                    await self.process_user_data(token_info, user)
                    # Optional: Update last_updated after processing
                    await sync_to_async (user.save)()
                except Exception as e:
                    logger.error(f"Error processing user data: {e}", exc_info=True)
            
            return response
        
        except Exception as e:
            logger.error(f"Callback error: {e}", exc_info=True)
            return  JsonResponse(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
class TokenVerifyView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            # This checks Spotify token validity
            spotify_token = SpotifyToken.objects.get(user=request.user)
            if spotify_token.is_expired():
                return Response(
                    {"error": "Token expired"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            # Check JWT validity (implicit via IsAuthennticated)
            return Response({"valid": True,
                             "spotify_valid": True,
                             "jwt_exp": request.auth.payload['exp'],
                             "spotify_exp": spotify_token.expires_at.timestamp()
                             })
            
        except SpotifyToken.DoesNotExist:
            return Response({
                "valid": True,
                "spotify_valid": False,
                "message": "No spotify token found"
            },
            status = status.HTTP_206_PARTIAL_CONTENT)