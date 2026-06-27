# Phase 3 — MT4 Expert Advisor

## Objective
Build the MT4 EA in MQL4 that listens via ZeroMQ, places trades, and manages positions automatically.

## What Gets Built
- ZeroMQ subscriber in MQL4
- Trade placement logic (market/limit orders)
- Position sizing from signal payload
- SL/TP management
- Partial close at TP1 (50%)
- Move SL to break-even after TP1
- Trail SL behind 5M swing lows
- Hard close at kill zone end
- Trade result reporter back to Python

## Status
🔴 Not started — waiting for Phase 2 completion
