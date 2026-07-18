#!/usr/bin/env python3
"""
fetch_ohlcv.py — one-shot historical OHLCV downloader for 3SHA research.

Runs on YOUR machine. The research sandbox has no market-data network access,
so the data pull happens here (once per symbol/timeframe), not per change.

Produces a standardized CSV the backtest engine reads directly:
    columns : timestamp,open,high,low,close,volume
    timestamp: UTC, ISO-8601
    ordering : ascending, de-duplicated

Only the BASE (chart) timeframe is needed — HTF1/HTF2 are resampled in Python
(which is also step one of the Pine-parity check).

INSTALL (only the one you need):
    pip install ccxt        # crypto
    pip install yfinance    # stocks / ETFs

USAGE:
    # Crypto (no API key needed):
    python fetch_ohlcv.py --source crypto --symbol BTC/USDT --timeframe 15m --start 2023-01-01

    # Stocks / ETFs:
    python fetch_ohlcv.py --source stock  --symbol SPY      --timeframe 15m --start 2024-06-01

Then upload the CSV in chat, or commit it and tell me the path.
"""
import argparse
import csv
import sys
import time
from datetime import datetime, timezone


def parse_start_ms(s):
    return int(datetime.strptime(s, "%Y-%m-%d")
               .replace(tzinfo=timezone.utc).timestamp() * 1000)


def fetch_crypto(symbol, timeframe, start_ms, exchange_id):
    import ccxt
    ex = getattr(ccxt, exchange_id)({"enableRateLimit": True})
    ex.load_markets()
    if ex.timeframes and timeframe not in ex.timeframes:
        sys.exit(f"{exchange_id} has no timeframe {timeframe}. "
                 f"Supported: {sorted(ex.timeframes)}")
    rows, since, limit = [], start_ms, 1000
    now = ex.milliseconds()
    while since < now:
        batch = ex.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
        if not batch:
            break
        rows += batch
        since = batch[-1][0] + 1
        time.sleep(ex.rateLimit / 1000.0)
        if len(batch) < limit:
            break
    return [(datetime.fromtimestamp(r[0] / 1000, tz=timezone.utc).isoformat(),
             r[1], r[2], r[3], r[4], r[5]) for r in rows]


def fetch_stock(symbol, timeframe, start):
    import yfinance as yf
    tf_map = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
              "60m": "60m", "1h": "60m", "1d": "1d"}
    if timeframe not in tf_map:
        sys.exit(f"Unsupported stock timeframe {timeframe}. Use: {list(tf_map)}")
    df = yf.download(symbol, start=start, interval=tf_map[timeframe],
                     auto_adjust=False, progress=False)
    if df.empty:
        sys.exit("No data. Yahoo intraday history is limited "
                 "(~730 days for 60m, ~60 days for 15m).")
    rows = []
    for ts, row in df.iterrows():
        t = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
        rows.append((t.isoformat(),
                     float(row["Open"]), float(row["High"]),
                     float(row["Low"]), float(row["Close"]),
                     float(row["Volume"])))
    return rows


def main():
    ap = argparse.ArgumentParser(description="Fetch OHLCV → standardized CSV for 3SHA research")
    ap.add_argument("--source", required=True, choices=["crypto", "stock"])
    ap.add_argument("--symbol", required=True, help="e.g. BTC/USDT or SPY")
    ap.add_argument("--timeframe", required=True, help="e.g. 15m, 60m/1h, 1d")
    ap.add_argument("--start", required=True, help="YYYY-MM-DD (UTC)")
    ap.add_argument("--exchange", default="binance", help="crypto exchange id (default: binance)")
    ap.add_argument("--out", default=None, help="output path (default: <symbol>_<tf>.csv)")
    a = ap.parse_args()

    if a.source == "crypto":
        rows = fetch_crypto(a.symbol, a.timeframe, parse_start_ms(a.start), a.exchange)
    else:
        rows = fetch_stock(a.symbol, a.timeframe, a.start)

    # sort ascending + dedupe on timestamp
    seen, clean = set(), []
    for r in sorted(rows, key=lambda x: x[0]):
        if r[0] in seen:
            continue
        seen.add(r[0])
        clean.append(r)

    out = a.out or f"{a.symbol.replace('/', '')}_{a.timeframe}.csv"
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        w.writerows(clean)

    if clean:
        print(f"OK  {len(clean)} bars  {clean[0][0]} -> {clean[-1][0]}")
        print(f"OK  wrote {out}")
    else:
        print("No rows written.")


if __name__ == "__main__":
    main()
