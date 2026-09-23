from __future__ import annotations
import os, time
class SharedRateLimiter:
    def __init__(self, limit=60, window=60): self.limit=limit; self.window=window; self.redis=None; self.backend='local'
    def configure(self):
        url=os.getenv('REDIS_URL','').strip()
        if not url:return
        try:
            import redis
            r=redis.Redis.from_url(url, decode_responses=True); r.ping(); self.redis=r; self.backend='redis'
        except Exception: pass
    def allow(self,key):
        if self.redis:
            bucket=int(time.time()//self.window); k=f'ai_trading:rl:{key}:{bucket}'
            n=self.redis.incr(k); self.redis.expire(k,self.window+1); return n<=self.limit
        return True
api_limiter=SharedRateLimiter(); api_limiter.configure()
