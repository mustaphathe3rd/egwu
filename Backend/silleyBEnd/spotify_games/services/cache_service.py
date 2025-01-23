from django.core.cache import cache
from typing import Any, Optional
import hashlib
from functools import wraps
from django.conf import settings
import json
import logging

logger = logging.getLogger("spotify_games")

class GameCacheService:
    def __init__(self, timeout: int = 3600):
        self.cache_timeout = getattr(settings, 'GAME_CACHE_TIMEOUT', 3600) # 1 hour default
    
    def _make_key(self, *args, **kwargs):
        """Create a unique cache key based on arguments."""
        key_parts = [str(arg) for arg in args]
        key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
        key_string = ":".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _get_artist_key(self, artist_id):
        """Generate a cache key for artist data."""
        return f"artist:{artist_id}"
    
    def cache_game_session(self, user_id, game_type, game_data):
        """Cache game session data."""
        key = self._make_key(user_id, game_type)
        cache.set(key, json.dumps(game_data), self.cache_timeout)
        
    def get_game_session(self, user_id, game_type):
        """Retrieve cached game session with error handling."""
        try:
            key = self._make_key(user_id, game_type)
            data = cache.get(key)
            return json.loads(data) if data else None
        except json.JSONDecoderError:
            logger.error("Invalid JSON in cache")
            cache.delete(key)
            return None
    
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
        
    def invalidate_pattern(self, pattern):
        """Invalidate all keys matching a pattern."""
        keys = cache.keys(pattern)
        cache.delete_many(keys)
        
               