from django.apps import AppConfig
from django.conf import settings
import os


class SpotifyGamesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'spotify_games'

    # def ready(self):
    #     """Verify template directory structure on app startup"""
    #     required_dirs = [
    #         os.path.join(settings.BASE_DIR, 'templates'),
    #         os.path.join(settings.BASE_DIR, 'templates', 'spotify_games'),
    #         os.path.join(settings.BASE_DIR, 'spotify_games', 'templates'),
    #     ]
        
    #     for directory in required_dirs:
    #         if not os.path.exists(directory):
    #             os.makedirs(directory)
    #             print(f"Created missing template directory: {directory}")