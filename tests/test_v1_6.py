import os, uuid
os.environ['DATABASE_URL']='sqlite:///./data/test_v16.db'; os.environ['JWT_SECRET']='x'*40
from fastapi.testclient import TestClient
from src.api.app import app
from src.api.market_data import Quote, market_data
from src.api.strategy_engine import backtest_strategy
from datetime import datetime, timezone

def auth(c):
    email=f'v16-{uuid.uuid4().hex}@example.com'; password='password123'; c.post('/api/auth/register',json={'email':email,'password':password}); return c.post('/api/auth/login',json={'email':email,'password':password}).json()['access_token']

def test_strategy_crud_and_validation():
    c=TestClient(app); h={'Authorization':f'Bearer {auth(c)}'}
    r=c.post('/api/strategies',headers=h,json={'name':'Momentum','symbols':'AAA.NS,BBB.NS','position_size_pct':10,'max_exposure_pct':20,'enabled':False}); assert r.status_code==201
    sid=r.json()['id']; assert c.get('/api/strategies',headers=h).json()[0]['name']=='Momentum'
    r=c.post(f'/api/strategies/{sid}/enable?enabled=true',headers=h); assert r.status_code==200 and r.json()['enabled'] is True
    assert c.delete(f'/api/strategies/{sid}',headers=h).json()['deleted'] is True

def test_strategy_backtest():
    r=backtest_strategy([100,101,102,100,99,103,104]); assert r['trade_count']>=2; assert 'max_drawdown_pct' in r

def test_strategy_run_once_places_paper_order(monkeypatch):
    monkeypatch.setattr(market_data,'quote',lambda symbol,force=False: Quote(symbol.upper(),101.0,datetime.now(timezone.utc)))
    c=TestClient(app); h={'Authorization':f'Bearer {auth(c)}'}
    c.post('/api/portfolio/reset',headers=h)
    # Seed previous price so next quote creates a BUY signal.
    from src.api.event_engine import engine
    engine._previous_prices['AAA.NS']=100.0
    r=c.post('/api/strategies',headers=h,json={'name':'Auto','symbols':'AAA.NS','enabled':True,'min_confidence':1,'position_size_pct':5,'max_exposure_pct':10,'cooldown_seconds':0}); assert r.status_code==201
    r=c.post('/api/strategies/run-once',headers=h); assert r.status_code==200
    assert r.json()['orders'] and r.json()['orders'][0]['side']=='BUY'
