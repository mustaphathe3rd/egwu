from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication, InvalidToken
from spotify.models import SpotifyToken, User
from rest_framework import exceptions
from rest_framework_simplejwt.exceptions import InvalidToken
import jwt
from django.conf import settings
import logging

logger = logging.getLogger("spotify_games")
# class SpotifyTokenAuthentication(BaseAuthentication):
#     """Proper JWT authentication for game app"""
#     def authenticate(self, request):
#         jwt_token = request.COOKIES.get('access_token')
#         if not jwt_token:
#             return None
        
#         try:
#             payload = jwt.decode(jwt_token, settings.SECRET_KEY, algorithms=['HS256'])
            
#             user = User.objects.get(spotify_id=payload['user_id'])
#             return (user, None)
#         except (jwt.ExpiredSignatureError, jwt.DecodeError, User.DoesNotExist):
#             return None
        
class CompositeAuthentication(JWTAuthentication):
    def authenticate(self, request):
        try:
            # First check if access token exists in cookies
            jwt_token = request.COOKIES.get('access_token')
            logger.debug(f"Cookies present: {request.COOKIES.keys()}")
            
            if not jwt_token:
                logger.debug("No JWT token found in cookies")
                return None
            
            #Manually set the token in the authorization header
            logger.debug("JWT token found in cookies")
            request.META['HTTP_AUTHORIZATION'] = f'Bearer {jwt_token}'
            
            # Attempt JWT authentication
            user_auth = super().authenticate(request)
            if not user_auth:
                logger.debug("JWT authentication failed")
                return None
            
            user, _ = user_auth    
                   
            # Verify Spotify Token
            try:
                spotify_token = SpotifyToken.objects.get(user=user)
                if spotify_token.is_expired():
                    logger.info(f"Refreshing expired token for user {user.id}")
                    if not spotify_token.refresh_token:
                        logger.info(f"Token refresh_token not found for user {user.id}")
                        raise AuthenticationFailed(
                            "Spotify token needs refresh"
                        )
                    spotify_token.refresh()
                    logger.info(f"Token refreshed successfully for user {user.id}")
                return user_auth
            
            except SpotifyToken.DoesNotExist:
                logger.warning(f"No Spotify token found for {user.id}")
                raise AuthenticationFailed("No Spotify token found")
            
        except Exception as e:
            logger.error(f"Authentication error: {e}", exc_info=True)
            return None
            
            
                
           
        
        