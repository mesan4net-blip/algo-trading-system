# Trade Considerations

A running log of trade setup ideas, observations, and pattern notes captured from live chart analysis. These are raw observations to evaluate and potentially formalize into strategy logic later — not yet implemented rules.

---

## Entry #1 — 2026-06-30 — EURUSD 30M — Trend Continuation Entry

**Chart:** EURUSD, 30M, OANDA — using 3SHA-v3 strategy script
**Timeframe stack:** HTF2 = 1D, HTF1 = 4H, Base = Chart (30M)

**Observation:**
A clean downtrend continuation setup. At the marked point, all three SHA layers were in full alignment (bearish), and price had pulled back slightly before continuing the dominant trend direction.

**Trade idea:**
- **Open a SELL at the beginning** of the marked zone — entry justified by trend continuation, not a fresh reversal signal
- **Condition:** All 3 SHAs in alignment (bearish) at entry
- **Exit:** Close at end of session (London session shown ending around -50 pips into the move)

**Why this matters:**
This is a session-bounded trend continuation play — enter on alignment, ride the session, exit at session close rather than waiting for a trail/flip exit. Different exit philosophy from what's currently coded (trail-based or flip-based exits run indefinitely across sessions).

**Open question for strategy design:**
Should "close at end of session" become a formal, selectable exit mode alongside the existing trail/flip/R:R exits? This chart suggests it may outperform a trail-based hold-through-multiple-sessions approach, at least in trending conditions like this one.

---
