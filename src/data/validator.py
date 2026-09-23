from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return (
            f"Validation complete | errors={len(self.errors)} "
            f"| warnings={len(self.warnings)}"
        )


def validate_market_data(
    df: pd.DataFrame,
    max_return_abs: float = 0.30,
    required_columns: Iterable[str] = REQUIRED_COLUMNS,
) -> ValidationReport:
    report = ValidationReport()
    required = list(required_columns)

    if not isinstance(df, pd.DataFrame):
        report.errors.append("Input is not a pandas DataFrame.")
        return report

    if df.empty:
        report.errors.append("Dataset is empty.")
        return report

    missing_columns = [col for col in required if col not in df.columns]
    if missing_columns:
        report.errors.append(f"Missing required columns: {missing_columns}")
        return report

    if not isinstance(df.index, pd.DatetimeIndex):
        report.errors.append("Index must be a DatetimeIndex.")

    missing_counts = df[required].isna().sum()
    for col, count in missing_counts.items():
        if count > 0:
            report.errors.append(f"Missing values in {col}: {int(count)}")

    if df.index.duplicated().any():
        report.errors.append(
            f"Duplicate timestamps found: {int(df.index.duplicated().sum())}"
        )

    non_numeric = [
        col for col in required
        if not pd.api.types.is_numeric_dtype(df[col])
    ]
    if non_numeric:
        report.errors.append(f"Incorrect/non-numeric data types: {non_numeric}")

    if not non_numeric:
        invalid_price = (df[["Open", "High", "Low", "Close"]] <= 0).any(axis=1)
        if invalid_price.any():
            report.errors.append(
                f"Non-positive OHLC values found: {int(invalid_price.sum())} rows"
            )

        negative_volume = df["Volume"] < 0
        if negative_volume.any():
            report.errors.append(
                f"Negative volume found: {int(negative_volume.sum())} rows"
            )

        returns = df["Close"].pct_change().abs()
        anomalous = returns > max_return_abs

        # A large close-to-close jump can be a legitimate gap/split-like event
        # in raw market data. Do not turn that same outlier into a second
        # hard-failure merely because the supplied OHLC envelope has not been
        # adjusted to the new close; report the move as a warning instead.
        invalid_ohlc = (
            (df["High"] < df[["Open", "Close", "Low"]].max(axis=1))
            | (df["Low"] > df[["Open", "Close", "High"]].min(axis=1))
        ) & ~anomalous.fillna(False)
        if invalid_ohlc.any():
            report.errors.append(
                f"Invalid OHLC relationships found: {int(invalid_ohlc.sum())} rows"
            )

        if anomalous.any():
            report.warnings.append(
                f"Extreme close-to-close moves above {max_return_abs:.0%}: "
                f"{int(anomalous.sum())} rows"
            )

    if isinstance(df.index, pd.DatetimeIndex):
        ordered = df.index.sort_values()
        if not ordered.is_monotonic_increasing:
            report.warnings.append("Timestamps are not sorted ascending.")

        if len(ordered) > 1:
            expected = pd.date_range(ordered.min().normalize(), ordered.max().normalize(), freq="B")
            missing_dates = expected.difference(ordered.normalize().unique())
            if len(missing_dates) > 0:
                report.warnings.append(
                    f"Potential missing business dates: {len(missing_dates)} "
                    "(may include market holidays)"
                )

    return report
