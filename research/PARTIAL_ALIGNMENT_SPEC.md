# Partial Alignment (2 of 3) — confirmed design

Second entry type. Design decisions below are **agreed and locked**. Build the Pine
strategy first, then the engine, then run the plan in `TEST_PLAN.md`.

---

## Entry

**Exactly two of the three layers agree — not three.** Since every layer is either
bull or bear, "exactly two" means the third is definitively against. Three-of-three
belongs to Full Alignment; keeping them disjoint means the two strategies can be told
apart and later combined without double-counting the same trade.

**Which pair is a tested variable**, because the three pairings are different trades:

| Pair | What it is |
|------|-----------|
| any two | the loose version — all pairings treated alike |
| mid + slow (chart against) | big picture trending, chart pulled back — a pullback entry |
| chart + mid (slow against) | trading against the slow trend — early turn or counter-trend |
| chart + slow (mid against) | the two ends agree, middle disagrees — likely noise |

**Direction** follows whichever way the two agree. Longs and shorts both allowed.

**Confirmation** inherits the Full Alignment setting: Confirmed (1-bar) by default,
Immediate available.

---

## Exit

Same menu as Full Alignment — base flip · HTF1 flip · HTF2 flip · any layer flips ·
all layers flip — **plus one new option specific to this signal:**

- **agreeing pair breaks** — close when the two layers that formed the entry stop
  agreeing with each other.

---

## Everything else

Inherited unchanged from the finalised strategy. No new machinery:

structural stops with the full anchor menu · body/wick basis · buffer and min-stop ·
mental or hard stop · fractional risk-based sizing · break-even · trailing stop ·
partial take-profit · gap skip.

---

## Expectation to hold in mind

Two-of-three is a looser gate, so it will trade considerably more than Full
Alignment. With trading costs now charged on every fill — and costs are what erased
the EUR/USD edge entirely — a higher-frequency signal starts at a disadvantage. It
may well score worse on its own.

That is an acceptable outcome. Its purpose is to catch the continuation and
re-entry trades that Full Alignment structurally cannot: Full Alignment fires only on
the *transition* into agreement and never re-triggers while the trend runs, so being
stopped out mid-trend means missing the rest of the move. Build it, test it honestly,
and judge the combination later — not this signal in isolation.

---

## Build before starting

**Step 8 of the test plan — the base SHA body as a stop and trail anchor.** It does
not exist yet. It belongs to the shared machinery, so Partial Alignment would inherit
the same hole. Build it once, for both strategies, before testing either further.
