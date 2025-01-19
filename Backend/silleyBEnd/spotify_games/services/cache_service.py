from django.core.cache import cache
from typing import Any, Optional
from django.conf import settings
import json

class GameCacheService:
    def __init__(self, timeout: int = 3600):
        self.cache_timeout = getattr(settings, 'GAME_CACHE_TIMEOUT', 3600) # 1 hour default
    
    def _get_user_game_key(self, user_id, game_type):
        """Generate a cache key for user-specific game data."""
        return f"game:{user_id}:{game_type}"
    
    def _get_artist_key(self, artist_id):
        """Generate a cache key for artist data."""
        return f"artist:{artist_id}"
    
    def cache_game_session(self, user_id, game_type, game_data):
        """Cache game session data."""
        key = self._get_user_game_key(user_id, game_type)
        cache.set(key, json.dumps(game_data), self.cache_timeout)
        
    def get_game_session(self, user_id, game_type):
        """Retrieve cached game session data."""
        key = self._get_user_game_key(user_id, game_type)
        data = cache.get(key)
        return json.loads(data) if data else None
    
    def cache_artist_data(self, artist_id, artist_data):
        """Cache processed artist data."""
        key = self._get_artist_key(artist_id)
        cache.set(key, json.dumps(artist_data), self.cache_timeout)
        
    def get_artist_data(self, artist_id):
        """Retrieve cached artist data."""
        key = self._get_artist_key(artist_id)
        data = cache.get(key)
        return json.loads(data) if data else None
    
    def clear_user_game_cache(self, user_id):
        """Clear all game-related cache for a user."""
        pattern = f"game: {user_id}:*"
        keys = cache.keys(pattern)
        cache.delete_many(keys)
        
               