from __future__ import annotations

from pathlib import Path
import argparse

import pandas as pd
import yfinance as yf

from src.data.validator import validate_market_data
from src.utils.config import PROJECT_ROOT, load_config
from src.utils.logger import get_logger


def download_historical_data(symbol: str, period: str, interval: str) -> pd.DataFrame:
    if not symbol.strip():
        raise ValueError("symbol must not be empty.")

    data = yf.download(
        tickers=symbol,
        period=period,
        interval=interval,
        auto_adjust=False,
        progress=False,
    )
    if data.empty:
        raise RuntimeError(f"No data returned for symbol: {symbol}")

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    required = ["Open", "High", "Low", "Close", "Volume"]
    missing = [col for col in required if col not in data.columns]
    if missing:
        raise RuntimeError(f"Downloaded data missing expected columns: {missing}")

    result = data[required].copy()
    result.index = pd.to_datetime(result.index)
    return result


def save_data(df: pd.DataFrame, output_dir: str | Path, symbol: str, file_format: str) -> Path:
    destination = Path(output_dir)
    if not destination.is_absolute():
        destination = PROJECT_ROOT / destination
    destination.mkdir(parents=True, exist_ok=True)

    safe_symbol = symbol.replace("^", "").replace("/", "_")
    output_path = destination / f"{safe_symbol}_daily.{file_format}"

    if file_format == "parquet":
        df.to_parquet(output_path)
    elif file_format == "csv":
        df.to_csv(output_path)
    else:
        raise ValueError("file_format must be 'parquet' or 'csv'.")

    return output_path


def download_universe(symbols: list[str], period: str, interval: str,
                      output_dir: str | Path, file_format: str, logger) -> dict[str, str]:
    results: dict[str, str] = {}
    for symbol in symbols:
        try:
            logger.info("Downloading %s", symbol)
            df = download_historical_data(symbol, period, interval)
            report = validate_market_data(df)
            for warning in report.warnings:
                logger.warning("%s: %s", symbol, warning)
            if not report.is_valid:
                for error in report.errors:
                    logger.error("%s: %s", symbol, error)
                results[symbol] = "validation_failed"
                continue
            path = save_data(df, output_dir, symbol, file_format)
            results[symbol] = str(path)
            logger.info("%s: saved %d rows", symbol, len(df))
        except Exception as exc:
            logger.exception("Failed %s: %s", symbol, exc)
            results[symbol] = f"error: {exc}"
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Download market data.")
    parser.add_argument("--symbols", nargs="*", help="Yahoo Finance symbols. Defaults to config universe.")
    args = parser.parse_args()

    config = load_config()
    logger = get_logger(__name__, config["logging"]["level"],
                        PROJECT_ROOT / config["logging"]["file"])
    data_cfg = config["data"]
    symbols = args.symbols or data_cfg.get("symbols", [data_cfg["symbol"]])

    results = download_universe(
        symbols, data_cfg["period"], data_cfg["interval"],
        data_cfg["output_dir"], data_cfg["file_format"], logger
    )
    failed = [s for s, status in results.items() if status != "ok" and not status.endswith(".parquet") and not status.endswith(".csv")]
    logger.info("Batch download complete: %d succeeded, %d failed",
                len(symbols) - len(failed), len(failed))
    if failed:
        raise RuntimeError(f"Some downloads failed: {failed}")


if __name__ == "__main__":
    main()
