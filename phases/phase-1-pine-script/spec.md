# Phase 1 — Pine Script ICT Strategy

## Objective
Write a complete ICT/SMC Pine Script strategy in TradingView that detects high-probability setups, grades them, backtests them, and fires webhook alerts.

## What Gets Built
- HTF bias detector (Daily + 4H trend direction)
- Kill zone filter (London 2–5 AM EST, NY 8–11 AM EST)
- Order Block (OB) detection
- Fair Value Gap (FVG) detection
- Break of Structure (BOS) / Market Structure Shift (MSS) detection
- Confluence scorer (grades setup A+/B/C)
- Entry zone calculator (OB body + FVG 50%)
- SL placement (below OB origin)
- TP1 and TP2 levels
- Webhook alert with full trade JSON payload

## Success Criteria
- Backtested on minimum 2 years of data
- Win rate above 50% in backtest
- Average RR above 2.0
- Max drawdown below 20%
- Fires clean webhook JSON on signal

## Status
🔴 Not started

## Chat
Open a new chat. Paste ONBOARDING.md. Say: "Build Phase 1 — Pine Script ICT strategy"
