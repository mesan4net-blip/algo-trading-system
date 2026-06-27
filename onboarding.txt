# Onboarding — Read This First In Every Chat

## Project
ICT/SMC Algo Trading System — Self-learning, fully automated forex day trading.

## Current Phase: 1 — Pine Script ICT Strategy

## Architecture (locked)
```
TradingView Premium (Pine Script ICT strategy)
  → detects OB, FVG, BOS, MSS on Daily→4H→1H→5M
  → fires webhook on confirmed signal
Python Backend (AI news scoring + ML confidence filter)
  → approves or rejects signal
ZeroMQ Bridge
  → sends approved signal to MT4 instantly
MT4 Expert Advisor on Forex.com
  → places trade, manages position automatically
  → partial close at TP1, move SL to BE, trail to TP2
GitHub
  → logs everything, feeds ML retraining nightly
Forex.com VPS
  → runs everything 24/7
```

## Key Decisions Made
- Style: Day trading
- Framework: ICT/SMC
- TF Stack: Daily→4H→1H→5M
- Kill Zones: London 2–5 AM EST, NY 8–11 AM EST
- Signal source: TradingView Premium (already owned)
- Execution: MT4 on Forex.com via ZeroMQ EA (no TradersPost needed)
- Broker: Forex.com MT4 (already have account)
- VPS: Forex.com VPS (already available)
- Storage: GitHub (single source of truth)
- Dashboard: https://mesan4net-blip.github.io/algo-trading-system/

## What Was Rejected And Why
- TradersPost: $49-99/month, doesn't support Forex.com natively
- Twelve Data API: redundant — TradingView already has live data
- Notion: extra tool, manual sync required
- Scalping: too noisy for automation
- Swing trading: too slow, hard to automate entries

## Phase Tracker
| Phase | Name | Status |
|-------|------|--------|
| 1 | Pine Script ICT Strategy | Active |
| 2 | Python Backend + ZeroMQ Bridge | Pending |
| 3 | MT4 Expert Advisor | Pending |
| 4 | Intelligence Layer (AI + Fundamental) | Pending |
| 5 | ML Self-Learning Loop | Pending |
| 6 | Deploy to Forex.com VPS | Pending |

## APIs
| API | Purpose | Status |
|-----|---------|--------|
| TradingView | Live data + signals | Owned — not integrated yet |
| GitHub API | Project logging | Connected |
| Forex.com MT4 | Trade execution | Owned — not integrated yet |
| Forex.com VPS | 24/7 hosting | Available — not set up yet |
| NewsAPI | News headlines | Needed — Phase 2 |
| FRED API | Economic data | Needed — Phase 2 |
| CFTC COT | Institutional positioning | Needed — Phase 2 |
| Claude API | AI news scoring | Needed — Phase 2 |

## Chat Purpose
This chat is for: [REPLACE WITH YOUR SPECIFIC TASK BEFORE SENDING]

## GitHub Repo
https://github.com/mesan4net-blip/algo-trading-system

## Project Dashboard
https://mesan4net-blip.github.io/algo-trading-system/
