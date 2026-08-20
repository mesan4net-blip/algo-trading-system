# Asia / Trigger-Candle Breakout EA — Specification

**Status:** Draft for approval — no EA code written yet
**Target:** MT4 (MQL4), Forex.com broker, Forex.com VPS
**File to be built:** `phase3/ea/AsiaBreakout_EA_v1.mq4`

---

## 1. Objective

A single MT4 Expert Advisor that trades two related breakout patterns, both
confirmed by BAR CLOSE (never by wick or tick), both risking to a structural
level, both targeting a percentage of the 5-day ATR, and both hard-flat at
the New York close.

| | Flavor A | Flavor B |
|---|---|---|
| Name | Asia Range Breakout | Trigger Candle Breakout |
| Level source | High/Low of the Asia session | High/Low of one nominated candle |
| Default level | Asia session 00:00–08:00 GMT | First hour of London (H1) |
| Long entry | Signal bar CLOSES above the level high | Signal bar CLOSES above trigger high |
| Short entry | Signal bar CLOSES below the level low | Signal bar CLOSES below trigger low |
| Stop loss | Bottom of Asia range (long) / top (short) | Trigger candle low (long) / high (short) |
| Take profit | % of 5-day ATR (default 80%) | % of 5-day ATR (default 80%) |
| Hard exit | NY session close | NY session close |

Both flavors live in ONE EA behind `InpMode`. They share the session engine,
the ATR engine, position sizing, order plumbing and the hard-exit scheduler,
so there is exactly one place for each bug to live.

---

## 2. Signal timing — close-only, no repaint

Every decision reads CLOSED bars only (`shift >= 1`). The developing bar
(`shift 0`) is used for drawing and for the hard-exit clock, never for a
signal. A breakout is evaluated exactly once, on the first tick of the bar
that follows the qualifying close, and the entry is a market order at that
moment.

This mirrors the discipline already used in
`phase3/indicators/3SHA_PriceAboveAll_Alerts_v1.mq4`: a signal that appears
cannot later vanish.

---

## 3. Time and session handling

MT4 has no timezone database and the broker server clock is not GMT. This is
the single most common failure mode for session EAs, so it is handled
explicitly.

- `InpTimeMode` = `SERVER_TIME` | `GMT`. All session inputs are interpreted
  in the selected frame.
- Broker GMT offset is auto-detected as `round((TimeCurrent() - TimeGMT())/3600)`
  and can be overridden with `InpBrokerGMTOffsetOverride` (999 = auto).
- The detected offset, the resolved Asia window and the resolved NY close are
  printed to the Experts log on init and drawn on the chart.

### DST caveat (must be verified visually before going live)

Forex.com's server clock follows New York DST (UTC+2 winter / UTC+3 summer).
Consequences:

- In `SERVER_TIME` mode, **London and NY sit at a constant server hour all
  year**, but the **Asia session drifts one hour** across DST changeovers
  (Tokyo does not observe DST).
- In `GMT` mode, the **Asia session is constant**, but **London and NY drift
  one hour**.

Neither mode is correct for all three sessions at once. The EA therefore
draws the Asia box, the trigger candle box, and the SL/TP levels on the chart
so the windows can be verified by eye. `InpDstShiftHours` allows a manual
one-hour nudge if a changeover lands wrong.

---

## 4. Flavor A — Asia Range Breakout

### 4.1 Building the range
- Window: `InpAsiaStartHour:InpAsiaStartMin` to `InpAsiaEndHour:InpAsiaEndMin`
  (default 00:00 → 08:00). Windows that cross midnight are supported.
- Range is built from `InpRangeTF` bars (default M15) for precision, not from
  the signal TF. Only bars whose OPEN time falls inside the window are used;
  partial bars straddling the boundary are excluded.
- `AsiaHigh` = highest high in window, `AsiaLow` = lowest low in window.
- The range is FINAL at the window end. No breakout can be evaluated before
  that instant.

### 4.2 Entry
On the close of each `InpSignalTF` bar (default H1) inside the trade window:

- **Long** if `Close[1] > AsiaHigh + Buffer`
- **Short** if `Close[1] < AsiaLow  - Buffer`

Strictly greater / strictly less. Buffer is `InpBreakoutBufferPoints` or
`InpBreakoutBufferATRPct`, whichever is configured (default 0).

Entry is a market order on the next tick.

### 4.3 Stop loss
- Long: `AsiaLow  - InpSLBufferPoints`
- Short: `AsiaHigh + InpSLBufferPoints`

### 4.4 Take profit
`ATR5` = 5-day ATR (see §6). `Pct` = `InpTPPctOfATR` / 100 (default 0.80).

`InpTPAnchor = SL_ANCHOR` (default — the reading of "the ATR is considered
from the bottom of the Asia session all the way to the top"):

- Long:  `TP = AsiaLow  + Pct * ATR5`
- Short: `TP = AsiaHigh - Pct * ATR5`

The SL→TP span therefore equals 80% of the 5-day ATR.

`InpTPAnchor = ENTRY` (alternative):

- Long:  `TP = EntryPrice + Pct * ATR5`
- Short: `TP = EntryPrice - Pct * ATR5`

### 4.5 Degenerate-target guard
Under `SL_ANCHOR`, if the Asia range is wider than `Pct * ATR5`, the computed
TP sits at or below the entry (long) — an instantly invalid trade.
`InpOnInvalidTP` decides:

- `SKIP` (default) — no trade, reason logged.
- `USE_ENTRY_ANCHOR` — fall back to §4.4 ENTRY formula.
- `ENFORCE_MIN_RR` — push TP out to `InpMinRR` × SL distance.

The same guard applies to Flavor B.

---

## 5. Flavor B — Trigger Candle Breakout

- `InpTriggerTF` (default = `InpSignalTF` = H1) and
  `InpTriggerHour:InpTriggerMin` (default = London open) identify ONE candle
  per day by its OPEN time.
- When that candle closes, `TriggerHigh` / `TriggerLow` are latched and drawn.
- **Long** when a later `InpSignalTF` bar closes above `TriggerHigh + Buffer`.
- **Short** when a later bar closes below `TriggerLow - Buffer`.
- SL: long = `TriggerLow - InpSLBufferPoints`; short = `TriggerHigh + InpSLBufferPoints`.
- TP: identical to §4.4, anchored on the trigger candle low/high under
  `SL_ANCHOR`.
- `InpTriggerValidUntil` — setup expiry (default: NY close).

---

## 6. The 5-day ATR

- Computed on COMPLETED daily bars only (`shift >= 1`), true-range definition.
- `InpATRDays` default 5, `InpATRTimeframe` default D1.
- `InpATRSkipStuntedDays` (default true): Forex.com prints a short Sunday
  candle whose 2–3 hour range drags the 5-day mean down materially and
  shrinks every target. Daily bars whose range is below
  `InpATRStuntedThresholdPct` (default 25%) of the median of the lookback are
  skipped, and the window extends further back until `InpATRDays` qualifying
  bars are collected.
- ATR is recomputed once per new day, cached, and printed to the log.

---

## 7. Position and risk management

- **One trade at a time per pair.** Enforced by scanning open orders for
  `OrderSymbol() == Symbol() && OrderMagicNumber() == magic`. In `BOTH` mode
  each flavor has its own magic (`InpMagicAsia` 8801, `InpMagicTrigger` 8802)
  so they are independently capped at one.
- `InpOneTradeAcrossModes` (default true) additionally blocks Flavor B while a
  Flavor A trade is open on the same symbol, and vice versa.
- `InpMaxTradesPerDay` default 1.
- `InpAllowReEntryAfterSL` default false.
- `InpAllowOppositeDirectionSameDay` default false.
- Sizing: `InpLotMode = FIXED | RISK_PERCENT`. `InpFixedLots` 0.10;
  `InpRiskPercent` 1.0 sized off the actual SL distance and tick value, then
  rounded to lot step and clamped to broker min/max.

### Filters
`InpMaxSpreadPoints`, `InpMinRangePoints` / `InpMaxRangePoints` (reject
abnormal Asia ranges), `InpMaxSLPoints` (reject breakouts that closed far
from the level, where the structural stop is unaffordable),
`InpTradeMon..InpTradeFri`, `InpMinutesAfterSessionOpen`.

---

## 8. Hard exit — NY close

- `InpNYCloseHour:InpNYCloseMin` (default 17:00 New York = 21:00 GMT winter /
  22:00 GMT summer; constant in server time on a NY-DST broker clock).
- At that time every order carrying the EA's magic on this symbol is closed at
  market and any pending is deleted. Runs regardless of P/L, regardless of how
  close TP is.
- The exit routine is tick-driven with a re-check loop so a requote or a
  momentarily closed market cannot leave a position open. Failure to flatten
  raises an alert and retries.
- `InpFridayEarlyClose` optionally flattens earlier on Friday.

---

## 9. Optional trade management (all OFF by default)

`InpUseBreakEven` (+ trigger distance), `InpUsePartialClose` (+ % and level),
`InpUseTrailingStop`. Included as hooks because
`phases/phase-3-mt4-ea/spec.md` calls for them, but disabled so the strategy
under test is exactly the strategy specified above.

---

## 10. Broker plumbing

- `MODE_STOPLEVEL` and freeze-level validation; SL/TP pushed to the nearest
  legal distance or the trade skipped, per `InpOnStopLevelViolation`.
- 3/5-digit pip normalization.
- ECN fallback: if `OrderSend` with SL/TP is rejected, send naked then
  `OrderModify`.
- Retry with backoff on requotes/off-quotes; every failure logged with the
  MT4 error code.

---

## 11. Observability

- Chart objects: Asia box, trigger candle box, breakout level, SL line, TP
  line, entry marker.
- On-chart panel: resolved GMT offset, today's Asia H/L, ATR5, TP distance,
  trades taken today, next hard-exit time.
- CSV trade log (`Files/AsiaBreakout_<symbol>.csv`): date, mode, direction,
  levels, ATR5, entry, SL, TP, exit reason (TP / SL / NY close), R multiple.
  This feeds the Phase 5 ML loop.

---

## 12. Open questions

1. **TP anchor** — confirm `SL_ANCHOR` (SL→TP span = 80% of ATR5) is the
   intent, vs. measuring 80% of ATR5 from the entry price.
2. **Asia window** — confirm 00:00–08:00 GMT, or specify preferred hours.
3. **Invalid-TP handling** — confirm `SKIP` when the range exceeds 80% ATR5.
4. **Re-entry** — one trade per day only, or allow a second attempt after a
   stop-out?
5. **Opposite direction** — if a long breakout stops out and price then closes
   below the Asia low, take the short?
6. **Sizing** — fixed lots or % risk, and at what value?
7. **Pairs** — which symbols will this run on (affects range/spread filter
   defaults)?

---

## 13. Build plan

1. This spec — approved.
2. `phase3/ea/AsiaBreakout_EA_v1.mq4` — the EA.
3. `phase3/ea/README.md` — install, input reference, DST verification checklist.
4. Optional: `research/asia_breakout_backtest.py` — offline replay of both
   flavors on historical OHLC to sanity-check the rules and the 80% ATR target
   before the EA touches a live account.
