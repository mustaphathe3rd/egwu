from django.core.cache import cache
from typing import Any, Optional

class CacheService:
    def __init__(self, timeout: int = 3600):
        self.timeout = timeout
    
    def get(self, key:str) -> Optional[Any]:
        return cache.get(key)
    
    def set(self, key: str, value: Any, timeout: Optional[int] = None) -> None:
        cache.set(key, value, timeout or self.timeout)
        
    def delete(self, key:str) -> None:
        cache.delete(key)
        
    def clear(self) -> None:
        cache.clear()
        
               