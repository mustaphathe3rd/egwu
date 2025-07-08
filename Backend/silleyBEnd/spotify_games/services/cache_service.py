from django.core.cache import cache
from typing import Any, Optional
import hashlib
from functools import wraps
from django.conf import settings
import json
import logging

logger = logging.getLogger("spotify_games")

class GameCacheService:
    def __init__(self, timeout: int = 30):
        self.cache_timeout = getattr(settings, 'GAME_CACHE_TIMEOUT', 60) # 1 hour default
    
    def _make_key(self, session_id, game_type):
        return f"active-session:{session_id}:{game_type}"
    
    def _get_artist_key(self, artist_id):
        """Generate a cache key for artist data."""
        return f"artist:{artist_id}"
    
    def cache_game_session(self, session_id, game_type, game_data, timeout=None):
        """Cache game session data."""
        key = self._make_key(session_id, game_type)
        logger.debug(f"Caching game state for user {session_id} with key: {key}")
        logger.debug(f"Game state to cache: {game_data}")
        timeout = timeout or self.cache_timeout
        cache.set(key, json.dumps(game_data), self.cache_timeout)
        
    def get_game_session(self, session_id, game_type):
        """Retrieve cached game session with error handling."""
        try:
            key = self._make_key(session_id, game_type)
            logger.debug(f"Retrieving game state for user {session_id} with key: {key}")
            data = cache.get(key)
            logger.debug(f"Game state: {data}")
            return json.loads(data) if data else None
        except json.JSONDecoderError:
            logger.error("Invalid JSON in cache")
            cache.delete(key)
            return None
    
    
    def clear_game_session(self, session_id, game_type):
        """Clear the cached game session data."""
        key = self._make_key(session_id, game_type)
        logger.debug(f"Clearing game state for user {session_id} with key: {key}")
        cache.delete(key)

    
    def cache_artist_data(self, artist_id, artist_data):
        """Cache processed artist data."""
        key = self._get_artist_key(artist_id)
        cache.set(key, json.dumps(artist_data), self.cache_timeout)
        
    def get_artist_data(self, artist_id):
        """Retrieve cached artist data."""
        key = self._get_artist_key(artist_id)
        data = cache.get(key)
        logger.debug(f'Artist data: {data}')
        return json.loads(data) if data else None
    

        
    def invalidate_pattern(self, pattern):
        """Invalidate all keys matching a pattern."""
        keys = cache.keys(pattern)
        cache.delete_many(keys)
        
    def clear_user_games(self, user_id):
        """
        Clear all game caches for a user - this would require a more advanced
        caching system that tracks user's game sessions
        """
        # This is a simplified version - in a real implementation, you'd need
        # to store keys by user somewhere or use a cable backend that supports pattern matching
        pass
               