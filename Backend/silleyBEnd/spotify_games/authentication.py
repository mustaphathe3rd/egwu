from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from spotify.models import User
import jwt
from django.conf import settings


class SpotifyTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return None
        
        try:
            token = auth_header.split(' ')[1]
            payload = jwt.decode(
                token, 
                settings.JWT_SECRET_KEY,
                algorithms=['HS256'],
                options={'verify_exp': True}
            )
            user = User.objects.get(spotify_id=payload['spotify_id'])
            return (user, None)
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed('Token has expired')
        except (jwt.InvalidTokenError, User.DoesNotExist, IndexError):
            raise AuthenticationFailed('Invalid authentication token')