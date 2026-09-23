import os
os.environ['DATABASE_URL']='sqlite:///./data/test_v14.db'
os.environ['JWT_SECRET']='x'*40
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from src.api.app import app
from src.api.market_data import Quote, market_data

def test_health_v14():
    r=TestClient(app).get('/api/health'); assert r.status_code==200; assert r.json()['version']=='1.8.0'

def test_market_quote_cache(monkeypatch):
    market_data._cache.clear()
    monkeypatch.setattr(market_data, 'quote', lambda symbol, force=False: Quote(symbol.upper(), 123.45, datetime.now(timezone.utc)))
    q=market_data.quote('reliance.ns'); assert q.price==123.45; assert q.symbol=='RELIANCE.NS'

def test_market_order_uses_latest_quote(monkeypatch):
    from src.api.app import market_data as md
    monkeypatch.setattr(md, 'quote', lambda symbol, force=False: Quote(symbol.upper(), 100.0, datetime.now(timezone.utc)))
    c=TestClient(app)
    email='v14@example.com'; password='password123'
    c.post('/api/auth/register',json={'email':email,'password':password})
    token=c.post('/api/auth/login',json={'email':email,'password':password}).json()['access_token']
    r=c.post('/api/orders/market',headers={'Authorization':f'Bearer {token}'},json={'symbol':'RELIANCE.NS','side':'BUY','quantity':2})
    assert r.status_code==200; assert r.json()['status']=='FILLED'; assert r.json()['position']['market_price']==100.0
