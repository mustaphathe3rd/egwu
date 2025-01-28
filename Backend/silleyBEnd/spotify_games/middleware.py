from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
import logging

logger = logging.getLogger("spotify_games")

class JWTTokenRefreshMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if not request.path.startswith('/games/'):
            return None
        
        try:
            refresh_token = request.COOKIES.get('refresh_token')
            if not refresh_token:
                return None
            
            access_token = request.COOKIES.get('access_token')
            if not access_token:
                # Attempt to refresh using the refresh token
                refresh = RefreshToken(refresh_token)
                access_token = str(refresh.access_token)
                
                response = self.get_response(request)
                response.set_cookie(
                    'access_token',
                    access_token,
                    max_age=3600,
                    httponly=True,
                    secure=settings.SESSION_COOKIE_SECURE,
                    samesite = 'Lax',
                    path = '/'
                )
                return response
        
        except Exception as e:
            logger.error(f"Token refresh middleware error: {e}")
            return None