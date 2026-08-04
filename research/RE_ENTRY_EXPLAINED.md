# Re-Entry — What Is Actually Built

This describes the re-entry rule exactly as it stands in the code today
(commit `6b72e6c`, all five Pine files).

Buy trades are described throughout. Sell trades work identically, upside down.

---

## 1. The problem re-entry exists to solve

The entry signal fires **once**, on the first candle where the buy condition
becomes true. While the condition stays true, it never fires again.

Example. Price closes above the SHA layers, you buy. The trade closes ten
minutes later. Price then runs up for two hours, still above the layers the
whole time.

You get nothing from those two hours. The condition never went false, so it
never went true again, so nothing fired.

Re-entry exists to get you back into that move.

---

## 2. The rule

Re-enter when **both** are true:

1. The setup is valid again, and
2. A candle **closes above the reference level**.

That is the whole rule.

---

## 3. The reference level

The reference level is the **close** of whichever candle came last:

- the candle the trade exited on, or
- the candle that made the setup invalid.

Whichever happened most recently sets the level. It is not carried forward, not
raised, not dropped — the latest of those two events simply replaces it.

---

## 4. Worked examples

### Straight continuation — no pullback

- Trade closes on a candle that closes at 100.00. Reference = **100.00**.
- Setup is still valid. Price keeps rising.
- A candle closes at 100.30. Above 100.00, setup valid → **re-enter**.

### Setup breaks, then resumes

- Trade closes at 100.00. Reference = **100.00**.
- Price drops back into the layers. That candle closes at 99.00.
  The setup is now invalid, so reference = **99.00**.
- Price falls further to 98.00. Reference stays 99.00 — only the candle that
  *broke* the setup counts, not every candle after it.
- Price recovers and the setup becomes valid again, closing at 99.50.
  Above 99.00, setup valid → **re-enter**.

Note the second example: after the break, the bar to clear is 99.00, not the
original 100.00. Price does not have to climb all the way back.

---

## 5. The two settings

| Setting | Default | What it does |
|---|---|---|
| **Re-Enter After Exit** | Off | Master switch. Off means no re-entry, ever. |
| **Setup Must Still Hold** | On | Requires the setup to be valid. Turning it off leaves only the close-beats-reference test. |

There is no expiry, no cap on how many times a setup can re-enter, and no
toggle for the reference behaviour — it is always on.

---

## 6. Where this applies

All five Pine files carry identical re-entry logic:

- `phase1/strategies/3SHA_PriceAboveAll_v1.pine`
- `phase1/strategies/3SHA_PriceAboveAll_Renko_v1.pine`
- `phase1/strategies/3SHA_FullAlignment_v1.pine`
- `phase1/indicators/3SHA_PriceAboveAll_Alerts_v1.pine`
- `phase1/indicators/3SHA_FullAlignment_Alerts_v1.pine`

---

## 7. One thing to watch when testing

There is no limit on how many times a setup can re-enter. On the MSFT test
data, trades lasting 1–3 candles were the single worst group — 141 of them,
−19.1R combined. Re-entry produces more short trades by design, so that group
is the one to watch to judge whether this helped.

---

## 8. Naming, for reference against the code

| Plain English | Code name |
|---|---|
| the buy condition is true | `all_bull` |
| the sell condition is true | `all_bear` |
| reference level, buy side | `rearm_high` |
| reference level, sell side | `rearm_low` |
| the candle that broke the setup | `all_bull[1] and not all_bull` |
