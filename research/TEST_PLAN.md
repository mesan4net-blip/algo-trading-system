# 3SHA — test plan and variable register

Every variable, every variation, in the order they get tested. Generated from
`test_plan.py`, `fa_engine.py` and `3SHA_FullAlignment_v1.pine`.

Applies to **Full Alignment (3SHA-FA)** first, then to each new entry type as it is
built. Same plan for every strategy, so results stay comparable.

---

## How the plan runs

Each step sweeps **one** variable against everything locked in the steps before it.
What survives is a **region**, not a single best cell: a setting is only kept if it
stayed profitable across at least 4 of 5 separate stretches of history, and if its
neighbours held up too. Then it is locked and the next step begins.

Timeframes are **last on purpose** — so a finished, locked set can be run across
every timeframe combination to see how the same rules would have behaved on faster
or slower charts.

Ranking at every step: **return per year divided by the worst dip**, gated on block
consistency. Never raw return, never a bare ratio.

---

## The steps

| # | Step | Variations |
|---|------|-----------|
| 1 | Smoothing — chart + mid layer, coupled | 2,4 · 3,6 · 4,8 · 6,11 · 8,16 · 10,20 |
| 2 | Smoothing — slow layer | 2,2 · 3,6 · 4,8 · 6,11 · 8,16 · 10,20 |
| 3 | Smoothing — chart and mid uncoupled | all 36 pairs of the six values |
| 4 | Confirmation mode | Confirmed (1-bar) · Immediate |
| 5 | Direction | both · long only · short only |
| 6 | Skip gap entries | off · 0.25% · 0.5% · 1.0% |
| 6b | Re-enter after an exit | off · on — fires when price closes beyond the exit candle's high (long) or low (short) |
| 7 | Exit — how a trade ends | chart flips · mid flips · slow flips · opposite full alignment · chart flips held 2 bars · price back through mid SHA · profit target 2R · profit target 3R · gives back 40% of peak · time stop 30 bars |
| 8 | **BUILD:** base SHA body as stop and trail anchor | does not exist yet — needed for steps 9 and 15 |
| 9 | Initial stop anchor | trigger candle · swing · base body · HTF1 body · HTF2 body |
| 10 | Anchor basis | body · wick |
| 11 | Swing lookback | 5 · 10 · 20 · 30 |
| 12 | Stop buffer | 0.02% · 0.05% · 0.1% · 0.25% of price |
| 13 | Min stop distance | off · 0.25% · 0.5% |
| 14 | Stop style | mental (close-based) · hard (intra-bar) |
| 15 | Trailing stop anchor | off · swing · base body · HTF1 body · HTF2 body |
| 16 | Trail basis | body · wick |
| 17 | Trail lookback | 3 · 6 · 12 · 20 |
| 18 | Trail activation | 0.5R · 1R · 2R · 3R |
| 19 | Trail buffer | 0.02% · 0.05% · 0.1% · 0.25% |
| 20 | Break-even | off · 0.5R · 1R · 2R |
| 21 | Break-even offset | 0 · 0.05% · 0.1% |
| 22 | Partial take-profit | off · 1R/50% · 2R/50% · 2R/33% · 3R/50% |
| 23 | Risk per trade | 0.5% · 1% · 2% · 3% |
| 24 | Max equity per trade | 100% · 200% |
| 25 | **Timeframes + exit mode — run last, together** | every valid trio × (align-exit on · hold until stopped) |

Step 7 covers seven distinct exit ideas, not just which layer flips. On QQQ's
15-minute chart — the worst case for churn — a **profit target at 3R** turned
-3.0%/yr into **+3.9%/yr** and cut the drawdown from -18% to -6.6%; **giving back
40% of peak profit** was almost as good. Requiring the break to hold longer barely
helped, and the SHA cross was worse than doing nothing.

Step 9 also carries four newer anchors: **Last Bar Beyond Nearest SHA · Last Bar
Beyond Furthest SHA · Last SHA Bar Beyond Nearest SHA · Last SHA Bar Beyond
Furthest SHA** — the most recent bar with any part past the SHA, i.e. the last
place price was genuinely on the wrong side of the trend. On EUR/USD the two
*furthest* variants roughly quadrupled the risk-adjusted result against the swing
anchor: similar return, about a fifth of the drawdown.

Roughly **2,000 runs** in total, a few minutes on the compiled engine.

---

## Step 24 — what max equity means

The ceiling on how large one position may be, as a percent of the account.

- **100%** — cash account. A $100k account can hold a $100k position. No borrowing.
- **200%** — margin account. A $100k account can hold a $200k position; $100k of it
  is borrowed. This is roughly what a real stock margin account permits.

It matters because risk-based sizing sometimes asks for more than the account holds:
risking 1% with a stop 0.25% away needs a position worth four times the account.
Below the ceiling the trade is silently shrunk and the real risk ends up lower than
requested.

**400% was dropped.** The engine treats borrowed money as free — no interest, no
margin call, no gap risk through the stop. At 4x those omissions stop being a rounding
error. 100% and 200% are positions that could actually be held.

---

## Step 25 — timeframes and the exit mode, together

Run last, against the locked set. Only valid trios: **base < HTF1 < HTF2**, each at
least one step apart.

**Sweep the exit mode alongside the timeframes, not before them.** Whether to hold a
trade until the stop is hit — rather than exiting when the layers stop agreeing —
turns out to depend entirely on the base timeframe, so locking it earlier in the
sequence gives the wrong answer:

| Market | Base | Exit on misalignment | Hold until stopped |
|--------|------|---------------------:|-------------------:|
| QQQ | 15m | -3.0%/yr, 623 trades | **+3.1%/yr, 71 trades** |
| SPY | 15m | -3.1%/yr, 635 trades | **+3.0%/yr, 43 trades** |
| EUR/USD | 15m | -13.3%/yr, 420 trades | **+1.6%/yr, 10 trades** |
| QQQ | 5m | -19.9%/yr | -5.5%/yr |
| EUR/USD | 4h | **+2.2%/yr, 293 trades** | +0.8%/yr, 17 trades |

On a fast chart the base layer flips constantly, so exiting on misalignment churns
and pays a spread every time; holding lets the slow layers play out. On a 4-hour
base the churn is mild and the misalignment exit wins instead. Hold-until-stopped
needs no new code — it is simply **Alignment-Break Exit = off**.

**Reverse On Stop** (flip to the opposite side when stopped, only if that side is
fully aligned) is built and defaults to off. It has yet to earn a place: with the
misalignment exit on it never fires, because trades almost always end on that exit
rather than on the stop. Worth re-testing in the fast-base configurations where the
stop is the only way out.

| Base | HTF1 | HTF2 |
|------|------|------|
| 15m | 1h | 4h · 1D |
| 15m | 4h | 1D · 1W |
| 1h | 4h | 1D · 1W |
| 1h | 1D | 1W |
| 4h | 1D | 1W · 1M |
| 1D | 1W | 1M |

**Data still needed:** a Daily base requires Monthly, and only BTC has a monthly
file. EUR/USD, QQQ and SPY each need a 1M export before their Daily-base rows can
run. Everything else is already stored in `data/`.

---

## Why the plan is sequential and not exhaustive

Running every combination of every step at once:

- **412,782,428,160,000 combinations** — about 413 trillion
- One core at 1.27 ms each: **16,600 years**. A thousand cores: 17 years. A million
  cores: 6 days.

Compute is not the real obstacle. **Statistics is.** The test asks a setting to stay
profitable in at least 4 of 5 periods. Pure coin-flipping passes that **18.8%** of
the time — so 413 trillion combinations would yield roughly **77 trillion** false
winners on 14,000 bars of price data. The best-looking result would be the most
flattering accident in an ocean of noise, and it would fail on contact with a live
market.

Fewer, ordered tests are not a compromise for lack of hardware. They are the correct
method: each step asks one question against a locked baseline, so a survivor means
something.

**Where extra compute is worth spending:** joint sweeps of variables that plausibly
depend on each other — stop anchor with trail anchor, smoothing with exit trigger,
trail activation with break-even. A few thousand runs each. This covers the one real
weakness of testing variables one at a time, which is missing combinations that only
work together. The existing 6,480-run grid already covers seven variables jointly and
should be kept as a cross-check.

---

## Rules that must not be relaxed

- **len1 ≥ 2 and len2 ≥ len1** on every smoothing pair. Length 1 disables that EMA
  pass. 1,1 is a plain Heikin-Ashi, not a Smoothed Heikin-Ashi — any result from it
  measures a different indicator.
- **Never rank on raw return or on a bare ratio.** Return per year against the worst
  dip, gated on block consistency. A tiny drawdown alone must not win a top spot.
- **The higher-timeframe offset must follow the BASE bar's duration**, not a fixed
  15 minutes. A hardcoded offset leaks the daily value early on any chart faster
  than 15m — a look-ahead that makes fast-base results look falsely good.
- **Never rebuild one timeframe from another.** Use the native export per timeframe;
  BTC's 1h and 4h files disagree by about $224 when aggregated.
- **Charge trading costs on every fill.** 0.20% round trip for crypto, 0.02% for
  forex and large ETFs. Running without them erased nothing less than the entire
  EUR/USD edge once they were applied.
- **Position sizing is fractional** — risk divided by stop distance. Whole-unit
  rounding forced one whole Bitcoin per trade and ignored the risk setting entirely.
- **Keep every result, including the failures.** The full grid stays on the page
  underneath the top settings.

---

## Entry types

| Strategy | State |
|----------|-------|
| Full alignment | tested — 25,920 runs across 4 markets |
| Price above all | **built, not yet tested** — see `PRICE_ABOVE_ALL_SPEC.md` |
| Partial alignment (2 of 3) | spec locked, not built |
| Full cluster cross | not built |
| Pullback resume | not built |
| Early trend | not built |
| Trend continuation | not built |
| ~~High-timeframe price cross~~ | folded into Price Above All as `HTF2 only` |
| ~~Mid-timeframe price cross~~ | folded into Price Above All as `HTF1 only` |
