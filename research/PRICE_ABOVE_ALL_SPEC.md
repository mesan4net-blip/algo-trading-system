# Price Above All (3SHA-PA) — confirmed design

Second strategy built. Design decisions below are **agreed and locked**. The Pine
strategy exists at `phase1/strategies/3SHA_PriceAboveAll_v1.pine`, derived from
Full Alignment so everything except the entry is inherited unchanged.

Status: **built, not yet tested through the plan.**

---

## What changes: the entry

Full Alignment asks whether each layer is *internally* bullish — its smoothed close
above its smoothed open. This asks something different: **where does PRICE sit
relative to the three lines?**

A layer can point down while price is above it, and the reverse, so the two signals
fire at quite different moments. This is closer to a breakout than a trend-structure
signal.

**Long:** price closes above the selected SHA layers.
**Short:** price closes below them. Longs and shorts independently allowed.

**Which layers is a tested knob** — `Price Must Clear`:

| Option | Meaning |
|--------|---------|
| All three | the strictest, and the default |
| Both higher layers | ignores the chart layer |
| HTF2 only | the old "high-timeframe price cross" signal |
| HTF1 only | the old "mid-timeframe price cross" signal |
| Any two | loosest |

Folding the two single-layer options in here means the planned price-cross signals
no longer need strategies of their own. Eight signals become seven.

**Which edge of the SHA counts** follows the existing `Anchor Uses` setting: Body
compares body edges and ignores wicks on both sides, Wick uses the full extremes.
Same convention as the stop anchors, so there is one rule across the system.

**Firing:** on the FIRST breakout into the condition — the first bar price closes
beyond the lines after it wasn't. It does not re-fire while the condition stays
true. Confirmed (1-bar) or Immediate, same as Full Alignment.

---

## Re-entry after an exit — applies to EVERY strategy

Built into Full Alignment and inherited by all derivatives. Not specific to this
signal.

The entry fires once on the first breakout and never again while the condition
holds, so a trade stopped out mid-move leaves the rest of it untaken. This arms the
setup again after an exit:

- **Long:** fires when a later candle **closes above the exit candle's HIGH**
- **Short:** fires when a later candle **closes below the exit candle's LOW**

Price has to prove it is resuming by clearing the bar it was knocked out on. No
fresh transition required.

Two settings, both on by default:
- **Setup Must Still Hold** — only re-enter while the entry condition is still true
- **Cancel If Setup Breaks** — drop the armed re-entry if the condition fails before
  price clears the exit candle; it re-arms only after another exit

---

## Everything else is inherited

Identical to the Full Alignment list — see `PARTIAL_ALIGNMENT_SPEC.md` for the full
enumeration. In summary: nine stop anchors, body/wick basis, buffer, min-stop,
hard-stop toggle, fractional risk sizing, leverage ceiling, break-even, trailing stop
with four anchors, partial take-profit, reverse-on-stop, gap skip, and all seven
exits.

---

## How to run it

The engine takes the entry mode as a config flag:

```python
cfg.update(entry_mode='price_above', pa_layers='All three')
```

`entry_mode` defaults to `'alignment'` (Full Alignment). Everything else in the
bench — the plan, the ranking, the cost model, the block validation — works
unchanged.

---

## First look, not a verdict

EUR/USD 4h, one smoothing setting, no block validation:

| Entry | Trades | Per year | Worst dip |
|-------|-------:|---------:|----------:|
| Alignment (existing) | 346 | +0.24% | -3.7% |
| Alignment + re-entry | 347 | +0.37% | -3.7% |
| Price above all three | 697 | +0.49% | -9.5% |
| Price above all three + re-entry | 704 | +0.58% | -9.2% |
| Price above HTF2 only | 206 | -0.72% | -14.2% |
| Price above any two | 667 | -4.16% | -39.3% |

Price-above earns more per year but with roughly **two and a half times the
drawdown**, and it trades twice as often — so on return against pain, alignment is
still ahead. Costs are the headwind: this is a higher-frequency signal and costs are
what erased the EUR/USD edge once they were charged properly.

The single-layer options are worse than the full condition, which is mild evidence
the price-cross signals were never worth separate strategies.

Re-entry helps slightly in both modes and adds almost no trades — it fires rarely,
which is what you want from something meant to catch resumptions rather than churn.

**None of this is tested.** One market, one smoothing pair, no time blocks, no
walk-forward. Run it through `TEST_PLAN.md` before drawing any conclusion.
