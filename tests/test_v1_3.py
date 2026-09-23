import os
os.environ['DATABASE_URL']='sqlite:///./data/test_v13.db'
os.environ['JWT_SECRET']='x'*40
from fastapi.testclient import TestClient
from src.api.app import app
from src.api.jobs import JobQueue

def test_health_v13():
    r=TestClient(app).get('/api/health'); assert r.status_code==200; assert r.json()['version']=='1.8.0'

def test_queue_pop():
    q=JobQueue(); q.enqueue('x',{'a':1}); assert q.pop(0.1)

def test_prometheus_metrics_requires_auth():
    c=TestClient(app); assert c.get('/api/metrics/prometheus').status_code==401
