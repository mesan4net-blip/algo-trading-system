# Decisions Log

Every major decision, what was chosen, what was rejected, and why.

---

## [2026-06-27] Trading Style
- **Chosen:** Day Trading
- **Why:** Best fit for automation. Kill zones are fixed times. Signals are mechanical and repeatable. No overnight risk.
- **Rejected:** Swing trading (too slow, hard to automate entries), Scalping (too noisy, needs constant screen time)

## [2026-06-27] Framework
- **Chosen:** ICT / Smart Money Concepts (SMC)
- **Why:** Mechanical, repeatable, automatable patterns. OB, FVG, BOS are definable in code. Kill zones are fixed windows.
- **Rejected:** Pure TA (too subjective), Price Action only (too discretionary)

## [2026-06-27] Timeframe Stack
- **Chosen:** Daily → 4H → 1H → 5M
- **Why:** Best balance of signal quality and entry precision for day trading. Daily/4H give clean bias. 1H gives zone. 5M gives entry trigger.
- **Rejected:** Weekly bias (too slow), 1M entry (too noisy)

## [2026-06-27] Signal Source
- **Chosen:** TradingView Premium + Pine Script Strategy
- **Why:** Already owned. Has live data, backtesting, pattern detection, and webhook alerts built in. Eliminates need to build signal engine from scratch.
- **Rejected:** Twelve Data API (redundant — TradingView already provides live data)

## [2026-06-27] Execution Bridge
- **Chosen:** ZeroMQ bridge — Python to MT4 EA directly
- **Why:** Free, real-time, no middleware cost, used by professional algo traders. Direct socket connection between Python and MT4.
- **Rejected:** TradersPost ($49-99/month, does not support OANDA/Forex.com natively), building REST API from scratch (unnecessary complexity)

## [2026-06-27] Broker
- **Chosen:** Forex.com MT4
- **Why:** Already have account. MT4 fully supports EAs. Forex.com provides VPS access directly — no separate VPS needed.
- **Rejected:** OANDA (TradersPost does not support it natively), IC Markets, Pepperstone (would require new account setup)

## [2026-06-27] VPS
- **Chosen:** Forex.com VPS (built into existing account)
- **Why:** Already available through Forex.com. Runs MT4 24/7. No additional monthly cost or setup.
- **Rejected:** DigitalOcean, Hetzner (unnecessary — Forex.com VPS already available)

## [2026-06-27] Project Documentation
- **Chosen:** GitHub as single source of truth
- **Why:** Stores code AND docs in one place. Version controlled. Clean API for reading/writing. Every chat reads ONBOARDING.md to get full context instantly.
- **Rejected:** Notion (extra tool, manual sync required), Google Docs (too simple, no version control), Multiple chat HQ artifacts (no real persistence across chats)

## [2026-06-27] Chat Structure
- **Chosen:** One general discussion chat (this) + separate phase-specific chats
- **Why:** Keeps architecture decisions separate from build work. Each phase chat reads ONBOARDING.md for full context.
- **Rejected:** Everything in one chat (context gets too long), Multiple parallel chats (causes confusion and lost context)
