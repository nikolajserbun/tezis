import asyncio
import time
from collections import defaultdict, deque

from redis.asyncio import Redis

from app.core.config import settings
from app.core.errors import ServiceUnavailable


class RateLimiter:
    """Small Redis-backed sliding window limiter with an in-memory fallback.

    The fallback is intentional: local dev and tests must work without Redis.
    """

    RETRY_SECONDS = 5.0

    def __init__(self) -> None:
        self._redis: Redis | None = None
        self._retry_at = 0.0
        self._memory: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def _get_redis(self) -> Redis | None:
        if self._redis is not None:
            return self._redis
        now = time.monotonic()
        if now < self._retry_at:
            return None
        # Retry after a cooldown instead of sticking to the memory fallback
        # forever after one transient Redis failure.
        self._retry_at = now + self.RETRY_SECONDS
        try:
            client = Redis.from_url(settings.redis_url, decode_responses=True)
            await client.ping()
            self._redis = client
            self._retry_at = 0.0
        except Exception:
            self._redis = None
        return self._redis

    async def aclose(self) -> None:
        """Close the Redis client on shutdown (no-op in local dev/tests)."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
            self._retry_at = 0.0

    async def hit(self, key: str, *, limit: int, window_seconds: int) -> bool:
        """Return True if the request is allowed, False if the limit is exceeded."""
        redis = await self._get_redis()
        if redis is None and (settings.is_prod or settings.is_serverless):
            # A shared per-process bucket is meaningless across serverless
            # instances; fail closed rather than silently dropping limits.
            raise ServiceUnavailable("Rate limit storage is unavailable")
        if redis is not None:
            try:
                now = time.time()
                pipe = redis.pipeline()
                pipe.zremrangebyscore(key, 0, now - window_seconds)
                pipe.zcard(key)
                pipe.zadd(key, {f"{now}:{id(object())}": now})
                pipe.expire(key, window_seconds)
                _, count, _, _ = await pipe.execute()
                return int(count) < limit
            except Exception:
                self._redis = None
                self._retry_at = time.monotonic() + self.RETRY_SECONDS

        async with self._lock:
            now = time.time()
            bucket = self._memory[key]
            while bucket and bucket[0] <= now - window_seconds:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True


limiter = RateLimiter()
