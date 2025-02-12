from rest_framework.authentication import BaseAuthentication, SessionAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication, InvalidToken, JWTTokenUserAuthentication
from spotify.models import SpotifyToken, User
from rest_framework import exceptions
from rest_framework_simplejwt.exceptions import InvalidToken
import jwt
from django.conf import settings
import logging

logger = logging.getLogger("spotify_games")

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework import exceptions
import logging

logger = logging.getLogger('spotify')
    
class JWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        logger.debug("Attempting authentication")
        header = self.get_header(request)
        if header is None:
            logger.debug("No header found")
            return None
            

        logger.debug(f"Header: {header}")
        try:
            prefix = self.get_raw_token(header)
            if prefix is None:
                logger.debug("No prefix found")
                return None

            validated_token = self.get_validated_token(prefix)
            logger.debug(f"Successfully authenticated user {validated_token.user.id}, {validated_token}")
            user = self.get_user(validated_token)
            return (user, validated_token)
        except Exception:
            return None

# class CompositeAuthentication(JWTAuthentication, SessionAuthentication):
#     def authenticate(self, request):
#         # Try JWT from cookie first
#         if 'access_token' in request.COOKIES:
#             jwt_token = request.COOKIES['access_token']
#             logger.debug(f"Attempting JWT cookie authentication")
            
#             if not jwt_token:
#                 logger.debug("No JWT token found in cookies")
#             try:
#                 logger.debug("JWT token found in cookies")
#                 request.META['HTTP_AUTHORIZATION'] = f'Bearer {jwt_token}'
                
#                 user_auth = JWTAuthentication.authenticate(self,request)
#                 if user_auth:
#                     logger.debug("JWT authentication successful")
#                     return self._verify_full_auth(user_auth[0])
#             except AuthenticationFailed as e:
#                 logger.warning(f" JWT cookie auth failed: {str(e)}")
                
#         # Fall back to DRF's default JWT handling
#         try:
#             auth_header = get_authorization_header(request)
#             if auth_header:
#                 logger.debug(f"Attempting header JWT authentication")
#                 user_auth = JWTAuthentication.authenticate(self,request)
#                 if user_auth:
#                     return self._verify_full_auth(user_auth[0])
#         except AuthenticationFailed as e:
#             logger.warning(f"Header JWT auth failed: {str(e)}")
            
            
#         # Finally try session auth
#         logger.debug("Falling back to session authentication")
#         session_auth = SessionAuthentication.authenticate(self, request)
#         if session_auth:
#             logger.debug("Session authentication ongoing")
#             return self._verify_full_auth(session_auth[0])
        
#         return None
    
#     def _verify_full_auth(self, user):
#         """Verify Spotify token status without blocking authentication"""
#         try:
#             spotify_token = SpotifyToken.objects.get(user=user)
#             if spotify_token.is_expired():
#                 logger.info(f"Spotify token expired for {user.id}")
#                 if spotify_token.refresh_token:
#                     try:
#                         spotify_token.refresh()
#                     except Exception as refresh_error:
#                         logger.error(f"Token refresh failed: {str(refresh_error)}")
#                 else:
#                     logger.warning(f"No refresh token for {user.id}")
#         except SpotifyToken.DoesNotExist:
#             logger.warning(f"No Spotify token for {user.id}") 
            
#         # Return user even with expired Spotify token
#         return (user, None)           
                
# class CompositeAuthentication(JWTTokenUserAuthentication,SessionAuthentication):
#     def authenticate(self, request):
#         # Check cookie directly
#         if 'access_token' in request.COOKIES:
#             try:
#                 validated_token = self.get_validated_token(
#                     request.COOKIES['access_token']
#                 )
#                 return (self.get_user(validated_token), validated_token)
#             except Exception as e:
#                 logger.error(f"Invalid cookie JWT: {str(e)}")
                
#         # Then check header normally
#         return super().authenticate(request)
# class CompositeAuthentication(JWTAuthentication):
#     def authenticate(self, request):
#         try:
#             # First check if access token exists in cookies
#             jwt_token = request.COOKIES.get('access_token')
#             logger.debug(f"Cookies present: {request.COOKIES.keys()}")
#             logger.debug(f"Access token: {jwt_token}")
#             refresh_token = request.COOKIES.get('refresh_token')
#             logger.debug(f"Refresh token: {refresh_token}")
#             if not jwt_token:
#                 logger.debug("No JWT token found in cookies")
#                 return None
            
#             #Manually set the token in the authorization header
#             logger.debug("JWT token found in cookies")
#             request.META['HTTP_AUTHORIZATION'] = f'Bearer {jwt_token}'
            
#             # Attempt JWT authentication
#             user_auth = super().authenticate(request)
#             logger.debug(f"Final JWT token: {request.META.get('HTTP_AUTHORIZATION')}")
#             if not user_auth:
#                 logger.debug("JWT authentication failed")
#                 return None
            
#             user, _ = user_auth    
                   
#             # Verify Spotify Token
#             try:
#                 spotify_token = SpotifyToken.objects.get(user=user)
#                 if spotify_token.is_expired():
#                     logger.info(f"Refreshing expired token for user {user.id}")
#                     if not spotify_token.refresh_token:
#                         logger.info(f"Token refresh_token not found for user {user.id}")
#                         raise AuthenticationFailed(
#                             "Spotify token needs refresh"
#                         )
#                     spotify_token.refresh()
#                     logger.info(f"Token refreshed successfully for user {user.id}")
#                 return user_auth
            
#             except SpotifyToken.DoesNotExist:
#                 logger.warning(f"No Spotify token found for {user.id}")
#                 raise AuthenticationFailed("No Spotify token found")
            
#         except Exception as e:
#             logger.error(f"Authentication error: {e}", exc_info=True)
#             return None
            
            
                