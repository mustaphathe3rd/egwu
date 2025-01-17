from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from spotify.models import User
import jwt

class SpotifyTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return None
        
        try:
            #Extract token
            token = auth_header.split(' ')[1]
            #verify token and get user data
            payload = jwt.decode(token, 'your-secret-key', algorithms=['HS256'])
            user = User.objects.get(spotify_id=payload['spotify_id'])
            return(user, None)
        except (jwt.InvalidTokenError, User.DoesNotExist):
            raise AuthenticationFailed('Invalid authentication token')
        