import os
os.environ['DATABASE_URL']='sqlite:///./data/test_v1_1.db'
os.environ['JWT_SECRET']='test-secret-for-v1-1-hardening-123456789'
os.environ['ENVIRONMENT']='test'
from fastapi.testclient import TestClient
from src.api.app import app
from src.api.hardening import RateLimiter

def test_health_and_ready():
    c=TestClient(app); assert c.get('/api/health').status_code==200; assert c.get('/api/ready').json()['status']=='ready'

def test_security_headers_and_request_id():
    r=TestClient(app).get('/api/health',headers={'X-Request-ID':'abc123'}); assert r.headers['X-Request-ID']=='abc123'; assert r.headers['X-Content-Type-Options']=='nosniff'; assert r.headers['X-Frame-Options']=='DENY'

def test_register_order_idempotency():
    c=TestClient(app); email='hardening@example.com'; p='strongpass123'; rr=c.post('/api/auth/register',json={'email':email,'password':p}); assert rr.status_code in (201,409); token=rr.json().get('access_token') or c.post('/api/auth/login',json={'email':email,'password':p}).json()['access_token']; h={'Authorization':f'Bearer {token}','Idempotency-Key':'order-unique-1'}
    a=c.post('/api/orders',headers=h,json={'symbol':'TCS','side':'BUY','quantity':1,'price':100}); b=c.post('/api/orders',headers=h,json={'symbol':'TCS','side':'BUY','quantity':1,'price':100}); assert a.status_code==200 and b.json().get('idempotent_replay') is True

def test_rate_limiter():
    r=RateLimiter(2,60); assert r.allow('x'); assert r.allow('x'); assert not r.allow('x')
