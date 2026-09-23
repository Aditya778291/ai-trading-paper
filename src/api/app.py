from __future__ import annotations
import json, time, uuid
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import select, desc, text
from .database import get_db, init_db
from .config import settings
from .models import User, Portfolio, Order, Position, Trade, Decision, Strategy
from .audit import AuditEvent
from .schemas import RegisterIn, LoginIn, TokenOut, OrderIn, DecisionIn, UserOut
from .security import hash_password, verify_password, create_token, decode_token
from .notifications import notifier
from .hardening import login_limiter
from .observability import metrics, configure_logging
import logging
from datetime import datetime, timezone
import pandas as pd
from .jobs import queue
from .rate_limit import api_limiter
from .market_data import market_data, MarketDataError
from .live_engine import mark_portfolio_to_market
from .strategy_engine import strategy_engine, backtest_strategy
from src.data.universe import get_universe, search_universe, DISPLAY_NAMES
from src.features.feature_pipeline import build_features
from src.ai.intelligence import classify_market_regime, ensemble_signal
from src.models.ml_research import run_research, MLConfig
import math
from .event_engine import engine
from .schemas import MarketOrderIn, StrategyIn

settings.validate()
configure_logging()
log=logging.getLogger(__name__)
app=FastAPI(title='AI Trading Platform API', version='1.8.0', description='Market data, AI research and paper-trading API. No broker execution.')
origins=[x.strip() for x in settings.allowed_origins.split(',') if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=['GET','POST','DELETE','OPTIONS'], allow_headers=['Authorization','Content-Type','Idempotency-Key','X-Request-ID'])
bearer=HTTPBearer(auto_error=False)

@app.middleware('http')
async def security_middleware(request: Request, call_next):
    request_id=request.headers.get('X-Request-ID') or uuid.uuid4().hex
    start=time.perf_counter()
    if request.url.path.startswith('/api') and request.url.path not in ('/api/health','/api/ready'):
        if not api_limiter.allow(request.client.host if request.client else 'unknown'):
            from fastapi.responses import JSONResponse
            return JSONResponse({'detail':'Rate limit exceeded'}, status_code=429, headers={'X-Request-ID':request_id})
    response=await call_next(request)
    response.headers['X-Request-ID']=request_id
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['Cache-Control']='no-store' if request.url.path.startswith('/api') else 'no-cache'
    if settings.environment == 'production': response.headers['Strict-Transport-Security']='max-age=31536000; includeSubDomains'
    elapsed=(time.perf_counter()-start)*1000
    response.headers['X-Response-Time-ms']=f'{elapsed:.2f}'
    metrics.observe(request.method, request.url.path, response.status_code, elapsed)
    log.info('request method=%s path=%s status=%s request_id=%s latency_ms=%.2f', request.method, request.url.path, response.status_code, request_id, elapsed)
    return response

init_db()

def audit(db, event, user_id=None, request_id=None, detail=None):
    db.add(AuditEvent(user_id=user_id,event=event,request_id=request_id,detail=json.dumps(detail,default=str) if detail is not None else None))

def current_user(creds: HTTPAuthorizationCredentials=Depends(bearer), db: Session=Depends(get_db)) -> User:
    if not creds: raise HTTPException(status_code=401, detail='Authentication required')
    try: uid=decode_token(creds.credentials)
    except Exception: raise HTTPException(status_code=401, detail='Invalid or expired token')
    user=db.get(User,uid)
    if not user: raise HTTPException(status_code=401, detail='User not found')
    return user

def portfolio_for(user: User, db: Session) -> Portfolio:
    p=db.scalar(select(Portfolio).where(Portfolio.user_id==user.id))
    if not p:
        p=Portfolio(user_id=user.id); db.add(p); db.commit(); db.refresh(p)
    return p

@app.get('/api/health')
def health(): return {'status':'ok','service':'ai-trading-platform','version':'1.8.0','mode':'paper-trading-only'}

@app.get('/api/metrics')
def api_metrics(user=Depends(current_user)):
    return {**metrics.snapshot(), 'job_queue_backend': queue.backend, 'job_queue_depth': queue.depth()}

@app.get('/api/metrics/prometheus')
def prometheus_metrics(user=Depends(current_user)):
    snap=metrics.snapshot()
    lines=[f"ai_trading_requests_total {snap['requests']}", f"ai_trading_errors_total {snap['errors']}", f"ai_trading_p95_latency_ms {snap['p95_latency_ms']}"]
    return __import__('fastapi').responses.PlainTextResponse('\n'.join(lines)+'\n', media_type='text/plain; version=0.0.4')

@app.get('/api/ready')
def ready(db:Session=Depends(get_db)):
    try: db.execute(text('SELECT 1'))
    except Exception: raise HTTPException(503,'Database unavailable')
    return {'status':'ready','database':'ok'}

@app.post('/api/auth/register', response_model=TokenOut, status_code=201)
def register(data:RegisterIn, request:Request, db:Session=Depends(get_db)):
    email=data.email.lower()
    if db.scalar(select(User).where(User.email==email)): raise HTTPException(409,'Email already registered')
    user=User(email=email,password_hash=hash_password(data.password)); db.add(user); db.flush(); db.add(Portfolio(user_id=user.id)); audit(db,'auth.register',user.id,request.headers.get('X-Request-ID'),{'email':email}); db.commit()
    return TokenOut(access_token=create_token(user.id))

@app.post('/api/auth/login', response_model=TokenOut)
def login(data:LoginIn, request:Request, db:Session=Depends(get_db)):
    key=f'{request.client.host if request.client else "unknown"}:{data.email.lower()}'
    if not login_limiter.allow(key): raise HTTPException(429,'Too many login attempts; try again later')
    user=db.scalar(select(User).where(User.email==data.email.lower()))
    if not user or not verify_password(data.password,user.password_hash): raise HTTPException(401,'Invalid credentials')
    audit(db,'auth.login',user.id,request.headers.get('X-Request-ID')); db.commit()
    return TokenOut(access_token=create_token(user.id))

@app.get('/api/me', response_model=UserOut)
def me(user=Depends(current_user)): return user

def _quote_dict(q):
    change = (q.price - q.previous_close) if q.previous_close else None
    change_pct = (change / q.previous_close * 100.0) if change is not None and q.previous_close else None
    return {
        'symbol': q.symbol, 'name': DISPLAY_NAMES.get(q.symbol, q.symbol), 'price': q.price,
        'previous_close': q.previous_close, 'change': change, 'change_pct': change_pct,
        'open': q.open, 'high': q.high, 'low': q.low, 'volume': q.volume,
        'timestamp': q.timestamp, 'source': q.source,
    }

@app.get('/api/market/universe')
def market_universe(user=Depends(current_user)):
    return [{'symbol':i.symbol,'name':i.name,'market':i.market} for i in get_universe()]

@app.get('/api/market/search')
def market_search(q: str = '', user=Depends(current_user)):
    rows=search_universe(q)[:50]
    return [{'symbol':i.symbol,'name':i.name,'market':i.market} for i in rows]

@app.get('/api/market/quote/{symbol}')
def market_quote(symbol: str, user=Depends(current_user)):
    try:
        return _quote_dict(market_data.quote(symbol))
    except MarketDataError as exc:
        raise HTTPException(503, str(exc))

@app.get('/api/market/quotes')
def market_quotes(symbols: str, user=Depends(current_user)):
    requested=[x.strip().upper() for x in symbols.split(',') if x.strip()]
    if not requested: raise HTTPException(422,'symbols is required')
    try:
        quotes=market_data.quotes(requested)
    except MarketDataError as exc:
        raise HTTPException(503,str(exc))
    return [_quote_dict(q) for q in quotes]

@app.get('/api/market/history/{symbol}')
def market_history(symbol: str, range: str = '1d', user=Depends(current_user)):
    try:
        df=market_data.history(symbol, range)
    except MarketDataError as exc:
        raise HTTPException(503, str(exc))
    candles=[]
    for idx,row in df.iterrows():
        ts=idx.to_pydatetime() if hasattr(idx,'to_pydatetime') else idx
        if ts.tzinfo is None: ts=ts.replace(tzinfo=timezone.utc)
        candles.append({'time':ts.isoformat(),'open':float(row.get('Open',row['Close'])),'high':float(row.get('High',row['Close'])),'low':float(row.get('Low',row['Close'])),'close':float(row['Close']),'volume':float(row.get('Volume',0) or 0)})
    return {'symbol':symbol.upper(),'name':DISPLAY_NAMES.get(symbol.upper(),symbol.upper()),'range':range,'candles':candles,'source':'yahoo_finance'}

_ai_cache = {}
@app.get('/api/ai/insight/{symbol}')
def ai_insight(symbol: str, user=Depends(current_user)):
    key=symbol.strip().upper()
    now=time.time()
    cached=_ai_cache.get(key)
    if cached and now-cached[0] < 120:
        return cached[1]
    try:
        df=market_data.history(key,'5y')
        features=build_features(df, drop_warmup_rows=False)
        regime=classify_market_regime(features)
        latest=features.dropna(subset=['Close']).iloc[-1]
        rsi=float(latest['RSI_14']) if pd.notna(latest.get('RSI_14')) else None
        macd=float(latest['MACD']) if pd.notna(latest.get('MACD')) else None
        macd_hist=float(latest['MACD_HIST']) if pd.notna(latest.get('MACD_HIST')) else None
        sma20=float(latest['SMA_20']) if pd.notna(latest.get('SMA_20')) else None
        sma50=float(latest['SMA_50']) if pd.notna(latest.get('SMA_50')) else None
        score=0.0
        reasons=[]
        if rsi is not None:
            if rsi < 30: score += 1; reasons.append('RSI is in an oversold zone')
            elif rsi > 70: score -= 1; reasons.append('RSI is in an overbought zone')
        if macd_hist is not None:
            if macd_hist > 0: score += 1; reasons.append('MACD histogram is positive')
            else: score -= 1; reasons.append('MACD histogram is negative')
        close=float(latest['Close'])
        if sma20 is not None:
            if close > sma20: score += 1; reasons.append('Price is above SMA 20')
            else: score -= 1; reasons.append('Price is below SMA 20')
        if sma50 is not None:
            if close > sma50: score += 1; reasons.append('Price is above SMA 50')
            else: score -= 1; reasons.append('Price is below SMA 50')
        rule_signal='Bullish' if score >= 2 else ('Bearish' if score <= -2 else 'Neutral')
        ml=None
        try:
            if len(df) >= 180:
                research=run_research(df, MLConfig(horizon=5, threshold=0.0, train_ratio=0.8))
                signal=ensemble_signal(research['results'])
                ml={'signal':signal.get('signal'),'probability':None if not math.isfinite(float(signal.get('probability',float('nan')))) else float(signal['probability']),'confidence':float(signal.get('confidence',0)),'model_count':int(signal.get('model_count',0))}
        except Exception as exc:
            ml={'signal':'Unavailable','probability':None,'confidence':0,'model_count':0,'error':str(exc)}
        result={'symbol':key,'name':DISPLAY_NAMES.get(key,key),'price':close,'signal':rule_signal,'score':score,'regime':regime.get('regime'),'trend':regime.get('trend'),'volatility':regime.get('volatility'),'rsi_14':rsi,'macd':macd,'macd_hist':macd_hist,'sma20':sma20,'sma50':sma50,'reasons':reasons[:6],'ml_research':ml,'generated_at':datetime.now(timezone.utc).isoformat(),'disclaimer':'AI output is a research signal, not investment advice or a guarantee of future returns.'}
        _ai_cache[key]=(now,result)
        return result
    except Exception as exc:
        raise HTTPException(503, f'Unable to generate AI insight: {exc}')

@app.get('/api/portfolio')
def portfolio(user=Depends(current_user),db:Session=Depends(get_db)):
    p=portfolio_for(user,db); snapshot=mark_portfolio_to_market(db,p)
    return {'id':p.id,'initial_cash':p.initial_cash,**snapshot}

@app.post('/api/portfolio/mark-to-market')
def mark_to_market(user=Depends(current_user),db:Session=Depends(get_db)):
    p=portfolio_for(user,db); return mark_portfolio_to_market(db,p,force=True)

def position_dict(x): return {'symbol':x.symbol,'quantity':x.quantity,'avg_price':x.avg_price,'market_price':x.market_price,'market_value':x.quantity*x.market_price,'unrealized_pnl':(x.market_price-x.avg_price)*x.quantity,'stop_loss':x.stop_loss,'take_profit':x.take_profit}

@app.get('/api/positions')
def positions(user=Depends(current_user),db:Session=Depends(get_db)):
    p=portfolio_for(user,db); return [position_dict(x) for x in db.scalars(select(Position).where(Position.portfolio_id==p.id,Position.quantity!=0)).all()]

@app.post('/api/orders/market')
def market_order(data:MarketOrderIn, request:Request, user=Depends(current_user),db:Session=Depends(get_db)):
    try:
        q=market_data.quote(data.symbol)
    except MarketDataError as exc:
        raise HTTPException(503,str(exc))
    return order(OrderIn(symbol=q.symbol, side=data.side, quantity=data.quantity, price=q.price, reason=data.reason or 'market-order', signal=data.signal, idempotency_key=data.idempotency_key), request, user, db)

@app.post('/api/orders')
def order(data:OrderIn, request:Request, user=Depends(current_user),db:Session=Depends(get_db)):
    side=data.side.upper(); symbol=data.symbol.upper()
    if side not in ('BUY','SELL'): raise HTTPException(422,'side must be BUY or SELL')
    p=portfolio_for(user,db)
    idempotency_key=data.idempotency_key or request.headers.get('Idempotency-Key')
    if idempotency_key:
        prior=db.scalar(select(Order).where(Order.idempotency_key==idempotency_key))
        if prior: return {'order_id':prior.id,'status':prior.status,'idempotent_replay':True}
    pos=db.scalar(select(Position).where(Position.portfolio_id==p.id,Position.symbol==symbol)); gross=data.quantity*data.price; fee=gross*settings.commission_bps/10000
    if side=='BUY':
        if p.cash < gross+fee: return reject(db,p,symbol,data,'Insufficient cash',request)
        p.cash-=gross+fee
        if not pos: pos=Position(portfolio_id=p.id,symbol=symbol,quantity=0,avg_price=0,market_price=data.price); db.add(pos)
        pos.avg_price=((pos.avg_price*pos.quantity)+(data.price*data.quantity))/(pos.quantity+data.quantity); pos.quantity+=data.quantity; pos.market_price=data.price; realized=0
    else:
        if not pos or pos.quantity < data.quantity: return reject(db,p,symbol,data,'Insufficient position',request)
        realized=(data.price-pos.avg_price)*data.quantity-fee; pos.quantity-=data.quantity; pos.market_price=data.price; p.cash+=gross-fee
        if pos.quantity==0: pos.avg_price=0
    o=Order(portfolio_id=p.id,symbol=symbol,side=side,quantity=data.quantity,price=data.price,status='FILLED',reason=data.reason,signal=data.signal,idempotency_key=idempotency_key); db.add(o); db.flush()
    db.add(Trade(portfolio_id=p.id,order_id=o.id,symbol=symbol,side=side,quantity=data.quantity,price=data.price,realized_pnl=realized,reason=data.reason,signal=data.signal)); queue.enqueue('notification',{'event':'order.filled','order_id':o.id,'symbol':symbol,'side':side}); audit(db,'order.filled',user.id,request.headers.get('X-Request-ID'),{'order_id':o.id,'symbol':symbol,'side':side}); db.commit()
    notifier.notify('order.filled',{'order_id':o.id,'symbol':symbol,'side':side,'quantity':data.quantity,'price':data.price})
    return {'order_id':o.id,'status':'FILLED','cash':p.cash,'position':position_dict(pos)}

def reject(db,p,symbol,data,reason,request):
    idempotency_key=data.idempotency_key or request.headers.get('Idempotency-Key')
    o=Order(portfolio_id=p.id,symbol=symbol,side=data.side.upper(),quantity=data.quantity,price=data.price,status='REJECTED',reason=reason,signal=data.signal,idempotency_key=idempotency_key); db.add(o); audit(db,'order.rejected',None,request.headers.get('X-Request-ID'),{'symbol':symbol,'reason':reason}); db.commit(); notifier.notify('order.rejected',{'symbol':symbol,'reason':reason}); raise HTTPException(422,reason)

@app.get('/api/orders')
def orders(user=Depends(current_user),db:Session=Depends(get_db),limit:int=50,offset:int=0):
    limit=max(1,min(limit,200)); offset=max(0,offset); p=portfolio_for(user,db); rows=db.scalars(select(Order).where(Order.portfolio_id==p.id).order_by(desc(Order.timestamp)).offset(offset).limit(limit+1)).all(); more=len(rows)>limit; rows=rows[:limit]
    return {'items':[order_dict(x) for x in rows],'next_offset':offset+limit if more else None}
def order_dict(x): return {'id':x.id,'symbol':x.symbol,'side':x.side,'quantity':x.quantity,'price':x.price,'status':x.status,'reason':x.reason,'signal':x.signal,'idempotency_key':x.idempotency_key,'timestamp':x.timestamp}

@app.get('/api/trades')
def trades(user=Depends(current_user),db:Session=Depends(get_db),limit:int=50,offset:int=0):
    limit=max(1,min(limit,200)); offset=max(0,offset); p=portfolio_for(user,db); rows=db.scalars(select(Trade).where(Trade.portfolio_id==p.id).order_by(desc(Trade.timestamp)).offset(offset).limit(limit+1)).all(); more=len(rows)>limit; rows=rows[:limit]
    return {'items':[trade_dict(x) for x in rows],'next_offset':offset+limit if more else None}
def trade_dict(x): return {'id':x.id,'order_id':x.order_id,'symbol':x.symbol,'side':x.side,'quantity':x.quantity,'price':x.price,'realized_pnl':x.realized_pnl,'reason':x.reason,'signal':x.signal,'timestamp':x.timestamp}

@app.post('/api/decisions')
def decision(data:DecisionIn,request:Request,user=Depends(current_user),db:Session=Depends(get_db)):
    p=portfolio_for(user,db); d=Decision(portfolio_id=p.id,symbol=data.symbol.upper(),signal=data.signal,confidence=data.confidence,regime=data.regime,explanation=data.explanation); db.add(d); db.flush(); audit(db,'decision.created',user.id,request.headers.get('X-Request-ID'),{'decision_id':d.id}); db.commit(); notifier.notify('decision.created',{'decision_id':d.id,'symbol':d.symbol,'signal':d.signal}); return decision_dict(d)
def decision_dict(x): return {'id':x.id,'symbol':x.symbol,'signal':x.signal,'confidence':x.confidence,'regime':x.regime,'explanation':x.explanation,'timestamp':x.timestamp}

@app.get('/api/decisions')
def decisions(user=Depends(current_user),db:Session=Depends(get_db),limit:int=50,offset:int=0):
    limit=max(1,min(limit,200)); offset=max(0,offset); p=portfolio_for(user,db); rows=db.scalars(select(Decision).where(Decision.portfolio_id==p.id).order_by(desc(Decision.timestamp)).offset(offset).limit(limit+1)).all(); more=len(rows)>limit; rows=rows[:limit]
    return {'items':[decision_dict(x) for x in rows],'next_offset':offset+limit if more else None}

@app.get('/api/audit')
def audit_log(user=Depends(current_user),db:Session=Depends(get_db),limit:int=50):
    limit=max(1,min(limit,200)); rows=db.scalars(select(AuditEvent).where(AuditEvent.user_id==user.id).order_by(desc(AuditEvent.timestamp)).limit(limit)).all(); return [{'id':x.id,'event':x.event,'request_id':x.request_id,'detail':x.detail,'timestamp':x.timestamp} for x in rows]

@app.delete('/api/account')
def delete_account(request: Request, user=Depends(current_user), db: Session=Depends(get_db)):
    # Google Play account deletion requirement: permanently remove the app account and paper-trading data.
    p = portfolio_for(user, db)
    db.query(Strategy).filter(Strategy.portfolio_id == p.id).delete(synchronize_session=False)
    db.query(AuditEvent).filter(AuditEvent.user_id == user.id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()
    return {'deleted': True}

@app.get('/api/strategies')
def strategies(user=Depends(current_user), db:Session=Depends(get_db)):
    p=portfolio_for(user,db)
    rows=db.scalars(select(Strategy).where(Strategy.portfolio_id==p.id).order_by(Strategy.id)).all()
    return [strategy_dict(x) for x in rows]

def strategy_dict(x):
    return {'id':x.id,'name':x.name,'symbols':x.symbols,'enabled':x.enabled,'min_confidence':x.min_confidence,'position_size_pct':x.position_size_pct,'max_exposure_pct':x.max_exposure_pct,'max_open_positions':x.max_open_positions,'cooldown_seconds':x.cooldown_seconds,'total_orders':x.total_orders,'last_action':x.last_action,'created_at':x.created_at}

@app.post('/api/strategies', status_code=201)
def create_strategy(data:StrategyIn, request:Request, user=Depends(current_user), db:Session=Depends(get_db)):
    if data.position_size_pct > data.max_exposure_pct: raise HTTPException(422,'position_size_pct cannot exceed max_exposure_pct')
    p=portfolio_for(user,db); s=Strategy(portfolio_id=p.id,**data.model_dump()); db.add(s); db.flush(); audit(db,'strategy.created',user.id,request.headers.get('X-Request-ID'),{'strategy_id':s.id}); db.commit(); return strategy_dict(s)

@app.post('/api/strategies/{strategy_id}/enable')
def enable_strategy(strategy_id:int, enabled:bool=True, user=Depends(current_user), db:Session=Depends(get_db)):
    p=portfolio_for(user,db); s=db.scalar(select(Strategy).where(Strategy.id==strategy_id,Strategy.portfolio_id==p.id))
    if not s: raise HTTPException(404,'Strategy not found')
    s.enabled=enabled; db.commit(); return strategy_dict(s)

@app.delete('/api/strategies/{strategy_id}')
def delete_strategy(strategy_id:int, user=Depends(current_user), db:Session=Depends(get_db)):
    p=portfolio_for(user,db); s=db.scalar(select(Strategy).where(Strategy.id==strategy_id,Strategy.portfolio_id==p.id))
    if not s: raise HTTPException(404,'Strategy not found')
    db.delete(s); db.commit(); return {'deleted':True,'strategy_id':strategy_id}

@app.get('/api/strategies/status')
def strategy_status(user=Depends(current_user)):
    st=strategy_engine.stats
    return {'running':strategy_engine.running,'interval_seconds':strategy_engine.interval_seconds,'cycles':st.cycles,'signals':st.signals,'orders':st.orders,'rejected':st.rejected,'errors':st.errors,'last_cycle':st.last_cycle}

@app.post('/api/strategies/start')
def strategy_start(user=Depends(current_user)):
    return {'started':strategy_engine.start(),'running':strategy_engine.running}

@app.post('/api/strategies/stop')
def strategy_stop(user=Depends(current_user)):
    return {'stopped':strategy_engine.stop(),'running':strategy_engine.running}

@app.post('/api/strategies/run-once')
def strategy_run_once(user=Depends(current_user)):
    return strategy_engine.run_once()

@app.post('/api/strategies/backtest')
def strategy_backtest(payload:dict, user=Depends(current_user)):
    prices=payload.get('prices')
    if not isinstance(prices,list): raise HTTPException(422,'prices must be a list')
    try: return backtest_strategy(prices, float(payload.get('min_move_pct',0.25)), float(payload.get('position_size_pct',10)), float(payload.get('commission_bps',settings.commission_bps)))
    except ValueError as exc: raise HTTPException(422,str(exc))

@app.get('/api/engine/status')
def engine_status(user=Depends(current_user)):
    st=engine.stats
    return {'running':engine.running,'interval_seconds':engine.interval_seconds,'max_quote_age_seconds':engine.max_quote_age_seconds,'cycles':st.cycles,'quotes':st.quotes,'risk_triggers':st.exits,'errors':st.errors,'last_cycle':st.last_cycle}

@app.post('/api/engine/start')
def engine_start(user=Depends(current_user)):
    return {'started':engine.start(),'running':engine.running}

@app.post('/api/engine/stop')
def engine_stop(user=Depends(current_user)):
    return {'stopped':engine.stop(),'running':engine.running}

@app.post('/api/engine/run-once')
def engine_run_once(user=Depends(current_user)):
    return engine.run_once()

@app.post('/api/positions/{symbol}/risk')
def position_risk(symbol: str, stop_loss: float|None=None, take_profit: float|None=None, user=Depends(current_user), db:Session=Depends(get_db)):
    if stop_loss is not None and stop_loss <= 0: raise HTTPException(422,'stop_loss must be positive')
    if take_profit is not None and take_profit <= 0: raise HTTPException(422,'take_profit must be positive')
    p=portfolio_for(user,db); pos=db.scalar(select(Position).where(Position.portfolio_id==p.id,Position.symbol==symbol.upper()))
    if not pos or pos.quantity == 0: raise HTTPException(404,'Open position not found')
    if stop_loss is not None and take_profit is not None and stop_loss >= take_profit: raise HTTPException(422,'stop_loss must be below take_profit')
    if stop_loss is not None and stop_loss >= pos.avg_price: raise HTTPException(422,'stop_loss must be below average price')
    if take_profit is not None and take_profit <= pos.avg_price: raise HTTPException(422,'take_profit must be above average price')
    pos.stop_loss=stop_loss; pos.take_profit=take_profit; db.commit()
    return position_dict(pos)

@app.post('/api/portfolio/reset')
def reset(request:Request,user=Depends(current_user),db:Session=Depends(get_db)):
    p=portfolio_for(user,db); p.cash=p.initial_cash
    for x in p.positions: x.quantity=0; x.avg_price=0; x.stop_loss=None; x.take_profit=None
    db.query(Order).filter(Order.portfolio_id==p.id).delete(); db.query(Trade).filter(Trade.portfolio_id==p.id).delete(); db.query(Decision).filter(Decision.portfolio_id==p.id).delete(); db.query(Strategy).filter(Strategy.portfolio_id==p.id).delete(); audit(db,'portfolio.reset',user.id,request.headers.get('X-Request-ID')); db.commit(); return {'status':'reset','cash':p.cash}
