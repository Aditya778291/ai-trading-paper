from fastapi.testclient import TestClient
from src.api.app import app
from src.api.jobs import JobQueue

def test_health_v12():
    c=TestClient(app); r=c.get('/api/health'); assert r.status_code==200; assert r.json()['version']=='1.8.0'

def test_local_job_queue():
    q=JobQueue(); assert q.backend=='local'; q.enqueue('test',{'x':1}); assert q.depth()==1

def test_auth_and_metrics():
    c=TestClient(app); email='v12_test@example.com';
    r=c.post('/api/auth/register',json={'email':email,'password':'strong-pass-123'}); assert r.status_code in (201,409)
    if r.status_code==409: r=c.post('/api/auth/login',json={'email':email,'password':'strong-pass-123'})
    token=r.json()['access_token']; m=c.get('/api/metrics',headers={'Authorization':f'Bearer {token}'}); assert m.status_code==200; assert 'requests' in m.json()
