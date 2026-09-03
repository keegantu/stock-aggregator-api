"""
Pull daily OHLCV history from Alpha Vantage into one flat CSV for Tableau.

Setup:
    pip install requests pandas
    export ALPHAVANTAGE_API_KEY=your_key_here

Run:
    python pull_stock_data.py

Output:
    stock_daily.csv  -- one row per ticker per trading day
"""

import os
import time
import sys
import requests
import pandas as pd

API_KEY = os.environ.get("ALPHAVANTAGE_API_KEY")
if not API_KEY:
    sys.exit("Set ALPHAVANTAGE_API_KEY first:  export ALPHAVANTAGE_API_KEY=your_key")

# Free tier allows 25 requests/day, so keep this list short.
# A mix of sectors makes the dashboard more interesting than 5 tech names.
TICKERS = {
    "AAPL": "Technology",
    "MSFT": "Technology",
    "JPM":  "Financials",
    "XOM":  "Energy",
    "JNJ":  "Healthcare",
    "WMT":  "Consumer",
}

URL = "https://www.alphavantage.co/query"

# Alpha Vantage put outputsize=full behind the paywall for TIME_SERIES_DAILY.
# TIME_SERIES_WEEKLY is still free AND returns full history, so we use that.
# Set MODE = "daily" if you only want the last 100 trading days instead.
MODE = "weekly"

# Use the ADJUSTED weekly endpoint: it back-adjusts for stock splits and
# dividends, so a 3-for-1 split doesn't look like a 66% one-week crash.
# (Weekly adjusted is free; only the DAILY adjusted endpoint is paywalled.)
FUNCTION = "TIME_SERIES_WEEKLY_ADJUSTED" if MODE == "weekly" else "TIME_SERIES_DAILY"
SERIES_KEY = "Weekly Adjusted Time Series" if MODE == "weekly" else "Time Series (Daily)"
# rolling windows: ~1 quarter and ~1 year in each frequency
SHORT_WIN, LONG_WIN = (13, 52) if MODE == "weekly" else (20, 50)
PERIODS_PER_YEAR = 52 if MODE == "weekly" else 252


def fetch(symbol):
    """Return a DataFrame of daily bars for one ticker."""
    params = {"function": FUNCTION, "symbol": symbol, "apikey": API_KEY}
    if MODE == "daily":
        params["outputsize"] = "compact"   # 'full' is a paid feature now
    r = requests.get(URL, params=params, timeout=30)
    r.raise_for_status()
    payload = r.json()

    # Alpha Vantage returns errors as normal 200s, so check explicitly
    if SERIES_KEY not in payload:
        note = payload.get("Note") or payload.get("Information") or payload.get("Error Message")
        raise RuntimeError(f"{symbol}: {note or payload}")

    df = pd.DataFrame.from_dict(payload[SERIES_KEY], orient="index")
    df.index = pd.to_datetime(df.index)
    df = df.rename(columns={
        "1. open": "open", "2. high": "high", "3. low": "low",
        "4. close": "close_raw", "5. adjusted close": "close",
        "6. volume": "volume", "5. volume": "volume",
    })
    # keep only the columns we care about, then make them numeric
    keep = [c for c in ["open", "high", "low", "close", "close_raw", "volume"]
            if c in df.columns]
    df = df[keep].astype(float)

    if "close_raw" in df.columns:
        # scale OHL by the same split factor applied to close, so highs/lows
        # stay consistent with the adjusted close
        factor = df["close"] / df["close_raw"]
        for col in ("open", "high", "low"):
            df[col] = df[col] * factor
        df = df.drop(columns=["close_raw"])
    df.index.name = "date"
    return df.sort_index()


def enrich(df, symbol, sector):
    """Add the derived columns that make a dashboard worth looking at."""
    df = df.copy()
    df["ticker"] = symbol
    df["sector"] = sector

    df["period_return_pct"] = df["close"].pct_change() * 100
    df["ma_short"] = df["close"].rolling(SHORT_WIN).mean()
    df["ma_long"] = df["close"].rolling(LONG_WIN).mean()
    # realized volatility over the short window, annualized
    df["volatility_ann"] = df["period_return_pct"].rolling(SHORT_WIN).std() * (PERIODS_PER_YEAR ** 0.5)
    df["dollar_volume"] = df["close"] * df["volume"]
    df["range_pct"] = (df["high"] - df["low"]) / df["low"] * 100

    return df.reset_index()


def main():
    frames = []
    for i, (symbol, sector) in enumerate(TICKERS.items()):
        print(f"[{i+1}/{len(TICKERS)}] {symbol} ...", flush=True)
        try:
            frames.append(enrich(fetch(symbol), symbol, sector))
        except Exception as e:
            print(f"  skipped: {e}")
        # free tier is rate limited; be polite
        if i < len(TICKERS) - 1:
            time.sleep(15)

    if not frames:
        sys.exit("No data pulled. Check your API key and daily request limit.")

    out = pd.concat(frames, ignore_index=True)

    # Trim to recent years so the file stays manageable in Tableau Public
    out = out[out["date"] >= "2019-01-01"]

    cols = ["date", "ticker", "sector", "open", "high", "low", "close", "volume",
            "period_return_pct", "ma_short", "ma_long", "volatility_ann",
            "dollar_volume", "range_pct"]
    out = out[cols].round(4)

    out.to_csv("stock_history.csv", index=False)
    print(f"\nWrote stock_history.csv ({MODE}) — {len(out):,} rows, "
          f"{out['ticker'].nunique()} tickers, "
          f"{out['date'].min().date()} to {out['date'].max().date()}")


if __name__ == "__main__":
    main()
