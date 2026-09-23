from __future__ import annotations

from pathlib import Path
import pandas as pd

from src.features.feature_pipeline import build_features
from src.data.validator import validate_market_data


def load_symbol_file(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if p.suffix == ".parquet":
        return pd.read_parquet(p)
    return pd.read_csv(p, index_col=0, parse_dates=True)


def scan_dataset(raw: pd.DataFrame, symbol: str) -> dict:
    report = validate_market_data(raw)
    if not report.is_valid:
        return {"Symbol": symbol, "Status": "Invalid", "Errors": "; ".join(report.errors)}

    f = build_features(raw)
    if len(f) < 2:
        return {"Symbol": symbol, "Status": "Insufficient data"}

    latest = f.iloc[-1]
    prev = f.iloc[-2]
    close = float(latest["Close"])

    def num(col):
        value = latest.get(col)
        return float(value) if pd.notna(value) else float("nan")

    sma50 = num("SMA_50")
    rsi = num("RSI_14")
    relvol = num("RELATIVE_VOLUME")
    vol20 = num("ROLLING_VOL_20")
    ret20 = float(f["Close"].pct_change(20).iloc[-1]) if len(f) > 20 else float("nan")

    return {
        "Symbol": symbol,
        "Status": "OK",
        "Close": close,
        "1D %": (close / float(prev["Close"]) - 1) * 100,
        "20D %": ret20 * 100 if pd.notna(ret20) else float("nan"),
        "RSI": rsi,
        "Rel Volume": relvol,
        "Volatility": vol20 * 100 if pd.notna(vol20) else float("nan"),
        "Above SMA50": bool(pd.notna(sma50) and close > sma50),
    }


def scan_directory(data_dir: str | Path) -> pd.DataFrame:
    paths = sorted(list(Path(data_dir).glob("*.parquet")) + list(Path(data_dir).glob("*.csv")))
    rows = []
    for path in paths:
        symbol = path.stem.replace("_daily", "")
        # Reattach Yahoo-style index symbols where possible.
        symbol = {"NSEI": "^NSEI", "NSEBANK": "^NSEBANK",
                  "CNXFIN": "^CNXFIN", "BSESN": "^BSESN"}.get(symbol, symbol + ".NS" if not symbol.endswith(".NS") else symbol)
        try:
            rows.append(scan_dataset(load_symbol_file(path), symbol))
        except Exception as exc:
            rows.append({"Symbol": symbol, "Status": f"Error: {exc}"})
    return pd.DataFrame(rows)


def rank_momentum(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "20D %" not in df:
        return df
    return df.sort_values("20D %", ascending=False, na_position="last").reset_index(drop=True)


def rank_volume(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "Rel Volume" not in df:
        return df
    return df.sort_values("Rel Volume", ascending=False, na_position="last").reset_index(drop=True)


def rank_volatility(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "Volatility" not in df:
        return df
    return df.sort_values("Volatility", ascending=False, na_position="last").reset_index(drop=True)
