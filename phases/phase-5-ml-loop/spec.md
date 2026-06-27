# Phase 5 — ML Self-Learning Loop

## Objective
System learns from its own trade history and continuously improves strategy parameters without human intervention.

## What Gets Built
- Trade outcome logging pipeline (GitHub → ML training data)
- Nightly retraining script (Python + scikit-learn)
- Feature importance analysis (which conditions predict wins)
- Parameter auto-adjustment (OB sensitivity, confluence threshold, RR minimum)
- Market regime detector (trending vs ranging — adjusts strategy accordingly)
- Performance dashboard (win rate, RR, drawdown over time)

## Status
🔴 Not started — waiting for Phase 4 completion
