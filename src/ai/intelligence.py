"""V0.7 AI Intelligence Engine.

Research layer built on V0.6 model outputs. It combines model probabilities,
classifies a broad market regime, produces a transparent confidence score,
explains the signal using feature importance, and reports model health.

No execution or profitability claims are made here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd


@dataclass
class IntelligenceConfig:
    bullish_threshold: float = 0.60
    bearish_threshold: float = 0.40
    agreement_weight: float = 0.40
    probability_weight: float = 0.60


def classify_market_regime(df: pd.DataFrame) -> dict:
    """Classify trend/volatility regime from point-in-time market features."""
    if df.empty or "Close" not in df.columns:
        return {"regime": "Unknown", "trend": "Unknown", "volatility": "Unknown"}

    close = df["Close"].astype(float)
    latest = float(close.iloc[-1])
    sma20 = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else np.nan
    sma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else np.nan
    ret20 = float(close.pct_change(20).iloc[-1]) if len(close) > 20 else np.nan
    vol20 = float(close.pct_change().rolling(20).std().iloc[-1]) if len(close) > 20 else np.nan

    if pd.notna(sma50):
        if latest > sma50 and pd.notna(ret20) and ret20 > 0:
            trend = "Bullish"
        elif latest < sma50 and pd.notna(ret20) and ret20 < 0:
            trend = "Bearish"
        else:
            trend = "Sideways"
    elif pd.notna(sma20):
        trend = "Bullish" if latest > sma20 else "Bearish"
    else:
        trend = "Unknown"

    if pd.notna(vol20):
        # Relative classification, using annualized daily volatility.
        annualized = vol20 * np.sqrt(252)
        volatility = "High" if annualized >= 0.30 else ("Low" if annualized <= 0.15 else "Normal")
    else:
        volatility = "Unknown"

    if trend == "Bullish" and volatility == "High":
        regime = "Bullish / High Volatility"
    elif trend == "Bearish" and volatility == "High":
        regime = "Bearish / High Volatility"
    elif trend == "Bullish":
        regime = "Bullish"
    elif trend == "Bearish":
        regime = "Bearish"
    elif trend == "Sideways":
        regime = "Sideways"
    else:
        regime = "Unknown"

    return {
        "regime": regime,
        "trend": trend,
        "volatility": volatility,
        "sma20": sma20,
        "sma50": sma50,
        "return_20d": ret20,
        "annualized_volatility": annualized if pd.notna(vol20) else np.nan,
    }


def ensemble_signal(
    model_results: pd.DataFrame,
    config: Optional[IntelligenceConfig] = None,
) -> dict:
    """Aggregate latest probabilities across successfully evaluated models."""
    cfg = config or IntelligenceConfig()
    if model_results is None or model_results.empty:
        return {"signal": "Neutral", "probability": np.nan, "confidence": 0.0, "agreement": 0.0}

    if "Latest Probability" not in model_results.columns:
        return {"signal": "Neutral", "probability": np.nan, "confidence": 0.0, "agreement": 0.0}

    probs = pd.to_numeric(model_results["Latest Probability"], errors="coerce").dropna()
    if probs.empty:
        return {"signal": "Neutral", "probability": np.nan, "confidence": 0.0, "agreement": 0.0}

    mean_prob = float(probs.mean())
    bullish_votes = int((probs >= 0.5).sum())
    bearish_votes = int((probs < 0.5).sum())
    agreement = max(bullish_votes, bearish_votes) / len(probs)

    # Confidence is intentionally transparent: distance from 0.5 + agreement.
    directional_strength = abs(mean_prob - 0.5) * 2.0
    confidence = 100.0 * (
        cfg.probability_weight * directional_strength
        + cfg.agreement_weight * agreement
    )
    if mean_prob >= cfg.bullish_threshold:
        signal = "Bullish"
    elif mean_prob <= cfg.bearish_threshold:
        signal = "Bearish"
    else:
        signal = "Neutral"

    return {
        "signal": signal,
        "probability": mean_prob,
        "confidence": float(np.clip(confidence, 0, 100)),
        "agreement": agreement,
        "bullish_models": bullish_votes,
        "bearish_models": bearish_votes,
        "model_count": len(probs),
    }


def explain_signal(
    importance_by_model: Dict[str, pd.DataFrame],
    top_n: int = 5,
) -> pd.DataFrame:
    """Average normalized feature importance across available models."""
    frames = []
    for model_name, table in importance_by_model.items():
        if table is None or table.empty:
            continue
        t = table[["Feature", "Importance"]].copy()
        t["Importance"] = pd.to_numeric(t["Importance"], errors="coerce").fillna(0)
        total = t["Importance"].sum()
        if total > 0:
            t["Importance"] /= total
        t["Model"] = model_name
        frames.append(t)
    if not frames:
        return pd.DataFrame(columns=["Feature", "Importance", "Models"])
    all_imp = pd.concat(frames, ignore_index=True)
    summary = (
        all_imp.groupby("Feature", as_index=False)["Importance"]
        .mean()
        .sort_values("Importance", ascending=False)
        .head(top_n)
    )
    counts = all_imp.groupby("Feature")["Model"].nunique()
    summary["Models"] = summary["Feature"].map(counts)
    return summary.reset_index(drop=True)


def model_health(model_results: pd.DataFrame) -> pd.DataFrame:
    """Create a compact model-health table from V0.6 out-of-sample diagnostics."""
    if model_results is None or model_results.empty:
        return pd.DataFrame()

    rows = []
    for name, row in model_results.iterrows():
        err = row.get("Error")
        if pd.notna(err) if err is not None else False:
            rows.append({"Model": name, "Status": "Error", "Health": "Unavailable"})
            continue

        auc = row.get("ROC AUC", np.nan)
        brier = row.get("Brier Score", np.nan)
        logloss = row.get("Log Loss", np.nan)
        agreement_prob = row.get("Latest Probability", np.nan)

        # Diagnostic status only; thresholds are not profitability claims.
        checks = []
        if pd.notna(auc):
            checks.append(float(auc) >= 0.55)
        if pd.notna(brier):
            checks.append(float(brier) <= 0.25)
        if pd.notna(logloss):
            checks.append(float(logloss) <= 0.693)

        health = "Good" if checks and sum(checks) / len(checks) >= 2/3 else (
            "Watch" if checks else "Insufficient Data"
        )
        rows.append({
            "Model": name,
            "Status": "OK",
            "Health": health,
            "ROC AUC": auc,
            "Brier Score": brier,
            "Log Loss": logloss,
            "Latest Probability": agreement_prob,
        })
    return pd.DataFrame(rows)
