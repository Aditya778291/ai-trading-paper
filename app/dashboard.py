from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.universe import get_universe, load_watchlist, save_watchlist
from src.data.validator import validate_market_data
from src.features.feature_pipeline import build_features
from src.features.scanner import scan_directory as legacy_scan, load_symbol_file, rank_momentum, rank_volume, rank_volatility
from src.features.screener import Rule, ScanDefinition, FIELDS, scan_directory as rule_scan_directory, load_scans, save_scan_collection
from src.visualization.charts import (
    create_candlestick_chart, create_macd_chart, create_rsi_chart,
    create_volume_chart, create_normalized_comparison_chart,
)

st.set_page_config(page_title="AI Market Research", page_icon="📊", layout="wide")
DATA_DIR = ROOT / "data" / "raw"
SAVED_SCANS = ROOT / "configs" / "saved_scans.json"


@st.cache_data
def load_market_data(path: str) -> pd.DataFrame:
    return load_symbol_file(path)


def available_files() -> list[Path]:
    return sorted(list(DATA_DIR.glob("*.parquet")) + list(DATA_DIR.glob("*.csv")))


def file_symbol(path: Path) -> str:
    key = path.stem.replace("_daily", "")
    return {"NSEI": "^NSEI", "NSEBANK": "^NSEBANK", "CNXFIN": "^CNXFIN", "BSESN": "^BSESN"}.get(
        key, key if key.endswith(".NS") else key + ".NS"
    )


def main() -> None:
    st.title("📊 AI Market Research Platform")
    st.caption("V0.5 • Multi-symbol research + custom intelligent screener — descriptive research only.")

    files = available_files()
    if not files:
        st.warning("No local market data found. Run `python -m src.data.downloader` first.")
        st.stop()

    universe = get_universe()
    names = {i.symbol: i.name for i in universe}
    symbol_options = [file_symbol(p) for p in files]

    with st.sidebar:
        st.header("Market Explorer")
        selected_symbol = st.selectbox("Symbol", symbol_options, format_func=lambda s: names.get(s, s))
        selected_file = next(p for p in files if file_symbol(p) == selected_symbol)
        chart_rows = st.slider("Visible candles", 30, 500, 180)
        indicators = st.multiselect(
            "Trend overlays",
            ["SMA_10", "SMA_20", "SMA_50", "SMA_100", "SMA_200", "EMA_9", "EMA_21", "EMA_50"],
            default=["SMA_20", "SMA_50"],
        )
        show_bb = st.checkbox("Show Bollinger Bands", value=False)

    raw = load_market_data(str(selected_file))
    report = validate_market_data(raw)
    if not report.is_valid:
        st.error("Critical data validation errors detected.")
        for error in report.errors:
            st.error(error)
        st.stop()

    features = build_features(raw)
    data = features.tail(chart_rows)
    latest = data.iloc[-1]
    previous = data.iloc[-2] if len(data) > 1 else latest

    st.subheader(names.get(selected_symbol, selected_symbol))
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Latest Close", f"{latest['Close']:,.2f}", f"{latest['Close'] - previous['Close']:+.2f}")
    c2.metric("RSI (14)", f"{latest['RSI_14']:.2f}" if pd.notna(latest["RSI_14"]) else "N/A")
    c3.metric("ATR (14)", f"{latest['ATR_14']:.2f}" if pd.notna(latest["ATR_14"]) else "N/A")
    c4.metric("Relative Volume", f"{latest['RELATIVE_VOLUME']:.2f}x" if pd.notna(latest["RELATIVE_VOLUME"]) else "N/A")
    c5.metric("20D Return", f"{features['Close'].pct_change(20).iloc[-1] * 100:.2f}%" if len(features) > 20 else "N/A")

    tabs = st.tabs(["📈 Chart", "📊 Indicators", "⭐ Watchlist", "🔎 Scanner", "🧠 Custom Screener", "📋 Comparison", "🧪 Data Quality", "🧠 ML Research", "🤖 AI Intelligence"])

    with tabs[0]:
        st.plotly_chart(create_candlestick_chart(data, indicators, show_bb), width="stretch", height=620)
        st.plotly_chart(create_volume_chart(data), width="stretch", height=240)

    with tabs[1]:
        left, right = st.columns(2)
        with left:
            st.plotly_chart(create_rsi_chart(data), width="stretch", height=300)
        with right:
            st.plotly_chart(create_macd_chart(data), width="stretch", height=300)

    with tabs[2]:
        st.subheader("Watchlist")
        watchlist = load_watchlist(ROOT)
        selected = st.multiselect("Symbols", list(names.keys()),
                                  default=[s for s in watchlist if s in names],
                                  format_func=lambda s: names[s])
        if st.button("Save watchlist", type="primary"):
            save_watchlist(ROOT, selected)
            st.success("Watchlist saved.")
            st.rerun()

        rows = []
        for p in files:
            if file_symbol(p) in selected:
                f = build_features(load_market_data(str(p)))
                x = f.iloc[-1]
                rows.append({
                    "Symbol": names.get(file_symbol(p), file_symbol(p)),
                    "Close": x["Close"],
                    "RSI": x["RSI_14"],
                    "Rel Volume": x["RELATIVE_VOLUME"],
                    "20D %": f["Close"].pct_change(20).iloc[-1] * 100 if len(f) > 20 else None,
                })
        if rows:
            st.dataframe(pd.DataFrame(rows), width="stretch")

    with tabs[3]:
        st.subheader("Market Scanner")
        scan = legacy_scan(DATA_DIR)
        scan = scan[scan["Status"] == "OK"] if not scan.empty else scan
        if not scan.empty:
            st.write("🔥 Top Momentum")
            st.dataframe(rank_momentum(scan).head(10), width="stretch")
            st.write("📈 High Relative Volume")
            st.dataframe(rank_volume(scan).head(10), width="stretch")
            st.write("⚡ Highest 20D Volatility")
            st.dataframe(rank_volatility(scan).head(10), width="stretch")
            bullish = int(scan["Above SMA50"].sum())
            st.metric("SMA50 Breadth", f"{bullish}/{len(scan)}", f"{bullish / len(scan) * 100:.1f}%")
        else:
            st.info("No valid datasets available for scanning.")

    with tabs[4]:
        st.subheader("🧠 Intelligent Stock Screener")
        st.caption("Build AND conditions across price, trend, momentum, volume, return and volatility.")

        left, right = st.columns([3, 1])
        with left:
            rule_count = st.number_input("Number of conditions", min_value=1, max_value=8, value=3, step=1)
        with right:
            scan_name = st.text_input("Scan name", value="My Scan")

        rules = []
        for i in range(int(rule_count)):
            a, b, c = st.columns([2, 1, 1])
            with a:
                field = st.selectbox("Metric", list(FIELDS.keys()), key=f"field_{i}")
            with b:
                op = st.selectbox("Operator", [">", ">=", "<", "<=", "==", "!="], key=f"op_{i}")
            with c:
                default = {
                    "RSI (14)": 70, "Relative Volume": 1.5,
                    "20D Return (%)": 0, "Volatility (20D, %)": 5,
                }.get(field, 0)
                value = st.number_input("Value", value=float(default), key=f"value_{i}")
            rules.append(Rule(field, op, value))

        col_run, col_save = st.columns(2)
        run = col_run.button("🔎 Run screener", type="primary")
        save = col_save.button("💾 Save scan")

        if save:
            scans = load_scans(SAVED_SCANS)
            scans = [s for s in scans if s.name != scan_name]
            scans.append(ScanDefinition(scan_name, rules))
            save_scan_collection(SAVED_SCANS, scans)
            st.success(f"Saved scan: {scan_name}")

        if run:
            results = rule_scan_directory(DATA_DIR, rules)
            matches = results[results["Match"] == True].copy() if not results.empty else results
            st.metric("Matches", len(matches))
            if matches.empty:
                st.info("No symbols currently satisfy every condition.")
            else:
                st.dataframe(matches.drop(columns=["Match"], errors="ignore"), width="stretch")

        st.divider()
        saved = load_scans(SAVED_SCANS)
        if saved:
            st.write("Saved scans")
            for saved_scan in saved:
                st.write(f"**{saved_scan.name}** — " + " AND ".join(
                    f"{r.field} {r.operator} {r.value:g}" for r in saved_scan.rules
                ))

    with tabs[5]:
        st.subheader("Multi-Symbol Comparison")
        compare_symbols = st.multiselect("Choose downloaded symbols", symbol_options,
                                         default=symbol_options[:min(4, len(symbol_options))],
                                         format_func=lambda s: names.get(s, s))
        series_map = {}
        for s in compare_symbols:
            p = next((p for p in files if file_symbol(p) == s), None)
            if p:
                series_map[names.get(s, s)] = load_market_data(str(p))["Close"]
        if series_map:
            st.plotly_chart(create_normalized_comparison_chart(series_map), width="stretch", height=480)

    with tabs[6]:
        st.subheader("Data Quality Status")
        st.success(report.summary())
        for warning in report.warnings:
            st.warning(warning)
        st.write("Dataset rows:", len(raw))
        st.write("Date range:", f"{raw.index.min().date()} → {raw.index.max().date()}")
        st.write("Columns:", ", ".join(raw.columns))

    st.divider()
    st.caption("Research outputs are descriptive. They are not predictions, investment recommendations, or guarantees of future performance.")


if __name__ == "__main__":
    main()


# V0.6 — Machine Learning Research
if "🧠 ML Research" in tabs:
    with tabs[-1]:
        st.subheader("Machine Learning Research")
        st.caption(
            "Research-only models with chronological out-of-sample evaluation. "
            "Probabilities are not trading guarantees."
        )
        try:
            from src.models.ml_research import MLConfig, run_research

            ml_symbol = st.selectbox("ML symbol", symbols, key="ml_symbol")
            ml_horizon = st.slider("Prediction horizon (trading days)", 1, 20, 5, key="ml_horizon")
            ml_threshold_pct = st.number_input(
                "Forward-return threshold (%)", value=0.0, step=0.25, key="ml_threshold"
            )
            ml_train_ratio = st.slider(
                "Chronological train ratio", 0.60, 0.90, 0.80, 0.05, key="ml_train_ratio"
            )

            if st.button("Run ML Research", type="primary"):
                ml_df = load_symbol_data(ml_symbol)
                cfg = MLConfig(
                    horizon=ml_horizon,
                    threshold=ml_threshold_pct / 100.0,
                    train_ratio=ml_train_ratio,
                )
                report = run_research(ml_df, cfg)
                st.session_state["ml_report"] = report

            report = st.session_state.get("ml_report")
            if report is not None:
                st.markdown("### Out-of-sample model results")
                st.dataframe(
                    report["results"].round(4),
                    use_container_width=True,
                )

                st.markdown("### Latest-row probability snapshot")
                latest = []
                for name, row in report["results"].iterrows():
                    if "Latest Probability" in row and pd.notna(row["Latest Probability"]):
                        latest.append({
                            "Model": name,
                            "Probability of target class": row["Latest Probability"],
                        })
                if latest:
                    st.dataframe(pd.DataFrame(latest).round(4), use_container_width=True)

                st.markdown("### Feature importance")
                model_names = list(report["importance"].keys())
                if model_names:
                    chosen = st.selectbox("Importance model", model_names, key="ml_importance_model")
                    st.dataframe(
                        report["importance"][chosen].head(15).round(4),
                        use_container_width=True,
                    )

                st.info(
                    f"Labeled rows: {len(report['data'])} · "
                    f"Train: {len(report['train'])} · Test: {len(report['test'])} · "
                    f"Features: {len(report['features'])}"
                )
        except Exception as exc:
            st.error(f"ML research error: {exc}")


# V0.7 — AI Intelligence Engine
with tabs[-1]:
    st.subheader("AI Intelligence Engine")
    st.caption(
        "Transparent ensemble research layer: model agreement, confidence, "
        "market regime, explanations, and model-health diagnostics."
    )
    try:
        from src.ai.intelligence import (
            IntelligenceConfig,
            classify_market_regime,
            ensemble_signal,
            explain_signal,
            model_health,
        )

        report = st.session_state.get("ml_report")
        if report is None:
            st.info("Run the ML Research tab first. V0.7 uses its out-of-sample diagnostics and model probabilities.")
        else:
            intelligence = ensemble_signal(report["results"], IntelligenceConfig())
            regime = classify_market_regime(load_symbol_data(st.session_state.get("ml_symbol", symbols[0])))

            c1, c2, c3 = st.columns(3)
            c1.metric("Ensemble Signal", intelligence["signal"])
            c2.metric("Latest Probability", f"{intelligence['probability']:.1%}" if pd.notna(intelligence["probability"]) else "N/A")
            c3.metric("Confidence", f"{intelligence['confidence']:.0f}%")

            st.markdown("### Market Regime")
            st.write(
                f"**{regime['regime']}** · Trend: {regime['trend']} · "
                f"Volatility: {regime['volatility']}"
            )

            st.markdown("### Signal Explanation")
            explanation = explain_signal(report["importance"], top_n=8)
            if not explanation.empty:
                st.dataframe(explanation.round(4), use_container_width=True)
            else:
                st.info("No feature-importance data is available.")

            st.markdown("### Model Health")
            health = model_health(report["results"])
            if not health.empty:
                st.dataframe(health.round(4), use_container_width=True)

            st.warning(
                "Confidence is a model-agreement diagnostic, not a probability of profit. "
                "Backtesting and execution costs are handled in later milestones."
            )
    except Exception as exc:
        st.error(f"AI Intelligence error: {exc}")


# ---------------- V0.8 Scientific Backtesting ----------------
with st.expander("📈 V0.8 Scientific Backtesting", expanded=False):
    st.caption(
        "Research-only backtesting with next-bar execution, transaction costs, "
        "slippage, risk controls, walk-forward windows, and Monte Carlo trade bootstrapping."
    )
    try:
        from src.backtesting.backtester import (
            BacktestConfig, backtest_long_only, technical_signal,
            walk_forward_backtest, monte_carlo_trade_returns, monte_carlo_summary
        )
        bt_symbol = st.selectbox(
            "Backtest symbol",
            symbols if "symbols" in globals() and symbols else ["RELIANCE"],
            key="v08_bt_symbol",
        )
        bt_strategy = st.selectbox(
            "Strategy", ["SMA Crossover", "RSI + Trend", "Trend"], key="v08_bt_strategy"
        )
        c1, c2, c3 = st.columns(3)
        commission = c1.number_input("Commission (bps/side)", 0.0, 100.0, 5.0, 0.5)
        slippage = c2.number_input("Slippage (bps/side)", 0.0, 100.0, 5.0, 0.5)
        position_fraction = c3.slider("Position size (% equity)", 10, 100, 100, 5) / 100.0
        c4, c5, c6 = st.columns(3)
        stop_loss = c4.number_input("Stop loss (%)", 0.0, 50.0, 2.0, 0.25) / 100.0
        take_profit = c5.number_input("Take profit (%)", 0.0, 100.0, 4.0, 0.25) / 100.0
        wf_splits = c6.number_input("Walk-forward splits", 2, 10, 5, 1)
        mc_sims = st.number_input("Monte Carlo simulations", 100, 20000, 2000, 100)

        if st.button("Run V0.8 Backtest", type="primary", key="v08_run"):
            data = load_symbol_data(bt_symbol)
            signal = technical_signal(data, bt_strategy)
            cfg = BacktestConfig(
                position_fraction=position_fraction,
                commission_bps=commission,
                slippage_bps=slippage,
                stop_loss_pct=stop_loss if stop_loss > 0 else None,
                take_profit_pct=take_profit if take_profit > 0 else None,
            )
            result = backtest_long_only(data, signal, cfg)
            st.subheader("Performance")
            metrics_view = {k: v for k, v in result.metrics.items() if k not in {"Initial Equity", "Final Equity"}}
            st.dataframe(pd.DataFrame([metrics_view]), use_container_width=True)
            if not result.equity_curve.empty:
                st.line_chart(result.equity_curve["Equity"], use_container_width=True)
            st.subheader("Trade Log")
            st.dataframe(result.trades, use_container_width=True)

            st.subheader("Walk-Forward")
            wf = walk_forward_backtest(
                data, lambda train: technical_signal(train, bt_strategy), cfg, int(wf_splits)
            )
            st.dataframe(wf, use_container_width=True)

            if not result.trades.empty:
                mc = monte_carlo_trade_returns(result.trades, int(mc_sims))
                st.subheader("Monte Carlo")
                st.dataframe(pd.DataFrame([monte_carlo_summary(mc)]), use_container_width=True)
                st.caption(
                    "Monte Carlo is a bootstrap of completed trade returns; it is not a forecast "
                    "and does not establish future profitability."
                )
            else:
                st.info("No completed trades; Monte Carlo requires at least one trade.")
    except Exception as exc:
        st.error(f"Backtesting unavailable: {exc}")


# ---------------- V0.9 Advanced Paper Trading ----------------
with st.expander("💼 V0.9 Advanced Paper Trading", expanded=False):
    st.caption(
        "Simulated portfolio only. Orders are filled against historical bars; "
        "there is no broker connectivity or live execution."
    )
    try:
        from src.paper_trading.engine import replay_decisions, decision_replay_table
        pt_symbol = st.selectbox(
            "Paper-trading symbol",
            symbols if "symbols" in globals() and symbols else ["RELIANCE"],
            key="v09_symbol",
        )
        pt_strategy = st.selectbox(
            "Signal strategy",
            ["SMA Crossover", "RSI + Trend", "Trend"],
            key="v09_strategy",
        )
        p1, p2, p3 = st.columns(3)
        pt_cash = p1.number_input("Starting virtual cash", 1000.0, 10_000_000.0, 100_000.0, 5000.0)
        pt_cost = p2.number_input("Commission (bps/side)", 0.0, 100.0, 5.0, 0.5)
        pt_size = p3.slider("Position size (% cash)", 10, 100, 100, 5) / 100.0

        if st.button("Replay Paper Trades", type="primary", key="v09_run"):
            from src.backtesting.backtester import technical_signal
            pt_data = load_symbol_data(pt_symbol)
            pt_signal = technical_signal(pt_data, pt_strategy)
            portfolio, pt_equity = replay_decisions(
                pt_data, pt_signal, pt_symbol, pt_cash, pt_cost, pt_size
            )
            final_equity = float(pt_equity["Equity"].iloc[-1]) if not pt_equity.empty else portfolio.cash
            st.metric("Final virtual equity", f"${final_equity:,.2f}")
            st.dataframe(pt_equity, use_container_width=True)
            st.subheader("Positions")
            st.dataframe(
                pd.DataFrame([vars(x) for x in portfolio.positions.values()]),
                use_container_width=True,
            )
            st.subheader("Order & Decision Journal")
            st.dataframe(decision_replay_table(portfolio), use_container_width=True)
            st.caption("Replay is historical simulation and does not represent live fills or future results.")
    except Exception as exc:
        st.error(f"Paper trading unavailable: {exc}")
