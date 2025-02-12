from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
import logging
from asgiref.sync import sync_to_async

logger = logging.getLogger("spotify_games")

# class JWTTokenRefreshMiddleware(MiddlewareMixin):
#     async def call(self, request):
#         if not request.path.startswith('/games/'):
#             return await self.get_response(request)

#         refresh_token = request.COOKIES.get('refresh_token')
#         if not refresh_token:
#             return None

#         access_token = request.COOKIES.get('access_token')

#         if not access_token:
#             try:
#                 # Attempt to refresh using the refresh token
#                 refresh = RefreshToken(refresh_token)
#                 access_token = str(refresh.access_token)

#                 # Get the async response
#                 response = await self.get_response(request)

#                 # Set the new access token cookie
#                 response.set_cookie(
#                     'access_token',
#                     access_token,
#                     max_age=3600,
#                     httponly=True,
#                     secure=settings.SESSION_COOKIE_SECURE,
#                     samesite = 'Lax',
#                     domain=settings.SESSION_COOKIE_DOMAIN,
#                     path = '/')
#                 return response

#             except Exception as e:
#                 logger.error(f"Token refresh middleware error: {e}")
#                 return await self.get_response(request)

#         # Pass through if no refresh needed
#         return await self.get_response(request)

# spotify_games/middleware.py
class JWTTokenRefreshMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if not request.path.startswith('/games/'):
            return None
            
        try:
            refresh_token = request.COOKIES.get('refresh_token')
            access_token = request.COOKIES.get('access_token')
            
            if not access_token and refresh_token:
                # Only refresh if we have refresh token but no access token
                refresh = RefreshToken(refresh_token)
                new_access_token = str(refresh.access_token)
                
                response = self.get_response(request)
                response.set_cookie(
                    'access_token',
                    new_access_token,
                    max_age=3600,
                    httponly=True,
                    secure=settings.SESSION_COOKIE_SECURE,
                    samesite='Lax',
                    path='/',
                    domain=settings.SESSION_COOKIE_DOMAIN if settings.SESSION_COOKIE_DOMAIN else None
                )
                return response
                
            return None
            
        except Exception as e:
            logger.error(f"Token refresh middleware error: {e}")
            return None