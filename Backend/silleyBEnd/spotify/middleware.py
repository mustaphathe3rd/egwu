from django.utils import timezone
from .models import SpotifyToken

class SpotifyTokenMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                token = SpotifyToken.objects.get(user=request.user)
                if token.is_expired():
                    token.refresh()
            except SpotifyToken.DoesNotExist:
                pass
        return self.get_response(request)