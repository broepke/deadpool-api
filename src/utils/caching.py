"""Caching utilities for the application."""
import time
from typing import Any, Callable, Dict, Optional, TypeVar, Awaitable

T = TypeVar('T')

class Cache:
    """Simple in-memory cache with TTL."""
    
    def __init__(self, ttl: int = 300):  # 5 minute default TTL
        self._cache: Dict[str, tuple[Any, float]] = {}
        self.ttl = ttl
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache if it exists and hasn't expired."""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            else:
                # Clean up expired entry
                del self._cache[key]
        return None
    
    def set(self, key: str, value: Any) -> None:
        """Set a value in the cache with current timestamp."""
        self._cache[key] = (value, time.time())
    
    def delete(self, key: str) -> None:
        """Remove a value from the cache."""
        if key in self._cache:
            del self._cache[key]
    
    async def get_or_compute(
        self,
        key: str,
        compute_func: Callable[[], Awaitable[T]]
    ) -> T:
        """Get from cache or compute and cache the value."""
        cached_value = self.get(key)
        if cached_value is not None:
            return cached_value
        
        value = await compute_func()
        self.set(key, value)
        return value

# Global cache instance
reporting_cache = Cache()