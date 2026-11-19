"""
backend/ratelimit.py - Small in-memory rate limits for the public endpoints.

The API runs as a single process, so a dict of timestamps is enough. Limits
reset when the server restarts, which is fine for stopping floods.
"""
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import HTTPException, Request


class RateLimiter:
    def __init__(self) -> None:
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_seconds: float) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            if len(self._hits) > 20000:  # drop idle keys so memory stays small
                for k in [k for k, v in self._hits.items() if not v]:
                    del self._hits[k]
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()


def client_ip(request: Request) -> str:
    """The visitor's IP. On Render, requests arrive through a proxy, so
    request.client is the proxy; the real address is in the forwarding headers."""
    for header in ("true-client-ip", "cf-connecting-ip"):
        value = request.headers.get(header, "").strip()
        if value:
            return value
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


def enforce(request: Request, name: str, limit: int, window_seconds: float, message: str) -> None:
    """Raise 429 when this visitor has used `name` more than `limit` times in the window."""
    if not limiter.allow(f"{name}:{client_ip(request)}", limit, window_seconds):
        raise HTTPException(status_code=429, detail=message)
