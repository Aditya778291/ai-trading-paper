from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json
import operator

import pandas as pd

from src.features.feature_pipeline import build_features
from src.features.scanner import load_symbol_file
from src.data.validator import validate_market_data


OPERATORS = {
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
}

FIELDS = {
    "Close": "Close",
    "RSI (14)": "RSI_14",
    "Relative Volume": "RELATIVE_VOLUME",
    "20D Return (%)": "__RET20_PCT",
    "Volatility (20D, %)": "__VOL20_PCT",
    "SMA 20 Distance (%)": "__SMA20_DIST",
    "SMA 50 Distance (%)": "__SMA50_DIST",
    "SMA 200 Distance (%)": "__SMA200_DIST",
    "ATR (14)": "ATR_14",
}


@dataclass
class Rule:
    field: str
    operator: str
    value: float


@dataclass
class ScanDefinition:
    name: str
    rules: list[Rule] = field(default_factory=list)


def prepare_features(raw: pd.DataFrame) -> pd.DataFrame:
    f = build_features(raw).copy()
    f["__RET20_PCT"] = f["Close"].pct_change(20) * 100
    f["__VOL20_PCT"] = f["Close"].pct_change().rolling(20).std() * 100
    for n in (20, 50, 200):
        col = f"SMA_{n}"
        f[f"__SMA{n}_DIST"] = (f["Close"] / f[col] - 1) * 100
    return f


def apply_rules(row: pd.Series, rules: list[Rule]) -> tuple[bool, list[str]]:
    reasons = []
    for rule in rules:
        column = FIELDS[rule.field]
        value = row.get(column)
        if pd.isna(value):
            return False, [f"{rule.field}: unavailable"]
        try:
            ok = OPERATORS[rule.operator](float(value), float(rule.value))
        except (TypeError, ValueError):
            return False, [f"{rule.field}: invalid value"]
        reasons.append(f"{rule.field} {rule.operator} {rule.value:g}")
        if not ok:
            return False, reasons
    return True, reasons


def scan_symbol(raw: pd.DataFrame, symbol: str, rules: list[Rule]) -> dict[str, Any]:
    report = validate_market_data(raw)
    if not report.is_valid:
        return {"Symbol": symbol, "Match": False, "Status": "Invalid data"}

    f = prepare_features(raw)
    if f.empty:
        return {"Symbol": symbol, "Match": False, "Status": "No data"}

    row = f.iloc[-1]
    match, reasons = apply_rules(row, rules)

    return {
        "Symbol": symbol,
        "Match": match,
        "Status": "OK",
        "Close": float(row["Close"]),
        "RSI": float(row["RSI_14"]) if pd.notna(row["RSI_14"]) else None,
        "Rel Volume": float(row["RELATIVE_VOLUME"]) if pd.notna(row["RELATIVE_VOLUME"]) else None,
        "20D Return %": float(row["__RET20_PCT"]) if pd.notna(row["__RET20_PCT"]) else None,
        "Volatility %": float(row["__VOL20_PCT"]) if pd.notna(row["__VOL20_PCT"]) else None,
        "Reasons": " AND ".join(reasons),
    }


def scan_directory(data_dir: str | Path, rules: list[Rule]) -> pd.DataFrame:
    paths = sorted(list(Path(data_dir).glob("*.parquet")) + list(Path(data_dir).glob("*.csv")))
    rows = []
    for path in paths:
        key = path.stem.replace("_daily", "")
        symbol = {
            "NSEI": "^NSEI", "NSEBANK": "^NSEBANK",
            "CNXFIN": "^CNXFIN", "BSESN": "^BSESN"
        }.get(key, key if key.endswith(".NS") else key + ".NS")
        try:
            rows.append(scan_symbol(load_symbol_file(path), symbol, rules))
        except Exception as exc:
            rows.append({"Symbol": symbol, "Match": False, "Status": f"Error: {exc}"})
    return pd.DataFrame(rows)


def save_scan(path: str | Path, scan: ScanDefinition) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "name": scan.name,
        "rules": [r.__dict__ for r in scan.rules]
    }, indent=2), encoding="utf-8")


def load_scans(path: str | Path) -> list[ScanDefinition]:
    p = Path(path)
    if not p.exists():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return [
            ScanDefinition(
                name=item["name"],
                rules=[Rule(**r) for r in item.get("rules", [])]
            )
            for item in raw
        ]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return []


def save_scan_collection(path: str | Path, scans: list[ScanDefinition]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps([
        {"name": s.name, "rules": [r.__dict__ for r in s.rules]}
        for s in scans
    ], indent=2), encoding="utf-8")
