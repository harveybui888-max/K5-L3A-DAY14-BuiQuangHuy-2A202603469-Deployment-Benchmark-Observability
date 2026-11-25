"""
Rate limiting (tiêu chí 7) — sliding window 60s lưu trong Redis.
"""
import hashlib
import time
import uuid

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

_memory_requests: dict[str, list[float]] = {}


def _key_id(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]


def check_rate_limit(key: str) -> None:
    """Giới hạn RATE_LIMIT_PER_MINUTE request / 60s cho mỗi API key."""
    limit = settings.rate_limit_per_minute
    now = time.time()
    window_start = now - 60.0
    redis_key = f"ratelimit:{_key_id(key)}"

    if r is not None:
        try:
            pipe = r.pipeline()
            pipe.zremrangebyscore(redis_key, 0, window_start)
            pipe.zcard(redis_key)
            _, count = pipe.execute()

            if count >= limit:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded",
                    headers={"Retry-After": "60"},
                )

            member = f"{now}:{uuid.uuid4().hex[:8]}"
            pipe = r.pipeline()
            pipe.zadd(redis_key, {member: now})
            pipe.expire(redis_key, 120)
            pipe.execute()
            return
        except HTTPException:
            raise
        except Exception:
            pass

    timestamps = [t for t in _memory_requests.get(redis_key, []) if t > window_start]
    if len(timestamps) >= limit:
        _memory_requests[redis_key] = timestamps
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": "60"},
        )
    timestamps.append(now)
    _memory_requests[redis_key] = timestamps
