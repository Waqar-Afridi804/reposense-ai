import threading
import time
from typing import Any


class TTLCache:
    """Thread-safe bounded in-memory TTL cache for per-user and short-lived lookups."""

    def __init__(self, max_size: int = 512, default_ttl: float = 60.0):
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        now = time.monotonic()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if now >= expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        expires_at = time.monotonic() + (ttl if ttl is not None else self._default_ttl)
        with self._lock:
            if len(self._store) >= self._max_size and key not in self._store:
                # Evict expired entries first, then oldest entry
                now = time.monotonic()
                expired = [k for k, (exp, _) in self._store.items() if now >= exp]
                for k in expired:
                    del self._store[k]
                if len(self._store) >= self._max_size:
                    oldest_key = next(iter(self._store))
                    del self._store[oldest_key]
            self._store[key] = (expires_at, value)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def invalidate_prefix(self, prefix: str) -> None:
        with self._lock:
            keys = [k for k in self._store if k.startswith(prefix)]
            for k in keys:
                del self._store[k]


auth_token_cache = TTLCache(max_size=512, default_ttl=60.0)
profile_sync_cache = TTLCache(max_size=512, default_ttl=300.0)
repo_response_cache = TTLCache(max_size=512, default_ttl=90.0)
health_cache = TTLCache(max_size=8, default_ttl=30.0)
