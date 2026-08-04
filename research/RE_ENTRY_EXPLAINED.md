# Re-Entry — What Is Actually Built

This describes the re-entry rule exactly as it stands in the code today
(commit `1fa1f4f`, all five Pine files). Nothing here is a plan or a proposal.
Where something is broken, it says so.

Buy trades are described throughout. Sell trades work identically, upside down.

---

## 1. The problem re-entry exists to solve

The entry signal fires **once**, on the first candle where the buy condition
becomes true. While the condition stays true, it never fires again.

Example. Price closes above the SHA layers, you buy. The trade is stopped out
ten minutes later. Price then runs up for two hours, still above the layers the
whole time.

You get nothing from those two hours. The condition never went false, so it
never went true again, so nothing fired.

Re-entry exists to get you back into that move.

---

## 2. The trigger level

When a trade closes, the code writes down one number:

> **the high of the candle the trade closed on**

Call it the **trigger level**. To get back in, a later candle has to **close
above** it.

This is the whole idea. Price must prove it is resuming by beating the candle
that pushed you out.

---

## 3. The three settings

| Setting | Default | What it does |
|---|---|---|
| **Re-Enter After Exit** | Off | Master switch. Off means no re-entry, ever. |
| **Setup Must Still Hold** | On | Re-entry only allowed while the buy condition is still true. |
| **Raise Bar On Setup Break** | On | Explained in section 4. |

---

## 4. "Raise Bar On Setup Break" — what it does

**The event it watches for:** price stops satisfying the buy condition. In
plain terms, price drops back down into or below the SHA layers.

**What happens when that occurs:** the trigger level is moved up to the
**highest point price has reached in the last N candles**, where N is the Swing
Lookback setting.

**It only ever moves up.** If that recent high is lower than the trigger level
already is, nothing happens. The level never comes down.

### Worked example

- Swing Lookback is 30.
- Trade closes on a candle whose high is 100.50. Trigger level = **100.50**.
- Next candle, price drops to 99.00 — below the layers. The buy condition is
  now false.
- Highest price in the last 30 candles was 100.80.
- Trigger level moves up to **100.80**.
- Price keeps falling for an hour. The trigger level stays at 100.80 — nothing
  lowers it.
- Price recovers and closes back above the layers at 100.40. No entry: 100.40
  is below 100.80.
- Price closes at 101.00. **Both conditions met — re-enter.**

### What it replaced

Before this change, when the buy condition went false the trigger level was
**thrown away entirely**. No number, no re-entry, ever.

That was the bug you hit on the QQQ chart. A trade closes near the top, price
immediately dips below the layers on the very next candle, the trigger level is
deleted, and nothing can get you back in for the rest of the move.

---

## 5. What this does NOT do — the gap you identified

**It does nothing about repeated stop-outs in a sideways market.**

The rule in section 4 only fires when price leaves the condition. If price
chops around while staying above the layers the whole time, the condition never
goes false, so the trigger level is never raised.

Worse: **every exit overwrites the trigger level outright.** It is not raised,
it is replaced with whatever that exit candle's high happens to be.

### Worked example of the problem

Price is drifting sideways, staying above the layers throughout.

| | What happens | Trigger level |
|---|---|---|
| Trade 1 closes | exit candle high is 100.50 | set to **100.50** |
| Price closes 100.60 | above trigger → **re-enter** | cleared |
| Trade 2 closes | exit candle high is 100.30 | set to **100.30** ← went DOWN |
| Price closes 100.40 | above trigger → **re-enter** | cleared |
| Trade 3 closes | exit candle high is 100.10 | set to **100.10** ← down again |
| Price closes 100.20 | above trigger → **re-enter** | cleared |

Three entries. Price has gone nowhere. Each stop-out made getting back in
*easier*, not harder, because the bar dropped every time.

This is the sideways drag. **It is not fixed.** The change in section 4 was
aimed at a different problem and does not touch this one.

---

## 6. The fix for section 5 — not built, needs a decision

The fix is one word: on exit, **raise** the trigger level instead of
**replacing** it. Each stop-out could then only push the bar higher. After two
or three stop-outs in chop, the bar sits at the top of the range and price has
to genuinely break out to get back in.

The open question is when that raised bar ever comes back down. If it only ever
rises, then after a long sideways stretch the bar could sit so high that a
genuine new move can't reach it.

Two candidates:

- **Reset when the setup restarts properly** — that is, price leaves the buy
  condition and later comes back into it. The argument: that is a genuinely new
  setup, so the old bar is stale history and should be forgotten.
- **Never reset within a run of trades** — the bar only clears when a normal
  entry fires. The argument: it is simpler, and any reset rule is another thing
  that can behave unexpectedly.

No decision has been made and nothing has been built.

---

## 7. How the pieces interact

Two separate things must both be true to re-enter (with the default settings):

1. Price closes above the trigger level.
2. The buy condition is currently true.

Because of (2), a pullback and resume is handled with no extra machinery: price
falls back into the layers, the bar gets raised, price comes back out above the
layers and above the raised bar, and you are back in.

---

## 8. Where this applies

All five Pine files carry identical re-entry logic:

- `phase1/strategies/3SHA_PriceAboveAll_v1.pine`
- `phase1/strategies/3SHA_PriceAboveAll_Renko_v1.pine`
- `phase1/strategies/3SHA_FullAlignment_v1.pine`
- `phase1/indicators/3SHA_PriceAboveAll_Alerts_v1.pine`
- `phase1/indicators/3SHA_FullAlignment_Alerts_v1.pine`

---

## 9. Two things to watch when testing

**Swing Lookback now does two jobs.** It sets where stops sit *and* how hard
re-entry is. At 30 the bar is high and re-entry is difficult. At 5 the bar sits
close to price and re-entry is easy. Changing it for one reason silently
changes the other. If that becomes a problem, giving re-entry its own lookback
setting is a one-line change.

**There is no limit on how many times a setup can re-enter.** No count cap, no
time limit. On the MSFT test data, trades lasting 1–3 candles were the single
worst group — 141 of them, −19.1R combined. Re-entry produces more short trades
by design, so that group is the one to watch to judge whether this helped.

---

## 10. Naming, for reference against the code

| Plain English | Code name |
|---|---|
| the buy condition is true | `all_bull` |
| the sell condition is true | `all_bear` |
| trigger level, buy side | `rearm_high` |
| trigger level, sell side | `rearm_low` |
| highest price in the last N candles | `sw_high_lvl` |
| Raise Bar On Setup Break | `reentry_reset` |
