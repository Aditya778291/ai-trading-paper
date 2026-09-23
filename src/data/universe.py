from __future__ import annotations

from dataclasses import dataclass

# A broad starter universe. The market API also accepts any valid Yahoo Finance
# ticker, so this list is a discovery/watchlist surface rather than a claim that
# it contains every security traded worldwide.
MARKET_GROUPS = {
    "Indian Indices": [
        ("^NSEI", "NIFTY 50"), ("^NSEBANK", "BANK NIFTY"),
        ("^CNXFIN", "FINNIFTY"), ("^CNXMIDCAP", "NIFTY MIDCAP 100"),
        ("^BSESN", "SENSEX"), ("^BSEBANK", "BSE BANKEX"),
        ("^NSEMDCP50", "NIFTY MIDCAP SELECT"),
    ],
    "Indian Stocks": [
        ("RELIANCE.NS", "RELIANCE"), ("TCS.NS", "TCS"), ("INFY.NS", "INFOSYS"),
        ("HDFCBANK.NS", "HDFC BANK"), ("ICICIBANK.NS", "ICICI BANK"),
        ("SBIN.NS", "SBI"), ("ITC.NS", "ITC"), ("LT.NS", "LARSEN & TOUBRO"),
        ("BHARTIARTL.NS", "BHARTI AIRTEL"), ("TATAMOTORS.NS", "TATA MOTORS"),
        ("AXISBANK.NS", "AXIS BANK"), ("KOTAKBANK.NS", "KOTAK MAHINDRA BANK"),
        ("HINDUNILVR.NS", "HINDUSTAN UNILEVER"), ("MARUTI.NS", "MARUTI SUZUKI"),
        ("SUNPHARMA.NS", "SUN PHARMA"), ("M&M.NS", "M&M"),
        ("ADANIENT.NS", "ADANI ENTERPRISES"), ("ADANIPORTS.NS", "ADANI PORTS"),
        ("TITAN.NS", "TITAN"), ("BAJFINANCE.NS", "BAJAJ FINANCE"),
        ("WIPRO.NS", "WIPRO"), ("HCLTECH.NS", "HCLTECH"),
        ("NTPC.NS", "NTPC"), ("POWERGRID.NS", "POWER GRID"),
        ("ONGC.NS", "ONGC"), ("COALINDIA.NS", "COAL INDIA"),
    ],
    "US Indices": [
        ("^GSPC", "S&P 500"), ("^IXIC", "NASDAQ Composite"),
        ("^DJI", "Dow Jones"), ("^RUT", "Russell 2000"),
    ],
    "Global Indices": [
        ("^FTSE", "FTSE 100"), ("^GDAXI", "DAX"), ("^FCHI", "CAC 40"),
        ("^N225", "Nikkei 225"), ("^HSI", "Hang Seng"), ("000001.SS", "Shanghai Composite"),
        ("^STI", "STI"), ("^KS11", "KOSPI"), ("^AXJO", "ASX 200"),
    ],
    "Commodities": [
        ("GC=F", "Gold Futures"), ("SI=F", "Silver Futures"),
        ("CL=F", "WTI Crude Oil"), ("BZ=F", "Brent Crude"),
        ("NG=F", "Natural Gas"), ("HG=F", "Copper Futures"),
    ],
    "Currencies": [
        ("USDINR=X", "USD / INR"), ("EURINR=X", "EUR / INR"),
        ("GBPINR=X", "GBP / INR"), ("JPYINR=X", "JPY / INR"),
        ("EURUSD=X", "EUR / USD"), ("GBPUSD=X", "GBP / USD"),
    ],
    "Crypto": [
        ("BTC-USD", "Bitcoin"), ("ETH-USD", "Ethereum"),
        ("BNB-USD", "BNB"), ("SOL-USD", "Solana"), ("XRP-USD", "XRP"),
    ],
}

DEFAULT_SYMBOLS = [symbol for group in MARKET_GROUPS.values() for symbol, _ in group]
DISPLAY_NAMES = {symbol: name for group in MARKET_GROUPS.values() for symbol, name in group}

@dataclass(frozen=True)
class Instrument:
    symbol: str
    name: str
    market: str

def get_universe() -> list[Instrument]:
    return [Instrument(symbol, name, market) for market, items in MARKET_GROUPS.items() for symbol, name in items]

def search_universe(query: str) -> list[Instrument]:
    q = query.strip().lower()
    if not q:
        return get_universe()
    return [i for i in get_universe() if q in i.symbol.lower() or q in i.name.lower() or q in i.market.lower()]
