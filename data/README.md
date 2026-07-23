# Market data

Raw TradingView OHLCV exports, stored so they never need re-uploading.

Layout: `data/<INSTRUMENT>/<timeframe>.csv` — columns: time, open, high, low, close (+volume).
Times are ISO with offset; parse as UTC.

`manifest.json` lists every instrument, timeframe, bar count and date range.

## Known issues
- BTCUSDT 1h and 4h exports disagree when aggregated. Use native per-timeframe files;
  never rebuild one timeframe from another.
- An early BTCUSDT dated-futures export was discarded (illiquid, unrepresentative).
