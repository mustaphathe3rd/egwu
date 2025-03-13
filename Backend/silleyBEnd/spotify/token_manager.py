from django.core.cache import cache
from typing import Optional, Dict
import json
import logging

logger = logging.getLogger("spotify")

class TokenManager:
    def __init__(self, prefix: str = "spotify_token"):
        self.prefix = prefix
        self.expiry = 3600  # 1 hour

    def _get_key(self, user_id: str) -> str:
        return f"{self.prefix}:{user_id}"

    def store_token(self, user_id: str, token_info: Dict) -> bool:
        key = self._get_key(user_id)
        try:
            return cache.set(key, json.dumps(token_info), self.expiry)
        except Exception as e:
            logger.error(f"Error storing token for user {user_id}: {e}")
            return False

    def get_token(self, user_id: str) -> Optional[Dict]:
        key = self._get_key(user_id)
        token_data = cache.get(key)
        return json.loads(token_data) if token_data else None

    def delete_token(self, user_id: str) -> bool:
        key = self._get_key(user_id)
        try:
            return cache.delete(key)
        except Exception as e:                     
            logger.error(f"Error deleting token for user {user_id}: {e}")
            return False