# Asia / Trigger-Candle Breakout EA — Specification

**Status:** Built — see `phase3/ea/AsiaBreakout_EA_v1.mq4`
**Target:** MT4 (MQL4), Forex.com broker, Forex.com VPS
**Files:** `phase3/ea/AsiaBreakout_EA_v1.mq4`, `phase3/ea/README.md`,
`research/verify_session_clock.py`

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

## 2. The three signal rules

They are deliberately **not** symmetrical:

| | Rule | Why |
|---|---|---|
| **Entry** | Bar must CLOSE beyond the level | A wick through the level is not a breakout |
| **Stop** | Bar must CLOSE back beyond the opposite level | A wick through the stop is not a failure either |
| **Target** | TOUCH — a real broker TP order | Take the money when it is offered |

Everything close-based reads CLOSED bars only (`shift >= 1`). The developing
bar is used for drawing and for the hard-exit clock, never for a signal. A
signal that appears cannot later vanish. This mirrors the discipline in
`phase3/indicators/3SHA_PriceAboveAll_Alerts_v1.mq4`.

### The consequence: the EA holds the stop, not the broker

A close-based stop cannot be a broker stop order — a broker stop fills on a
touch, which is exactly what the rule rejects. The EA therefore evaluates the
stop itself on each bar close, and the position is unprotected if the terminal
or the VPS dies.

So a **disaster stop** is attached to the order, parked beyond the structural
level (default: 25% of ATR5 past it) where it cannot pre-empt the close-based
rule in normal conditions but will still catch a gap, a flash move, or a dead
VPS. `InpProtectiveSLMode = PSL_NONE` disables it, with a warning on init.

Two things follow that are worth stating plainly:

- **A realised loss can exceed the structural stop distance.** Price may close
  far beyond the level on a fast bar. Risk-percent sizing uses the structural
  distance, so it is a planned risk, not a guaranteed one.
- **MT4's tick-mode backtest cannot model this faithfully.** The stop only
  reads bar closes, so "Open prices only" is the honest tester mode. The
  target is a genuine TP order and is modelled correctly at any setting.

## 3. Time and session handling

MT4 has no timezone database and the broker server clock is not GMT. This is
the single most common failure mode for session EAs, so each session carries
its **own** timezone rather than everything sharing one global setting:

| Session | Input | Default | DST rule applied |
|---|---|---|---|
| Asia | `InpAsiaTZ` | UTC | none |
| Trigger candle | `InpTriggerTZ` | London | EU: last Sun Mar 01:00 UTC → last Sun Oct 01:00 UTC |
| Hard exit | `InpNYCloseTZ` | New York | US: 2nd Sun Mar 07:00 UTC → 1st Sun Nov 06:00 UTC |

Tokyo is also selectable and correctly has no DST.

All reasoning happens in UTC, because DST transitions are *defined* in UTC
terms — evaluating them from a UTC instant is exact, with no ambiguous hour:

```
session local time  <--  UTC  -->  broker server time
```

### The broker's own clock

Handled separately from the sessions. `InpBrokerWinterOffsetHours` (default 2)
and `InpBrokerDSTRule` (default US) describe the server, and `BOFF_AUTO`
derives the winter base from `TimeGMT()` on init and prints what it found.

The one approximation is broker → UTC, which must guess the broker's DST state
before it knows the UTC instant. That is ambiguous only inside the one-hour
transition band, which falls at 02:00 New York on a Sunday — the market is
shut.

### What this looks like in practice

On a NY-DST broker clock (FOREX.com and most MT4 servers, UTC+2 winter /
UTC+3 summer):

| | Winter (server UTC+2) | Summer (server UTC+3) |
|---|---|---|
| Asia 00:00–08:00 UTC | 02:00–10:00 server | 03:00–11:00 server |
| Trigger 08:00 London | 10:00 server | 10:00 server |
| NY close 17:00 | 00:00 server | 00:00 server |

London and New York hold a constant server hour; Asia moves, because Tokyo has
no DST. For roughly three weeks each spring and one week each autumn the US and
EU changeover dates diverge and the London trigger sits at 11:00 server. All of
that is correct, and all of it is asserted in
`research/verify_session_clock.py`.

The EA also draws the resolved windows on the chart, which is the fastest way
to catch a misconfigured broker offset.

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

Measured from the structural level, CONFIRMED, not from the entry price:

- Long:  `TP = AsiaLow  + Pct * ATR5`
- Short: `TP = AsiaHigh - Pct * ATR5`

The span from the structural stop to the target is therefore 80% of the 5-day
ATR. The target is placed as a real broker TP order and fills on a touch.

### 4.5 Degenerate-target guard
Under `SL_ANCHOR`, if the Asia range is wider than `Pct * ATR5`, the computed
TP sits at or below the entry (long) — an instantly invalid trade.
CONFIRMED behaviour: **skip the day**, log the reason (`target behind entry`)
and show it on the panel. The target is never fudged outward to make the trade
possible. The same guard applies to Flavor B.

A second expiry guard exists for a case the original spec missed: a level stays
in memory until the next session replaces it, so hours after the NY close the
previous day's range is still loaded. Any level formed before the most recent
hard exit is treated as expired and cannot open a trade, whatever the daily
counters say.

---

## 5. Flavor B — Trigger Candle Breakout

- `InpTriggerTF` (default = `InpSignalTF` = H1) and
  `InpTriggerHour:InpTriggerMin` (default = London open) identify ONE candle
  per day by its OPEN time.
- When that candle closes, `TriggerHigh` / `TriggerLow` are latched and drawn.
- **Long** when a later `InpSignalTF` bar closes above `TriggerHigh + Buffer`.
- **Short** when a later bar closes below `TriggerLow - Buffer`.
- Stop level: long = `TriggerLow`, short = `TriggerHigh`, evaluated on bar
  close like Flavor A.
- TP: identical to §4.4, anchored on the trigger candle low/high.
- Setup expiry: the NY close (via the expired-level guard in §4.5).

### `InpCandleSLSource`

The requirements carried a contradiction here: one line put the candle-mode
stop at the **Asia session** low/high, while the target line and the exit rule
both put it at the **trigger candle** low/high. The trigger candle reading is
the default, because it is the one the other two statements agree on and the
one the original brief specified. `InpCandleSLSource = CSL_ASIA_SESSION`
switches to the wider Asia-based stop without a recompile. The target stays
anchored on the trigger candle either way, as specified.

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

## 9. Trade management beyond the specified rules

**Not implemented.** `phases/phase-3-mt4-ea/spec.md` calls for break-even
moves, partial closes and trailing stops, but none are in this EA: the
strategy under test is exactly the strategy specified above, and every extra
exit rule would change what the results mean. They belong in a v2 once the
base rules have a track record.

## 10. Broker plumbing

- `MODE_STOPLEVEL` and `MODE_FREEZELEVEL` validation. A disaster stop closer
  than the legal minimum is pushed out to it; a TARGET inside the minimum
  means the trade is skipped rather than silently retargeted.
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

## 12. Decisions taken

| Question | Answer |
|---|---|
| Target anchor | From the structural level, not the entry. Span = 80% of ATR5 |
| Entry confirmation | Bar close beyond the level |
| Stop confirmation | Bar close back beyond the opposite level |
| Target fill | Touch — a real broker TP order |
| Range wider than the target | Skip the day |
| Daylight saving | Real DST rules per session timezone, verified in `research/verify_session_clock.py` |
| Candle-mode stop source | Trigger candle, switchable to Asia via `InpCandleSLSource` |

Still on defaults, all changeable from the inputs panel without a recompile:

- Asia window 00:00–08:00 UTC.
- One trade per flavor per day; no re-entry after a stop-out; no opposite side
  the same day.
- Fixed 0.10 lots (`LOT_RISK_PERCENT` at 1% is available).
- No pair-specific spread or range filters set.

## 13. Build status

1. This spec.
2. `phase3/ea/AsiaBreakout_EA_v1.mq4` — the EA. Built.
3. `phase3/ea/README.md` — install, clock verification, input reference. Built.
4. `research/verify_session_clock.py` — Python port of the EA's time functions
   with the DST cases as assertions. Built, passing.
5. Not built: an offline Python replay of both flavors over historical OHLC.
   Worth doing before the EA touches a live account, because MT4's own tester
   cannot model a close-based stop honestly in tick mode.
