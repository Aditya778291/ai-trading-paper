from __future__ import annotations
import json, logging, sys
from collections import Counter
from threading import Lock

class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({'ts': self.formatTime(record, '%Y-%m-%dT%H:%M:%S%z'), 'level':record.levelname, 'logger':record.name, 'message':record.getMessage()}, default=str)

def configure_logging():
    root=logging.getLogger()
    if not root.handlers:
        h=logging.StreamHandler(sys.stdout); h.setFormatter(JsonFormatter()); root.addHandler(h); root.setLevel(logging.INFO)

class Metrics:
    def __init__(self): self._lock=Lock(); self.requests=Counter(); self.errors=Counter(); self.latency_ms=[]
    def observe(self, method, path, status, elapsed_ms):
        with self._lock:
            self.requests[(method,path)]+=1
            if status>=500: self.errors[(method,path)]+=1
            self.latency_ms.append(elapsed_ms); self.latency_ms=self.latency_ms[-2000:]
    def snapshot(self):
        with self._lock:
            lat=sorted(self.latency_ms); p95=lat[int(.95*(len(lat)-1))] if lat else 0
            return {'requests':sum(self.requests.values()),'errors':sum(self.errors.values()),'p95_latency_ms':round(p95,2), 'by_route':{f'{m} {p}':n for (m,p),n in self.requests.items()}}
metrics=Metrics()
