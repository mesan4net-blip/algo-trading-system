# Phase 2 — Python Backend + ZeroMQ Bridge

## Objective
Build the Python intelligence layer that receives TradingView webhooks, scores them against fundamental data and ML confidence, then passes approved signals to MT4 via ZeroMQ.

## What Gets Built
- Webhook receiver (Flask/FastAPI endpoint)
- ZeroMQ socket publisher
- NewsAPI integration (live news scoring)
- FRED API integration (economic calendar)
- CFTC COT data reader
- Claude API integration (AI news analysis)
- Signal approval/rejection logic
- GitHub logging (auto-writes trade decisions)

## Status
🔴 Not started — waiting for Phase 1 completion
