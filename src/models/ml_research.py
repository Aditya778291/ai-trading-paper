"""V0.6 machine-learning research utilities.

Research only: this module deliberately separates out-of-sample evaluation
from the latest-row probability snapshot and makes the time ordering explicit.
It does not place trades or claim profitability.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


DEFAULT_FEATURES = [
    "RSI_14",
    "ATR_14",
    "RELATIVE_VOLUME",
    "MACD",
    "MACD_SIGNAL",
    "MACD_HIST",
    "SMA_20",
    "SMA_50",
    "SMA_200",
    "EMA_12",
    "EMA_26",
]


@dataclass
class MLConfig:
    horizon: int = 5
    threshold: float = 0.0
    train_ratio: float = 0.80
    random_state: int = 42


def add_target(
    df: pd.DataFrame, horizon: int = 5, threshold: float = 0.0
) -> pd.DataFrame:
    """Add a forward-return target without leaking future values into features."""
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    out = df.copy()
    forward_return = out["Close"].shift(-horizon) / out["Close"] - 1.0
    out["FORWARD_RETURN"] = forward_return
    out["TARGET"] = np.where(
        forward_return.notna(),
        (forward_return > threshold).astype(int),
        np.nan,
    )
    return out


def choose_features(
    df: pd.DataFrame, requested: Optional[Iterable[str]] = None
) -> list[str]:
    """Choose numeric, point-in-time features that exist in the dataset."""
    candidates = list(requested or DEFAULT_FEATURES)
    usable = []
    for col in candidates:
        if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
            usable.append(col)

    # Add a few robust price-derived features if the indicator set is sparse.
    for col in ("__RET20_PCT", "__VOL20_PCT", "__SMA20_DIST", "__SMA50_DIST", "__SMA200_DIST"):
        if col in df.columns and pd.api.types.is_numeric_dtype(df[col]) and col not in usable:
            usable.append(col)
    if not usable:
        raise ValueError("No usable numeric ML features were found.")
    return usable


def build_ml_dataset(
    df: pd.DataFrame,
    horizon: int = 5,
    threshold: float = 0.0,
    features: Optional[Iterable[str]] = None,
) -> Tuple[pd.DataFrame, list[str]]:
    """Return labeled rows and the feature names used by the models."""
    data = add_target(df.sort_index(), horizon, threshold)
    feature_cols = choose_features(data, features)
    cols = feature_cols + ["TARGET", "FORWARD_RETURN"]
    clean = data[cols].replace([np.inf, -np.inf], np.nan).dropna()
    clean["TARGET"] = clean["TARGET"].astype(int)
    return clean, feature_cols


def chronological_split(
    data: pd.DataFrame, train_ratio: float = 0.80
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if not 0.50 <= train_ratio < 1.0:
        raise ValueError("train_ratio must be between 0.50 and < 1.0")
    cut = int(len(data) * train_ratio)
    if cut < 20 or len(data) - cut < 5:
        raise ValueError("Not enough labeled observations for a stable chronological split.")
    return data.iloc[:cut].copy(), data.iloc[cut:].copy()


def _calibrated(estimator, X_train, y_train):
    """Time-series-aware probability calibration."""
    class_counts = pd.Series(y_train).value_counts()
    if len(class_counts) < 2:
        raise ValueError("Training data contains only one target class.")
    n_splits = min(3, int(class_counts.min()))
    if n_splits < 2:
        return estimator.fit(X_train, y_train)
    calibrated = CalibratedClassifierCV(
        estimator=estimator,
        method="sigmoid",
        cv=TimeSeriesSplit(n_splits=n_splits),
    )
    return calibrated.fit(X_train, y_train)


def make_models(random_state: int = 42) -> Dict[str, object]:
    """Create baseline research models. XGBoost is optional."""
    models = {
        "Logistic Regression": Pipeline(
            [
                ("scale", StandardScaler()),
                ("model", LogisticRegression(max_iter=2000, random_state=random_state)),
            ]
        ),
        "Random Forest": RandomForestClassifier(
            n_estimators=300,
            min_samples_leaf=5,
            class_weight="balanced_subsample",
            random_state=random_state,
            n_jobs=-1,
        ),
    }
    try:
        from xgboost import XGBClassifier

        models["XGBoost"] = XGBClassifier(
            n_estimators=300,
            max_depth=3,
            learning_rate=0.04,
            subsample=0.85,
            colsample_bytree=0.85,
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=random_state,
            n_jobs=4,
        )
    except Exception:
        pass
    return models


def evaluate_model(model, X_test: pd.DataFrame, y_test: pd.Series) -> dict:
    prob = model.predict_proba(X_test)[:, 1]
    pred = (prob >= 0.5).astype(int)
    result = {
        "Accuracy": accuracy_score(y_test, pred),
        "Precision": precision_score(y_test, pred, zero_division=0),
        "Recall": recall_score(y_test, pred, zero_division=0),
        "Brier Score": brier_score_loss(y_test, prob),
        "Log Loss": log_loss(y_test, prob, labels=[0, 1]),
        "ROC AUC": np.nan,
    }
    if len(np.unique(y_test)) == 2:
        result["ROC AUC"] = roc_auc_score(y_test, prob)
    return result


def feature_importance(model, feature_names: list[str]) -> pd.DataFrame:
    """Extract model-specific importance, falling back to coefficient magnitude."""
    base = model
    if hasattr(model, "calibrated_classifiers_"):
        # Average calibrated sub-estimator importance where possible.
        rows = []
        for calibrated in model.calibrated_classifiers_:
            est = calibrated.estimator
            rows.append(_raw_importance(est, feature_names))
        if rows:
            imp = pd.concat(rows, axis=1).mean(axis=1)
            return pd.DataFrame({"Feature": imp.index, "Importance": imp.values}).sort_values(
                "Importance", ascending=False
            )

    values = _raw_importance(base, feature_names)
    return pd.DataFrame({"Feature": values.index, "Importance": values.values}).sort_values(
        "Importance", ascending=False
    )


def _raw_importance(model, feature_names: list[str]) -> pd.Series:
    if hasattr(model, "feature_importances_"):
        return pd.Series(model.feature_importances_, index=feature_names)
    if hasattr(model, "named_steps") and "model" in model.named_steps:
        estimator = model.named_steps["model"]
        if hasattr(estimator, "coef_"):
            return pd.Series(np.abs(estimator.coef_[0]), index=feature_names)
    if hasattr(model, "coef_"):
        return pd.Series(np.abs(model.coef_[0]), index=feature_names)
    return pd.Series(0.0, index=feature_names)


def run_research(
    df: pd.DataFrame,
    config: Optional[MLConfig] = None,
    features: Optional[Iterable[str]] = None,
) -> dict:
    cfg = config or MLConfig()
    data, feature_names = build_ml_dataset(
        df, cfg.horizon, cfg.threshold, features
    )
    train, test = chronological_split(data, cfg.train_ratio)
    X_train, y_train = train[feature_names], train["TARGET"]
    X_test, y_test = test[feature_names], test["TARGET"]

    results = {}
    fitted = {}
    for name, estimator in make_models(cfg.random_state).items():
        try:
            model = _calibrated(estimator, X_train, y_train)
            results[name] = evaluate_model(model, X_test, y_test)
            results[name]["Train Rows"] = len(train)
            results[name]["Test Rows"] = len(test)
            results[name]["Positive Rate (Test)"] = float(y_test.mean())
            latest_features = (
                df[feature_names]
                .replace([np.inf, -np.inf], np.nan)
                .dropna()
                .tail(1)
            )
            if latest_features.empty:
                raise ValueError("No complete latest feature row is available.")
            results[name]["Latest Probability"] = float(
                model.predict_proba(latest_features)[:, 1][0]
            )
            fitted[name] = model
        except Exception as exc:
            results[name] = {"Error": str(exc)}

    return {
        "data": data,
        "train": train,
        "test": test,
        "features": feature_names,
        "results": pd.DataFrame(results).T,
        "models": fitted,
        "importance": {
            name: feature_importance(model, feature_names)
            for name, model in fitted.items()
        },
    }
