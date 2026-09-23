from __future__ import annotations
import json, os, threading, time
from collections import deque
from dataclasses import dataclass

@dataclass
class Job:
    name: str
    payload: dict

class JobQueue:
    """Redis-backed queue with an explicit local fallback for development/tests."""
    def __init__(self):
        self.redis_url=os.getenv('REDIS_URL','').strip(); self._local=deque(); self._lock=threading.Lock(); self._redis=None
        if self.redis_url:
            try:
                import redis
                self._redis=redis.Redis.from_url(self.redis_url, decode_responses=True)
                self._redis.ping()
            except Exception: self._redis=None
    @property
    def backend(self): return 'redis' if self._redis is not None else 'local'
    def enqueue(self,name,payload):
        raw=json.dumps({'name':name,'payload':payload},default=str)
        if self._redis is not None: self._redis.rpush('ai_trading:jobs',raw); return
        with self._lock: self._local.append(raw)
    def depth(self):
        if self._redis is not None: return int(self._redis.llen('ai_trading:jobs'))
        with self._lock: return len(self._local)
    def pop(self, timeout=1):
        if self._redis is not None:
            item=self._redis.blpop('ai_trading:jobs', timeout=timeout)
            return item[1] if item else None
        deadline=time.time()+timeout
        while time.time()<deadline:
            with self._lock:
                if self._local: return self._local.popleft()
            time.sleep(0.05)
        return None
queue=JobQueue()
