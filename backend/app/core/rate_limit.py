"""Per-key sliding-window rate limiter.

Used for endpoints where the limit value is dynamic — e.g. grounded chat,
where each tenant can have a different per-minute cap stored on the tenant
row. slowapi's decorator value is fixed at definition time, so it can't
read DB state.

In-memory only — fine for a single-process deploy. For multi-worker /
multi-pod prod, swap the storage backend for Redis (slowapi already
supports this if the limit value can be made static via the key namespace).
"""
from __future__ import annotations

import time
from collections import deque
from threading import Lock

from fastapi import HTTPException

# {bucket_key: deque of float epoch timestamps within the active window}
_buckets: dict[str, deque[float]] = {}
_lock = Lock()


def check(key: str, limit_per_minute: int) -> None:
    """Raise HTTPException(429) if `key` has exceeded `limit_per_minute` in
    the past 60 seconds. Otherwise records a hit and returns silently."""
    if limit_per_minute <= 0:
        return  # 0 = unlimited; useful for internal/admin use cases.

    now = time.monotonic()
    cutoff = now - 60.0

    with _lock:
        bucket = _buckets.setdefault(key, deque())
        # Drop hits older than the window.
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

        if len(bucket) >= limit_per_minute:
            # Compute the seconds until the oldest hit ages out.
            retry_after = max(1, int(60 - (now - bucket[0])))
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded ({limit_per_minute}/minute). Retry in {retry_after}s.",
                headers={"Retry-After": str(retry_after)},
            )
        bucket.append(now)


def reset() -> None:
    """Test helper — wipe all buckets."""
    with _lock:
        _buckets.clear()
