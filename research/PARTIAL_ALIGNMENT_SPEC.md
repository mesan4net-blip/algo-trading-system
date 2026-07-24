# Partial Alignment (2 of 3) — confirmed design

Second entry type. Design decisions below are **agreed and locked**. Build the Pine
strategy first — derived from `3SHA_FullAlignment_v1.pine`, not written fresh — then
the engine, then run the plan in `TEST_PLAN.md`.

---

## What changes: the entry

**Exactly two of the three layers agree — not three.** Every layer is either bull or
bear, so "exactly two" means the third is definitively against. Three-of-three
belongs to Full Alignment; keeping them disjoint means the two can be told apart and
later combined without counting the same trade twice.

**Which pair is a tested variable**, because the three pairings are different trades:

| Pair | What it is |
|------|-----------|
| any two | the loose version — all pairings treated alike |
| mid + slow (chart against) | big picture trending, chart pulled back — a pullback entry |
| chart + mid (slow against) | trading against the slow trend — early turn or counter-trend |
| chart + slow (mid against) | the two ends agree, the middle disagrees — likely noise |

**Direction** follows whichever way the two agree. Longs and shorts both allowed.

---

## What changes: one new exit

The existing exit menu gains a single option specific to this signal:

- **the agreeing pair breaks** — close when the two layers that formed the entry
  stop agreeing with each other.

---

## Everything else is inherited — the full list

No new machinery. Every parameter below already exists in the Full Alignment
strategy and carries over unchanged. Listed in full so nothing is quietly dropped,
as happened before with Trigger Candle and the base SHA body anchor.

**Layers**
- Base smoothing: two EMA lengths (default 4, 8)
- HTF1: timeframe + two EMA lengths
- HTF2: timeframe + two EMA lengths
- Rule: length 1 disables a pass, so both must be >= 2 or it is no longer a
  Smoothed Heikin-Ashi

**Entry**
- Confirmation mode: Confirmed (1-bar) · Immediate
- Allow Longs · Allow Shorts (independent)
- Skip Gap Entries + gap threshold %

**Initial stop — nine anchors**
- Trigger Candle
- Swing (Prev N Bars) + lookback
- Base SHA Body
- HTF1 SHA Body
- HTF2 SHA Body
- Last Bar Beyond Nearest SHA
- Last Bar Beyond Furthest SHA
- Last SHA Bar Beyond Nearest SHA
- Last SHA Bar Beyond Furthest SHA
- Anchor basis: Body (open/close) · Wick (high/low)
- Stop buffer · Min stop distance
- Hard Stop toggle (intra-bar and gap-safe) — off means close-based

**Sizing**
- Risk per trade %, fractional — never rounded to whole units
- Max equity per trade % (leverage ceiling)

**Trade management**
- Break-even: on/off, trigger R, offset
- Trailing stop: on/off, anchor (Swing · Base Body · HTF1 Body · HTF2 Body),
  own basis, own buffer, lookback, activation R
- Partial take-profit: on/off, R, percent of position
- Reverse On Stop: flip to the opposite side when stopped, only if that side is
  fully aligned at that moment

**Exits — all seven, plus the new pair-break**
1. Alignment break, with a break-must-hold-N-bars setting
2. Price back through a chosen SHA body (Base · HTF1 · HTF2)
3. Profit target at N R
4. Give-back — closes after handing back a share of peak profit
5. Time stop — N bars without reaching a minimum R
6. Chart SHA crossing the mid SHA
7. Opposite full alignment
8. **NEW: the agreeing pair breaks**

**Accounting, fixed across all tests**
- Trading cost charged on every fill: 0.20% crypto, 0.02% forex and large ETFs
- Higher-timeframe values offset by the BASE bar duration — never a fixed 15
  minutes, which leaks the value early on faster charts
- Validation: full history plus 5 separate time blocks
- Ranking: return per year against the worst drop, gated on block consistency —
  never raw return, never a bare ratio
- Survivor counts are not comparable across grids of different sizes; judge by the
  ranked settings and the chance baseline

---

## Expectation to hold in mind

Two-of-three is a looser gate, so it will trade considerably more than Full
Alignment. With costs charged on every fill — and costs are what erased the EUR/USD
edge entirely — a higher-frequency signal starts at a disadvantage. It may well
score worse on its own.

That is an acceptable outcome. Its purpose is to catch the continuation and
re-entry trades that Full Alignment structurally cannot: Full Alignment fires only
on the transition into agreement and never re-triggers while the trend runs, so
being stopped out mid-trend means missing the rest of the move. Build it, test it
honestly, and judge the combination later — not this signal in isolation.
