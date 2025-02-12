from django.utils import timezone
from .models import SpotifyToken
from django.utils.decorators import sync_and_async_middleware
import logging

logger = logging.getLogger("spotify")
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