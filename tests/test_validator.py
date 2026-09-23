import pandas as pd

from src.data.validator import validate_market_data


def make_valid_data() -> pd.DataFrame:
    index = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-05"])
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0],
            "High": [103.0, 104.0, 105.0],
            "Low": [99.0, 100.0, 101.0],
            "Close": [102.0, 103.0, 104.0],
            "Volume": [1000, 1100, 1200],
        },
        index=index,
    )


def test_valid_data_has_no_errors():
    report = validate_market_data(make_valid_data())
    assert report.is_valid


def test_missing_values_are_errors():
    df = make_valid_data()
    df.loc[df.index[0], "Close"] = None
    report = validate_market_data(df)
    assert not report.is_valid
    assert any("Missing values" in error for error in report.errors)


def test_invalid_ohlc_is_detected():
    df = make_valid_data()
    df.loc[df.index[0], "High"] = 90.0
    report = validate_market_data(df)
    assert not report.is_valid
    assert any("Invalid OHLC" in error for error in report.errors)


def test_duplicate_timestamp_is_detected():
    df = make_valid_data()
    df = pd.concat([df, df.iloc[[0]]])
    report = validate_market_data(df)
    assert not report.is_valid
    assert any("Duplicate timestamps" in error for error in report.errors)


def test_extreme_move_is_warning():
    df = make_valid_data()
    df.loc[df.index[2], "Close"] = 200.0
    report = validate_market_data(df, max_return_abs=0.30)
    assert report.is_valid
    assert report.warnings
