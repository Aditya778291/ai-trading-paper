import os
os.environ['DATABASE_URL']='sqlite:///./data/test_v15.db'
os.environ['JWT_SECRET']='x'*40
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from src.api.app import app
from src.api.market_data import Quote, market_data

def auth(c):
    email='v15@example.com'; password='password123'
    c.post('/api/auth/register',json={'email':email,'password':password})
    return c.post('/api/auth/login',json={'email':email,'password':password}).json()['access_token']

def test_health_v15():
    assert TestClient(app).get('/api/health').json()['version']=='1.8.0'

def test_risk_levels_and_engine_trigger(monkeypatch):
    
    monkeypatch.setattr(market_data,'quote',lambda symbol,force=False: Quote(symbol.upper(),100.0 if not force else 110.0,datetime.now(timezone.utc)))
    c=TestClient(app); token=auth(c); h={'Authorization':f'Bearer {token}'}
    c.post('/api/portfolio/reset',headers=h)
    r=c.post('/api/orders/market',headers=h,json={'symbol':'TEST.NS','side':'BUY','quantity':2})
    assert r.status_code==200
    r=c.post('/api/positions/TEST.NS/risk',headers=h,params={'stop_loss':90,'take_profit':105})
    assert r.status_code==200 and r.json()['take_profit']==105
    r=c.post('/api/engine/run-once',headers=h); assert r.status_code==200
    assert r.json()['triggers'][0]['reason']=='take-profit'
    pos=c.get('/api/positions',headers=h).json(); assert all(x['symbol'] != 'TEST.NS' for x in pos)

def test_risk_validation(monkeypatch):
    monkeypatch.setattr(market_data,'quote',lambda symbol,force=False: Quote(symbol.upper(),100.0,datetime.now(timezone.utc)))
    c=TestClient(app); token=auth(c); h={'Authorization':f'Bearer {token}'}
    c.post('/api/portfolio/reset',headers=h)
    c.post('/api/orders/market',headers=h,json={'symbol':'ABC.NS','side':'BUY','quantity':1})
    r=c.post('/api/positions/ABC.NS/risk',headers=h,params={'stop_loss':105})
    assert r.status_code==422
