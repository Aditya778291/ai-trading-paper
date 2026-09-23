import os, uuid
os.environ['DATABASE_URL']='sqlite:///./data/test_v1_api.db'
os.environ['JWT_SECRET']='test-secret'
from fastapi.testclient import TestClient
from src.api.app import app

client=TestClient(app)

def test_health():
    r=client.get('/api/health'); assert r.status_code==200; assert r.json()['status']=='ok'

def test_register_login_and_order():
    email=f'test-v1-{uuid.uuid4().hex}@example.com'
    client.post('/api/auth/register',json={'email':email,'password':'password123'})
    r=client.post('/api/auth/login',json={'email':email,'password':'password123'}); assert r.status_code==200
    token=r.json()['access_token']; h={'Authorization':f'Bearer {token}'}
    assert client.get('/api/portfolio',headers=h).json()['cash']==100000
    r=client.post('/api/orders',headers=h,json={'symbol':'RELIANCE.NS','side':'BUY','quantity':10,'price':1000}); assert r.status_code==200
    assert client.get('/api/positions',headers=h).json()[0]['quantity']==10
    r=client.post('/api/orders',headers=h,json={'symbol':'RELIANCE.NS','side':'SELL','quantity':4,'price':1100}); assert r.status_code==200
    assert client.get('/api/trades',headers=h).json()['items'][0]['realized_pnl']>0

def test_auth_required(): assert client.get('/api/portfolio').status_code==401
