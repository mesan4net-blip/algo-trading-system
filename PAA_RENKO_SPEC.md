# 3SHA-PAAR — Price Above All + Renko Filter

**Status:** Draft spec. No code written. No existing file modified.
**Derived from:** `3SHA_PriceAboveAll_v1.pine` (unchanged, untouched)
**New files this spec will produce:**
- `phase1/strategies/3SHA_PriceAboveAll_Renko_v1.pine`
- `research/derive_paar.py` (derivation script, same pattern as `derive_pa.py`)
- `phase1/indicators/3SHA_Renko_Chart_v1.pine` (companion picture)
- `research/build_renko_indicator.py` (builds the indicator from the same engine text)
- this document, `PAA_RENKO_SPEC.md`

---

## 1. What this strategy is

It is the existing Price Above All strategy with one extra gate bolted on the front.

Before a PAA entry is allowed, a separately-tracked renko direction has to agree with it. Renko says up, PAA longs are allowed. Renko says down, PAA shorts are allowed. Renko disagrees, the entry is skipped and never taken — it is not queued or delayed.

Everything else about PAA stays exactly as it is: entry conditions, exits, stops, re-entry rule, position sizing, cost model. Renko touches entries only.

---

## 2. The one thing that makes this different

The chart is never switched to renko. It stays on the normal time chart — 15m, 4h, whatever the base is.

The renko bricks are tracked as a number running behind the scenes. Nothing is drawn as a chart type, nothing is recalculated backwards, and no past bar ever changes.

This is what makes it non-repainting. The standard TradingView renko chart fails on all three counts.

---

## 3. Brick size and formation — the settings

### Brick size

| Setting | Default | What it does |
|---|---|---|
| `renko_box_mode` | Derived | Derived / Fixed / Percent Of Price |
| `renko_box_fixed` | 0.0020 | Used in Fixed mode. The grid then never moves at all |
| `renko_box_pct` | 0.25 | Used in Percent mode. Frozen at each reset off the price then |
| `renko_reset` | Monthly | Daily / Weekly / Monthly |
| `renko_size_tf` | 30 min | Which bars are measured |
| `renko_avg` | Median | Median or Mean of those bar ranges |
| `renko_mult` | 1.0 | Brick size = average range × this |
| `renko_rth` | off | Size from the regular session only. Equities |
| `renko_round` | 0.0001 | Round to something clean |
| `renko_min` | 0 | Floor |
| `renko_box_max` | 0 | Ceiling, 0 = none |

**Three modes.** *Derived* measures recent bars and recalculates each reset. *Fixed* is the number you type, forever — the grid never moves and parameter sweeps stay clean because only one thing changes at a time. *Percent Of Price* scales with the instrument, which matters for something like QQQ that doubles over the years.

**Median by default.** One gap day, flash spike or bad tick will drag a mean and mis-size every brick that period. A median ignores it. Measured on test data, median and mean produced noticeably different brick counts from the same series.

**Ceiling.** The floor stops a dead period producing a silly-small brick. The ceiling catches the opposite: a data glitch or volatility explosion producing an absurd brick that would silently stop the strategy trading for a whole period, which is the worst kind of failure because nothing looks broken.

**Order of operations** is round, then floor, then ceiling — the ceiling is the last word, so a runaway value cannot slip through by being rounded up past it.

### Brick formation

| Setting | Default | What it does |
|---|---|---|
| `renko_feed_tf` | 5 min | Which bars the engine steps through |
| `renko_trigger` | Close | Close or Wick |
| `renko_rev` | 2 | Boxes needed to reverse |
| `renko_confirm` | 1 | Bricks before entries unlock |

**The feed is pinned**, not taken from the chart. This is what makes the *bricks* timeframe-proof rather than merely their size. `request.security_lower_tf` returns every feed bar inside the current chart bar, so a slow chart still sees the round trips a single chart bar would have hidden.

**Close or Wick.** Close demands a close beyond the boundary — conservative, safe for backtests. Wick only needs price to touch it, which is closer to true renko and more responsive. Inside a single feed bar the engine cannot know whether the high or the low came first, so it always tests the way price was already travelling before testing a reversal. Wick produced about 24% more bricks in testing.

**Nothing is sized or stepped from a modified chart type.** Both the sizing and the formation go through `ticker.standard()`, so Heikin Ashi, Renko, Kagi, Point & Figure, Line Break and Range charts leave the bricks untouched. This covers the renko only — the inherited PAA entry and exit logic still reads the chart's own close, so run this on ordinary candles.

**Formation runs only on confirmed bars.** On history every bar is confirmed so nothing changes there. Live, the current bar contributes nothing until it closes, which is what guarantees nothing already painted can move.

## 4. Where the brick lines sit

Brick boundaries sit at whole multiples of the brick size, counted from a price of zero.

EUR/USD with a 0.0020 brick: 1.0800, 1.0820, 1.0840, and so on.
QQQ with a 1.50 brick: 480.00, 481.50, 483.00, and so on.

They are the same lines no matter how much history is loaded, no matter what date the chart starts, no matter who runs it. This is the second thing the built-in renko gets wrong — its grid is anchored to the first bar on the chart, so scrolling back moves every brick.

---

## 5. What happens when the brick size changes at a month boundary

The grid is tied to the brick size, so a new size means a new grid. This needs handling or it produces a fake signal.

**The rule:** on the bar where a new brick size takes effect —

- The renko direction carries over unchanged. A change in the measuring stick must never flip the signal.
- The current brick's boundaries are re-set to the grid levels either side of the last confirmed close, using the new size.
- No brick prints on that bar. The re-anchor is silent.
- Normal brick formation resumes on the next bar.

---

## 6. How a brick forms

Only ever on a **closed bar**, and only ever off the **closing price**. Highs and lows are ignored. Nothing happens mid-candle.

Current state is a brick with a top and a bottom, one brick-size apart, plus a direction.

- **Direction is up.** A new up-brick prints when the close reaches one brick above the top. A down-brick prints when the close falls to `renko_reversal_boxes` bricks below the top.
- **Direction is down.** A new down-brick prints when the close reaches one brick below the bottom. An up-brick prints when the close rises `renko_reversal_boxes` bricks above the bottom.

With `renko_reversal_boxes = 2` this is standard renko: it takes one brick to keep going, two to turn around. Setting it to 1 makes the renko flip on every single crossing, which is much twitchier.

**More than one brick on the same bar is allowed.** If a bar closes far enough to print four bricks, four bricks print. See section 8 for why that does not turn into four trades.

---

## 7. When the filter actually flips

Separate from the brick geometry above.

`renko_confirm_bricks` is the number of bricks in a row in the new direction before the filter will permit entries that way. Default 1 — the filter flips the moment direction flips.

Setting it to 2 or 3 means the renko has to commit before entries are unlocked, at the cost of getting in later.

**Filter states:**

| Renko state | PAA longs | PAA shorts |
|---|---|---|
| Up, confirmed | allowed | blocked |
| Down, confirmed | blocked | allowed |
| Not yet established (warm-up) | blocked | blocked |
| Direction flipped, not yet confirmed | blocked | blocked |

**`renko_filter_enabled`** turns the whole gate off. With it off, this file behaves identically to plain PAA — same trades, same numbers. That is the A/B test: run it off, run it on, compare.

---

## 8. Not letting the backtest lie

This is the part that makes most renko backtests worthless and it is worth being blunt about.

When several bricks print inside one real bar, a renko-charted backtest treats each brick close as a separate moment in time and will happily buy at the first and sell at the last. That trade never existed. Those prices happened in the same instant.

**The rule here:** one trade decision per bar, filled at the actual bar close. Extra bricks on a bar change the renko direction and nothing else. They never create an extra fill, an extra entry, or an extra exit.

---

## 9. Full parameter list

| Input | Default | Notes |
|---|---|---|
| `renko_filter_enabled` | on | Off = identical to plain PAA |
| `renko_reset` | Monthly | Daily / Weekly / Monthly |
| `renko_size_tf` | 30 | Timeframe of the bars measured |
| `renko_mult` | 1.0 | Brick size = average range × this |
| `renko_box_round_step` | 0.0001 fx / 0.05 equity | Rounds the brick size to something clean |
| `renko_box_min` | = round step | Floor, stops a dead month producing a silly brick |
| `renko_reversal_boxes` | 2 | Bricks needed to turn around. 2 = standard renko |
| `renko_confirm_bricks` | 1 | Bricks in the new direction before entries unlock |

Everything inherited from PAA is unchanged and is not restated here.

---

## 10. What you give up

- **Bricks arrive in bursts.** In a fast move you get five at once, then nothing for hours. Anything that counts bricks or measures time between them behaves unevenly.
- **No renko chart to look at.** It lives as a number the strategy reads. It can be drawn as boxes on top of the normal chart if you want to see it, but that is a separate indicator file and is not part of this spec.
- **The filter cuts trade count.** Fewer trades means less statistical confidence in the result. Worth watching alongside the win rate.

---

## 11. Reconciliation requirement

Standard applies. The renko state has to be added to the Python engine and the results reconciled against TradingView to the penny before any result from this strategy is trusted. Entry-for-entry, position state, active stop.

The renko direction itself should be reconciled as its own column, not just implicitly through the trade list — a filter that silently disagrees between the two implementations would show up as missing trades and be hard to trace.

---

## 12. Test results — does it actually not repaint?

The Pine engine was ported line-for-line to Python (`renko_repaint_test.py`) and run over 30,000 synthetic 15m bars with deliberately drifting volatility, so that monthly box sizes genuinely change (seven distinct sizes, 0.0006 to 0.0017).

**Timeframe-proof bricks — PASS.** With the feed pinned to 5 minutes, the same series was run on 5m, 15m, 1h, 4h and daily charts. All five produced 1,252 bricks in identical order. Before the feed was pinned this was 344 bricks against 214.

Two real defects were caught getting there. The grid was seeded from the *last* feed bar of the chart bar rather than the first, so a 5-minute chart and a 4-hour chart started their grids in different cells and every brick afterwards sat one place out. And formation was skipped entirely on a re-anchor bar, discarding a number of feed bars that depended on the chart timeframe. Both fixed.

**Timeframe independence of the box size — PASS.** The same price series was rolled up to six timeframes from 15m to weekly and the engine run on each. Across 20 months, the brick size was identical on every timeframe in every month. Zero disagreements. Before the §3 fix, six of twenty months disagreed.

**Frozen history — PASS.** The series was truncated at three different points and re-run. Every surviving bar had identical brick state. Later bars never reach back and change earlier ones.

**Same grid at any history load — PASS after the §3 fix.** Starting the walk at four different points, the box size and brick boundaries matched the full run on 100% of comparable bars. Before the fix this was only 76% at one start point, caused by the partial-first-month problem now closed.

**The gate never loosens.** The decisive test. Across five different start points there were mismatches during warm-up, and in **every single one** the shorter-history run was locked with no trade permitted. There was not one case where less history allowed a trade that full history would have blocked. Less history can only ever make this strategy more conservative, never differently positioned.

Caveat worth stating plainly: this was tested on synthetic data. It proves the algorithm behaves as designed. It does not tell you the filter makes money, and it is not a substitute for reconciling against TradingView on real data.

---

## 13. Open items — need your sign-off before build

1. **Which "number I can set myself" did you mean?** I have specified two separate ones because the question has two honest readings: `renko_reversal_boxes` (how far price must travel to turn the renko around) and `renko_confirm_bricks` (how many bricks before the filter unlocks). Both are in the spec. If you only wanted one, say which and the other comes out.

2. **Bricks form off the close only.** Some renko builds use highs and lows, which makes bricks form sooner. Close-only is the safer choice and fits the rest of the system, but it is a choice, not a fact. Confirm or change.

3. **Renko does nothing to exits.** If the renko flips against an open position, the position stays open and exits on normal PAA rules. Confirm that is what you want — the alternative is a renko-flip exit, which would be a meaningfully different strategy.

4. **`renko_box_multiplier` default of 0.25.** A guess, based on it producing roughly a 15–20 pip brick on EUR/USD and roughly a 1.00–1.50 brick on QQQ. Should be tuned per market once testing starts, in line with preferring market-specialised settings over universal ones.

---

## Amendment log

| Date | Change |
|---|---|
| 2026-07-26 | Initial draft |
| 2026-07-26 | §3 amended after testing: bank days only from fully-observed calendar months. A mid-month start previously produced a different box for the following month, which made bricks depend on history load. Warm-up cost rises from one month to two. |
| 2026-07-26 | §13 added: repaint test results |
| 2026-07-26 | Six additions: pinned formation feed, three box modes (Derived/Fixed/Percent), median averaging, regular-hours sizing, maximum box size, and wick-or-close trigger. Two defects found by the new timeframe test and fixed: grid seeded from the last feed bar instead of the first, and formation skipped on re-anchor bars. |
| 2026-07-26 | Both the sizing average and the brick formation switched to `ticker.standard()`. Previously, switching the chart to Heikin Ashi or Renko fed modified prices into the engine and changed the bricks. |
| 2026-07-26 | §3 replaced with three settings: reset period, sizing bar timeframe, and multiplier. Brick size is now the average range of the sizing bars over the period that just finished. Averaging runs inside the sizing timeframe's context so it cannot vary with the chart. |
| 2026-07-26 | §3 rewritten: brick size now requested from the daily timeframe instead of rebuilt from chart bars, and the monthly freeze anchored in the daily series. The old approach made the brick size depend on the chart timeframe — roughly twice as wide on weekly as on daily. Also replaces calendar-month averaging with a rolling 21-day average, which is what made the daily request possible; this is a departure from the original elicited choice and is flagged as such. |
| 2026-07-26 | Companion indicator added. Its engine is the same text constant the strategy is built from, so the two cannot drift apart. It draws bricks against real time rather than as equal-width renko columns, so a burst of bricks inside one bar reads as one moment rather than several. |
