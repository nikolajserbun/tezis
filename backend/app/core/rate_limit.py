import asyncio
import time
from collections import defaultdict, deque

from redis.asyncio import Redis

from app.core.config import settings


class RateLimiter:
    """Small Redis-backed sliding window limiter with an in-memory fallback.

    The fallback is intentional: local dev and tests must work without Redis.
    """

    def __init__(self) -> None:
        self._redis: Redis | None = None
        self._redis_checked = False
        self._memory: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def _get_redis(self) -> Redis | None:
        if self._redis_checked:
            return self._redis
        self._redis_checked = True
        try:
            client = Redis.from_url(settings.redis_url, decode_responses=True)
            await client.ping()
            self._redis = client
        except Exception:
            self._redis = None
        return self._redis

    async def hit(self, key: str, *, limit: int, window_seconds: int) -> bool:
        """Return True if the request is allowed, False if the limit is exceeded."""
        redis = await self._get_redis()
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
