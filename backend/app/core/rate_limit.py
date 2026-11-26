from collections import deque
import threading
import time
from uuid import UUID
from fastapi import status

from app.core.errors import AppError


class SlidingWindowRateLimiter:
    """Thread-safe in-memory per-user sliding-window rate limiter."""

    def __init__(self) -> None:
        self._buckets: dict[tuple[UUID, str], deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, user_id: UUID, bucket: str, max_requests: int, window_seconds: float) -> None:
        now = time.monotonic()
        cutoff = now - window_seconds
        key = (user_id, bucket)

        with self._lock:
            timestamps = self._buckets.setdefault(key, deque())
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if len(timestamps) >= max_requests:
                raise AppError(
                    message=f"Rate limit exceeded for {bucket}. Please wait a moment and try again.",
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    code="rate_limited",
                )
            timestamps.append(now)


rate_limiter = SlidingWindowRateLimiter()
