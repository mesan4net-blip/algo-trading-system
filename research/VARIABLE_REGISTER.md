# 3SHA — complete variable register

Every variable in the strategy, every variation, and the order they are being or
still need to be tested. Generated from `test_plan.py`, `fa_engine.py` and
`3SHA_FullAlignment_v1.pine` — not from memory.

Strategy covered: **Full Alignment (3SHA-FA)**. Same register applies to each new
entry type as it is built.

---

## STAGE 1 — currently tested

7 variables, **6,480 combinations** per market. Every market gets the identical grid.
Each combination is also re-checked across 5 separate stretches of history, and is
only called a keeper if it stayed profitable in at least 4 of them.

| # | Variable | Variations | Count |
|---|----------|-----------|-------|
| 1 | Smoothing — chart + mid layer (coupled) | 2,4 · 3,6 · 4,8 · 6,11 · 8,16 · 10,20 | 6 |
| 2 | Smoothing — slow layer | 2,2 · 3,6 · 4,8 · 6,11 · 8,16 · 10,20 | 6 |
| 3 | Exit trigger | base flip · HTF1 flip · HTF2 flip | 3 |
| 4 | Initial stop anchor | Swing · HTF1 body · HTF2 body | 3 |
| 5 | Anchor basis | Body · Wick | 2 |
| 6 | Stop style | mental (close-based) · hard (intra-bar) | 2 |
| 7 | Trailing stop | off · Swing 3 · Swing 6 · HTF1 body · HTF2 body | 5 |

---

## STAGE 2 — built, never tested

These exist in the strategy today and can be swept immediately. Ordered by expected
impact.

| # | Variable | Variations to test | Why it matters | Grid effect |
|---|----------|--------------------|----------------|-------------|
| 8 | **Base timeframe** | 15m · 1h · 4h · 1D | Everything so far is 4-hour only. The live chart is 15m. | ×4 |
| 9 | **HTF1 timeframe** | 1h · 4h · 1D | Always Daily. Never varied. | ×3 |
| 10 | **HTF2 timeframe** | 4h · 1D · 1W | Always Weekly. Never varied. | ×3 |
| 11 | **Partial take-profit** | off · 1R/50% · 2R/50% · 2R/33% · 3R/50% | Entire feature dark in all 25,920 runs. | ×5 |
| 12 | **Confirmation mode** | Confirmed (1-bar) · Immediate | Always Confirmed. Immediate enters a bar earlier. | ×2 |
| 13 | **Exit trigger — remaining options** | Any layer flips · All layers flip | 2 of the 5 built options never tried. | +2 to #3 |
| 14 | **Stop anchor — Trigger Candle** | Trigger Candle | 4th built anchor, dropped from the plan. | +1 to #4 |
| 15 | **Skip gap entries** | off · on @0.25% · 0.5% · 1.0% | Built to your spec, never once enabled. | ×4 |
| 16 | **Break-even** | off · on @0.5R · 1R · 2R | Always on at 1R. | ×4 |
| 17 | **Trail activation** | 0.5R · 1R · 2R · 3R | Fixed at 1R. Probe showed it moves results. | ×4 |
| 18 | **Direction** | both · long only · short only | Always both. | ×3 |
| 19 | **Swing lookback (initial stop)** | 5 · 10 · 20 · 30 | Fixed at 10. | ×4 |
| 20 | **Stop buffer** | 0.02% · 0.05% · 0.1% · 0.25% of price | Fixed at 0.05%. | ×4 |
| 21 | **Trail lookback** | 3 · 6 · 12 · 20 | Only 3 and 6 tested. | +2 to #7 |
| 22 | **Trail basis** | Body · Wick, independent of the stop | Currently chained to the stop's basis. | ×2 |
| 23 | **Trail buffer** | independent of the stop buffer | Currently chained. | ×3 |
| 24 | **Risk per trade** | 0.5% · 1% · 2% · 3% | Fixed at 1%. Scales both sides, so low priority. | ×4 |
| 25 | **Max equity / leverage** | 100% · 200% · 400% | Fixed at 4×. | ×3 |
| 26 | **Min stop distance** | off · 0.25% · 0.5% | Always off. | ×3 |
| 27 | **Smoothing — chart vs mid, uncoupled** | all 36 pairs | Currently welded to one value. | ×6 |

---

## STAGE 3 — must be built first

| # | Variable | Note |
|---|----------|------|
| 28 | **Base SHA body as stop anchor** | Does not exist. Anchors only reach HTF1 and HTF2, yet the entry fires off the base layer flipping. |
| 29 | **Base SHA body as trail anchor** | Same gap on the trail side. |
| 30 | **Support / resistance stops and targets** | Parked by decision. Needs a rule-based definition of a level before it can be tested. |

---

## Recommended order

Run in this order. Do **not** unlock everything at once — each stage multiplies the
grid, and a bigger grid means more ways to be fooled by luck.

1. **Timeframes (#8, #9, #10).** Biggest unexplored space, and the live chart isn't
   even in it yet. Run alone with Stage 1 held at its best-known settings — do not
   multiply against the full grid.
2. **Build the base SHA body anchors (#28, #29)**, then fold them into variables 4
   and 7 as extra options.
3. **Partial take-profit (#11)** and the **remaining exit options (#13)**. Both are
   complete features currently invisible.
4. **Entry variations (#12, #14, #15, #18).**
5. **Management fine-tuning (#16, #17, #21, #22, #23).**
6. **Stop geometry (#19, #20, #26).**
7. **Sizing (#24, #25)** — last, because it scales return and drawdown together and
   largely cancels in the ranking.
8. **Uncoupling chart from mid smoothing (#27)** — most expensive; only if evidence
   suggests the two layers want different speeds.

---

## Held constant on purpose

| Setting | Value | Reason |
|---------|-------|--------|
| Entry signal | Full Alignment | This is the strategy under test |
| HTF2 lengths in Stage 1 | swept separately | Was frozen at 2,2 — corrected |
| Position sizing | fractional, risk ÷ stop distance | Whole-unit rounding was a bug — fixed |
| Trading cost | 0.20% crypto, 0.02% forex and ETFs, charged every fill | Was silently zero — fixed |
| Validation | full history + 5 time blocks | Ranking is block consistency first, then return per year ÷ worst dip |
| Date filter | off | Not a strategy variable |
| Display settings | — | Cosmetic; no effect on trades |

---

## Rules that must not be relaxed

- **len1 ≥ 2 and len2 ≥ len1** on every smoothing pair. A length of 1 disables that
  EMA pass; 1,1 is a plain Heikin-Ashi, not a Smoothed Heikin-Ashi, and any result
  from it is measuring a different indicator.
- **Never rank on raw return or on a bare ratio.** Return per year against the worst
  dip, gated on block consistency. A tiny drawdown alone must not win.
- **Never rebuild one timeframe from another.** Use the native export per timeframe;
  the BTC 1h and 4h files disagree by ~$224 when aggregated.
- **Charge trading costs on every fill.** They erased the EUR/USD edge entirely.
