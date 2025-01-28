from django.shortcuts import redirect
from django.urls import reverse

class SpotifyAuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        if request.path.startswith('/games'):
            if not request.user.is_authenticated:
                return redirect('spotify_login')
            
            try:
                spotify_token =  request.user.spotify_token
                if spotify_token.is_expired():
                    return redirect('spotify_refresh_token')
            except AttributeError:
                return redirect('spotify_login')
            
        response = self.get_response(request)
        return response