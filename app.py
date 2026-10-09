import os
from datetime import datetime, timezone

import ccxt
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Crypto Signal Lab", page_icon="📡", layout="wide")

st.title("📡 Crypto Signal Lab")
st.caption("Educational crypto signal dashboard • Bybit public market data • No trades are placed")

st.warning(
    "Signals are rule-based estimates, not financial advice or guaranteed predictions. "
    "Test on paper first. This app does not connect trading permissions or place orders."
)

DEFAULT_SYMBOLS = [
    "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT",
    "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "LINK/USDT", "TON/USDT",
    "SUI/USDT", "TRX/USDT", "DOT/USDT", "LTC/USDT", "BCH/USDT",
    "UNI/USDT", "NEAR/USDT", "APT/USDT", "ICP/USDT", "ETC/USDT",
    "FIL/USDT", "ATOM/USDT", "ARB/USDT", "OP/USDT", "INJ/USDT",
    "AAVE/USDT", "RENDER/USDT", "FET/USDT", "WIF/USDT", "PEPE/USDT",
    "SEI/USDT", "IMX/USDT", "MKR/USDT", "GRT/USDT", "ALGO/USDT",
    "VET/USDT", "FTM/USDT", "SAND/USDT", "MANA/USDT", "THETA/USDT",
    "EOS/USDT", "FLOW/USDT", "XTZ/USDT", "CRV/USDT", "DYDX/USDT",
    "JUP/USDT", "PYTH/USDT", "TIA/USDT", "WLD/USDT", "ONDO/USDT"
]

@st.cache_resource
def exchange_client():
    return ccxt.bybit({"enableRateLimit": True, "options": {"defaultType": "spot"}})

def fetch_ohlcv(symbol, timeframe, limit=220):
    ex = exchange_client()
    rows = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"])
    df["time"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    return df

def add_indicators(df):
    df = df.copy()
    df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()
    delta = df["close"].diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss.replace(0, pd.NA)
    df["rsi"] = 100 - (100 / (1 + rs))
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs()
    ], axis=1).max(axis=1)
    df["atr"] = tr.ewm(alpha=1/14, adjust=False).mean()
    df["vol_sma20"] = df["volume"].rolling(20).mean()
    return df

def analyze_symbol(symbol, entry_tf="1h", bias_tf="1d"):
    entry = add_indicators(fetch_ohlcv(symbol, entry_tf))
    daily = add_indicators(fetch_ohlcv(symbol, bias_tf, 220))
    e = entry.iloc[-1]
    d = daily.iloc[-1]
    prev = entry.iloc[-2]
    recent = entry.iloc[-21:-1]
    swing_high = float(recent["high"].max())
    swing_low = float(recent["low"].min())
    price = float(e["close"])
    atr = float(e["atr"])
    if pd.isna(atr) or atr <= 0:
        raise ValueError("Not enough candle data to calculate ATR")

    daily_bull = d["close"] > d["ema50"] and d["ema50"] > d["ema200"]
    daily_bear = d["close"] < d["ema50"] and d["ema50"] < d["ema200"]

    # Simple liquidity-sweep proxy: candle takes prior 20-candle extreme and closes back inside.
    sweep_low = float(e["low"]) < swing_low and price > swing_low
    sweep_high = float(e["high"]) > swing_high and price < swing_high

    # Basic momentum / structure proxy; not a full discretionary BOS/MSS detector.
    bull_break = price > swing_high and price > e["ema20"] and e["ema20"] > e["ema50"]
    bear_break = price < swing_low and price < e["ema20"] and e["ema20"] < e["ema50"]
    rsi = float(e["rsi"]) if pd.notna(e["rsi"]) else 50.0
    volume_ok = pd.notna(e["vol_sma20"]) and float(e["volume"]) >= float(e["vol_sma20"])

    score_long = sum([daily_bull, sweep_low, bull_break, rsi > 50 and rsi < 72, volume_ok])
    score_short = sum([daily_bear, sweep_high, bear_break, rsi < 50 and rsi > 28, volume_ok])

    signal = "WAIT"
    rationale = []
    if score_long >= 3 and daily_bull and (bull_break or sweep_low):
        signal = "POTENTIAL LONG"
        rationale = [
            "Daily trend filter is bullish" if daily_bull else "",
            "Entry timeframe shows a bullish break or downside sweep/reclaim" if (bull_break or sweep_low) else "",
            f"RSI is {rsi:.1f}",
            "Volume is at/above its 20-candle average" if volume_ok else "Volume is below its 20-candle average"
        ]
        sl = min(float(e["low"]), swing_low) - 0.15 * atr
        risk = max(price - sl, 0.25 * atr)
        tp1, tp2, tp3 = price + risk, price + 2*risk, price + 3*risk
    elif score_short >= 3 and daily_bear and (bear_break or sweep_high):
        signal = "POTENTIAL SHORT"
        rationale = [
            "Daily trend filter is bearish" if daily_bear else "",
            "Entry timeframe shows a bearish break or upside sweep/rejection" if (bear_break or sweep_high) else "",
            f"RSI is {rsi:.1f}",
            "Volume is at/above its 20-candle average" if volume_ok else "Volume is below its 20-candle average"
        ]
        sl = max(float(e["high"]), swing_high) + 0.15 * atr
        risk = max(sl - price, 0.25 * atr)
        tp1, tp2, tp3 = price - risk, price - 2*risk, price - 3*risk
    else:
        sl = tp1 = tp2 = tp3 = None
        rationale = [
            f"Daily bias: {'bullish' if daily_bull else 'bearish' if daily_bear else 'mixed'}",
            f"RSI is {rsi:.1f}",
            "No complete rule-based setup; wait rather than force a trade."
        ]

    return {
        "symbol": symbol, "price": price, "signal": signal, "rsi": rsi,
        "daily_bias": "Bullish" if daily_bull else "Bearish" if daily_bear else "Mixed",
        "score": max(score_long, score_short), "atr": atr,
        "sweep_low": sweep_low, "sweep_high": sweep_high,
        "volume_ok": bool(volume_ok), "sl": sl, "tp1": tp1, "tp2": tp2, "tp3": tp3,
        "time": str(e["time"]), "rationale": [x for x in rationale if x]
    }

with st.sidebar:
    st.header("Settings")
    mode = st.radio("Scan universe", ["Watchlist", "Top listed USDT spot pairs (first 100)"])
    default_selection = st.multiselect("Watchlist", DEFAULT_SYMBOLS, default=DEFAULT_SYMBOLS[:10])
    entry_tf = st.selectbox("Entry timeframe", ["15m", "1h", "4h"], index=1)
    bias_tf = st.selectbox("Higher-timeframe bias", ["4h", "1d", "1w"], index=1)
    risk_pct = st.number_input("Risk per trade (%) — planning only", min_value=0.1, max_value=2.0, value=0.5, step=0.1)
    account_size = st.number_input("Account balance (USDT) — optional", min_value=0.0, value=0.0, step=10.0)
    run_scan = st.button("🔎 Scan market", type="primary")

if mode == "Watchlist":
    symbols = default_selection or ["BTC/USDT"]
else:
    symbols = DEFAULT_SYMBOLS

st.caption(f"Last app view: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} • Data source: Bybit public spot candles")

if run_scan:
    results = []
    progress = st.progress(0)
    status = st.empty()
    for i, symbol in enumerate(symbols):
        status.write(f"Scanning {symbol} ({i+1}/{len(symbols)})…")
        try:
            results.append(analyze_symbol(symbol, entry_tf, bias_tf))
        except Exception as exc:
            results.append({"symbol": symbol, "signal": "DATA ERROR", "error": str(exc)})
        progress.progress((i+1)/len(symbols))
    st.session_state["results"] = results
    status.empty()
    progress.empty()

results = st.session_state.get("results", [])
if results:
    good = [r for r in results if r.get("signal") in ("POTENTIAL LONG", "POTENTIAL SHORT")]
    st.subheader("Market scan")
    st.write(f"Potential setups: **{len(good)}** out of **{len(results)} scanned pairs.")
    rows = []
    for r in results:
        rows.append({
            "Pair": r["symbol"], "Signal": r["signal"],
            "Price": r.get("price"), "Daily bias": r.get("daily_bias"),
            "RSI": round(r["rsi"], 1) if r.get("rsi") is not None else None,
            "Score / 5": r.get("score"), "Candle time (UTC)": r.get("time"),
            "Error": r.get("error", "")
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    options = [r["symbol"] for r in results if r.get("signal") != "DATA ERROR"]
    if options:
        selected = st.selectbox("Inspect a pair", options)
        r = next(x for x in results if x["symbol"] == selected)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Latest close", f'{r["price"]:,.6g}')
        c2.metric("Signal", r["signal"])
        c3.metric("Daily bias", r["daily_bias"])
        c4.metric("RSI", f'{r["rsi"]:.1f}')
        st.markdown("**Setup checks**")
        st.write(" • ".join(r["rationale"]))
        if r["sl"] is not None:
            st.markdown("**Illustrative levels (not guaranteed)**")
            lev = pd.DataFrame([
                {"Level": "Entry reference", "Price": r["price"]},
                {"Level": "Stop Loss", "Price": r["sl"]},
                {"Level": "TP1 (1R)", "Price": r["tp1"]},
                {"Level": "TP2 (2R)", "Price": r["tp2"]},
                {"Level": "TP3 (3R)", "Price": r["tp3"]},
            ])
            st.dataframe(lev, use_container_width=True, hide_index=True)
            if account_size > 0:
                risk_cash = account_size * risk_pct / 100
                distance = abs(r["price"] - r["sl"])
                qty = risk_cash / distance if distance > 0 else 0
                st.info(
                    f"Illustrative position quantity: {qty:.6g} units, based on "
                    f"{risk_pct:.2f}% account risk ({risk_cash:.4g} USDT). "
                    "This ignores fees, slippage, contract specifications and exchange minimums."
                )
        else:
            st.info("No complete setup. No entry levels are proposed.")
    csv = pd.DataFrame(rows).to_csv(index=False).encode("utf-8")
    st.download_button("Download scan as CSV", csv, "crypto_signal_scan.csv", "text/csv")
else:
    st.info("Choose your watchlist and timeframes, then press **Scan market**.")
    st.markdown("""
    **How the first version works**
    - Higher-timeframe EMA trend filter (EMA 50 / EMA 200).
    - Entry-timeframe EMA alignment and a 20-candle swing-level check.
    - A simple liquidity-sweep proxy (wick beyond a recent extreme, then close back inside).
    - RSI and volume context.
    - Potential SL and 1R/2R/3R targets when rules align.

    This is a transparent baseline, not a trained AI model and not a complete BOS/MSS or order-flow engine.
    """)

st.divider()
st.caption("No exchange API keys required. Do not paste API keys or seed phrases into this app. Signals may be delayed, unavailable, or wrong.")
