# AsiaBreakout_EA_v1 — install and configure

MT4 Expert Advisor for two session breakout patterns on one currency pair.

---

## The rules, in one place

| | Asia Range | Trigger Candle |
|---|---|---|
| Level | High/low of the Asia session | High/low of one nominated candle |
| Default | 22:00–09:00 GMT | 08:00 London local, H1 |
| **Entry** | Signal bar **CLOSES** beyond the level | Signal bar **CLOSES** beyond the level |
| **Stop** | Signal bar **CLOSES** back beyond the opposite level | same |
| **Target** | **TOUCH**, 80% of ATR5 from the opposite level | same |
| Hard exit | New York close | New York close |

Long target  = `AsiaLow  + 0.80 × ATR5`  ·  Short target = `AsiaHigh − 0.80 × ATR5`

The three rules are deliberately asymmetric. Entry and stop need a **close**;
the target only needs a **touch**.

---

## Install

1. In MT4: **File → Open Data Folder → MQL4 → Experts**.
2. Copy `AsiaBreakout_EA_v1.mq4` there.
3. In MetaEditor press **F7** to compile. Zero errors expected.
4. Back in MT4, refresh the Navigator, drag the EA onto one chart per pair.
5. Tick **Allow live trading** in the EA's Common tab, and enable the
   **AutoTrading** button on the toolbar.

One chart per pair. The EA reads whatever timeframes it needs through `iTime`
and friends, so the chart's own timeframe does not matter — but putting the
chart on `InpSignalTF` makes the drawn levels much easier to read.

---

## Before the first live trade: verify the clock

This is the step people skip and then wonder why the EA traded the wrong hours.

MT4 has no timezone database. The EA carries its own DST rules instead, so it
must be told what your broker's clock does.

1. Attach the EA to a chart and read the **Experts** tab. It prints:

   ```
   [AsiaBO] Broker winter offset resolved to UTC+2 (DST rule: US).
            Right now the server is UTC+3.
   ```

2. Check that against your broker. FOREX.com, like most MT4 brokers, runs
   **UTC+2 in winter and UTC+3 in summer, on New York DST dates** — which is
   the default (`InpBrokerWinterOffsetHours = 2`, `InpBrokerDSTRule = DST_US`).

3. Look at the chart. The EA draws the Asia box and the trigger candle box
   where it thinks they are. If the box does not sit on the Asia session,
   the clock settings are wrong — fix them before trading, not after.

4. On a NY-DST broker clock the shipped sessions work out like this:

   | | Summer (server UTC+3) | Winter (server UTC+2) |
   |---|---|---|
   | Asia 22:00–09:00 GMT | **01:00–12:00 server** | 00:00–11:00 server |
   | Trigger 08:00 London | **10:00 server** | 10:00 server |
   | NY close 17:00 New York | **00:00 server** | 00:00 server |

   The summer column is the reference table these defaults were set from.

   London and New York hold a constant server hour; Asia moves, because it is
   pinned to GMT. That is correct, not a bug — see below.

   For about three weeks each spring and one week each autumn the US and EU
   changeover dates do not line up, and the London trigger sits at 11:00
   server instead of 10:00. Also correct.

`research/verify_session_clock.py` is a Python port of the EA's time functions
with these cases as assertions. Run it if you change any timezone input:

```
python3 research/verify_session_clock.py
```

### Why Asia is fixed to GMT but London and New York are not

`InpAsiaTZ = TZ_UTC` — Sydney and Tokyo pull in opposite directions. Tokyo has
no DST at all; Sydney's runs in the southern summer, the opposite half of the
year from Europe's. No single local timezone describes the pair, so the Asia
window is a fixed GMT band, and its 11 hours are wide enough to contain both
markets whatever the season. The cost is that it moves an hour in server time
across the broker's own changeover.

`InpTriggerTZ = TZ_LONDON`, `InpNYCloseTZ = TZ_NEWYORK` — these track real
local clocks, so the trigger candle is always the true London open hour and
the hard exit is always the true 17:00 New York close. In GMT terms the London
trigger is 07:00 in summer and 08:00 in winter; the NY close is 21:00 in
summer and 22:00 in winter.

If you would rather freeze London to 07:00 GMT year-round to match the
reference table literally, set `InpTriggerTZ = TZ_UTC` and
`InpTriggerHour = 7`. That is the choice between "the London open" and "07:00
GMT" — they are the same thing only in summer.

### Note: the London trigger sits inside the Asia window

With Asia running to 09:00 GMT and the London trigger candle at 07:00–08:00
GMT (summer), the trigger candle is **inside** the Asia session, and closes an
hour before the Asia range is finalised.

This does not affect `MODE_TRIGGER_CANDLE` on its own — it stops against its
own candle. It matters in two cases:

- `InpCandleSLSource = CSL_ASIA_SESSION`, where the candle flavor needs the
  Asia range that does not exist yet. The EA reports `levels not ready` and
  skips until 09:00 GMT.
- `MODE_BOTH`, where the two flavors simply start at different times.

If you want the trigger candle to be the first *post-Asia* hour instead, set
`InpTriggerTZ = TZ_UTC` and `InpTriggerHour = 9`.

### Strategy Tester

`TimeGMT()` is meaningless in the tester, so `BOFF_AUTO` silently falls back to
the manual offset. Set `InpBrokerWinterOffsetHours` correctly before
backtesting or every session will be off by hours.

---

## Inputs that matter most

| Input | Default | Notes |
|---|---|---|
| `InpMode` | Asia range | Or trigger candle, or both on separate magics |
| `InpSignalTF` | H1 | The timeframe whose closes confirm entries and stops |
| `InpTPPctOfATR` | 80 | Percent of the 5-day ATR, measured from the level |
| `InpAsiaTZ` / hours | UTC, 22:00–09:00 | The Asia window (crosses midnight) |
| `InpTriggerTZ` / hour | London, 08:00 | Which candle is the trigger (07:00 GMT in summer) |
| `InpCandleSLSource` | Trigger candle | Switch to Asia session for a wider stop |
| `InpProtectiveSLMode` | 25% of ATR5 | The disaster stop — see below |
| `InpMaxTradesPerDay` | 1 | Per flavor |
| `InpLotMode` | Fixed 0.10 | Or risk % of equity |
| `InpNYCloseHour` | 17:00 New York | Hard exit |

---

## The disaster stop — read this

The stop rule is **close-based**, so the EA, not the broker, decides when a
trade is over. That means a wick straight through the Asia low does not stop
you out, which is the point. It also means that if the terminal or the VPS
dies with a position open, **nothing** limits the loss.

So a second stop is placed with the order, parked well beyond the structural
level — by default 25% of ATR5 past it. It cannot pre-empt the close-based
rule under normal conditions, but it catches a gap, a flash move, or a dead
VPS.

- `PSL_ATR_PCT` (default) — scales with the instrument, works on any pair.
- `PSL_POINTS` — fixed distance, if you prefer to set it per pair.
- `PSL_NONE` — no broker stop at all. The EA warns on init. Your risk.

Position sizing under `LOT_RISK_PERCENT` uses the **structural** stop
distance. Because the real stop is close-based, a realised loss can exceed the
nominal risk percentage. It is a planned risk, not a guaranteed one.

---

## What gets skipped, and why

The EA logs a reason every time it declines a setup. The panel shows the
latest one.

- **`target behind entry`** — the range is wider than 80% of ATR5, so the
  target computes to a price at or behind the entry. Unwinnable, so the day is
  skipped rather than fudged. Expect this on wide-range days; if you see it
  constantly, your `InpTPPctOfATR` is too low for the pair's typical range.
- **`level expired at NY close`** — the level in memory belongs to a session
  that has already had its hard exit. Dead levels never trade.
- **`stop too far`**, **`range too narrow` / `too wide`**, **`spread`**,
  **`near NY close`**, **`daily cap`**, **`weekday off`** — the filters.

---

## Output

- **Chart** — Asia box, trigger candle box, level lines, and the live stop and
  target of an open trade.
- **Panel** — resolved broker offset, ATR5, today's levels, trades taken, the
  next hard exit, and why the EA is currently idle.
- **`MQL4/Files/AsiaBreakout_<symbol>.csv`** — every entry, exit, and skip,
  with the reason. Exits closed by the broker (a target touch) are reconciled
  from history so wins are logged as well as losses. This feeds the Phase 5
  ML loop.

---

## Known limits

- **One symbol per chart.** The "one trade at a time" rule is enforced per
  symbol, not across your account. Two pairs will each take a trade.
- **No backtest of the close-based stop in tick mode.** MT4's tester models
  ticks inside the bar; since the stop only ever reads bar closes, "Open
  prices only" is the honest tester mode for this EA. The target is a real TP
  order, so that half is modelled correctly at any setting.
- **Daily counters reset at broker midnight.** On a UTC+2/+3 server that is
  exactly the New York close, so it lines up. On a broker whose clock differs,
  the expired-level guard still prevents dead-level trades, but the daily cap
  may reset at a slightly different hour than the session boundary.
