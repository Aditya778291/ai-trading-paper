from __future__ import annotations
import time
from collections import defaultdict, deque
from threading import Lock

class RateLimiter:
    """Small process-local limiter for dev/single-instance deployments.
    Use a shared gateway/Redis limiter for multi-instance production deployments.
    """
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit; self.window = window_seconds
        self._hits = defaultdict(deque); self._lock = Lock()
    def allow(self, key: str) -> bool:
        now = time.monotonic(); cutoff = now - self.window
        with self._lock:
            q = self._hits[key]
            while q and q[0] <= cutoff: q.popleft()
            if len(q) >= self.limit: return False
            q.append(now); return True

login_limiter = RateLimiter(10, 300)
