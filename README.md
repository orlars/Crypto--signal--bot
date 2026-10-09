# Crypto Signal Lab (Bybit public data)

A beginner-friendly, rule-based crypto signal dashboard. It reads public Bybit spot OHLCV candles and displays potential LONG/SHORT setups, daily bias, RSI, and illustrative SL/TP levels. It does not place trades.

## Run locally
1. Install Python 3.10+.
2. Open a terminal in this folder.
3. Run:
   ```bash
   pip install -r requirements.txt
   streamlit run app.py
   ```
4. Open the local URL shown in the terminal.

## Deploy online
You can deploy this project to a Python app host such as Streamlit Community Cloud. Upload the files to a GitHub repository, select `app.py` as the main file, and deploy. Review the host's current terms and limits first.

## Important limitations
- Uses Bybit public SPOT market data only; this is not a futures feed.
- "Top listed pairs" is a curated starter list, not a live ranking of the top 100 by market cap or volume.
- The signal rules are simple, transparent heuristics; liquidity sweeps are approximated from candle highs/lows.
- It does not implement full discretionary BOS/MSS, order blocks, news analysis, or an AI model.
- Does not send Telegram messages yet and does not execute trades.
- Do not use the levels blindly. Paper-test, include fees/slippage, and verify all levels manually before any real trade.
- Never provide withdrawal permission to a trading bot. Keep exchange API permissions disabled until you understand the security risks.
