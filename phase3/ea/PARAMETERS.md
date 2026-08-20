# Parameter reference

Every input in `AsiaBreakout_EA_v1.mq4`, what it does, and when you would
change it. The indicator `AsiaBreakout_Visualizer_v1.mq4` shares the strategy
inputs so you can see the effect of a change on history before applying it
live — **keep the two sets identical or the picture stops describing the
robot.**

Anything measured in **points** is raw `Point` units, not pips. On a 5-digit
EURUSD feed 1 pip = 10 points, so 30 points = 3 pips.

---

## STRATEGY

| Input | Default | What it does |
|---|---|---|
| `InpMode` | Asia range | `MODE_ASIA_RANGE` trades the Asia session high/low. `MODE_TRIGGER_CANDLE` trades one nominated candle's high/low. `MODE_BOTH` runs both on separate magic numbers |
| `InpSignalTF` | H1 | The timeframe whose **bar closes** confirm entries and stops. This is the single most consequential input: a lower timeframe reacts sooner and stops out more; a higher one gives the trade more room and enters later |
| `InpTPPctOfATR` | 80 | Target size as a percentage of the 5-day ATR, measured **from the structural level**, not from the entry. Lower it and more days become tradeable but each win is smaller; raise it and more days get skipped for `target behind entry` |
| `InpTradeLongs` / `InpTradeShorts` | both on | Direction filters. Turn one off to test a directional bias |

---

## ASIA SESSION

| Input | Default | What it does |
|---|---|---|
| `InpAsiaTZ` | UTC | Which clock the hours below are expressed in. UTC means a fixed GMT band all year; a market timezone means the window follows that market's DST |
| `InpAsiaStartHour` / `Min` | 22:00 | Session start |
| `InpAsiaEndHour` / `Min` | 09:00 | Session end. **This is also the moment the range is final** — no breakout can be evaluated before it. Windows that cross midnight are supported |
| `InpRangeTF` | M15 | The timeframe the high/low are measured on. M15 finds a tighter, more accurate range than H1 because a bar only counts if it opens *and* closes inside the window. M5 is tighter still at the cost of more history |

Asia defaults to a fixed GMT band because Sydney and Tokyo pull in opposite
directions — Tokyo has no DST, Sydney's runs in the southern summer — so no
single local clock describes the pair.

---

## TRIGGER CANDLE

Only used in `MODE_TRIGGER_CANDLE` and `MODE_BOTH`.

| Input | Default | What it does |
|---|---|---|
| `InpTriggerTZ` | London | Clock the trigger hour is in. `TZ_LONDON` follows the true London open through DST (07:00 GMT summer, 08:00 GMT winter); `TZ_UTC` freezes it to a GMT hour |
| `InpTriggerHour` / `Min` | 08:00 | The candle's **open** time. It must land on a bar boundary of `InpTriggerTF` — 08:30 on an H1 trigger finds nothing, and the EA warns on init |
| `InpTriggerTF` | H1 | Which candle. H4 makes the trigger the first four hours of London |
| `InpCandleSLSource` | Trigger candle | Where the stop and exit level come from in candle mode. `CSL_ASIA_SESSION` uses the Asia range instead — a much wider stop. **Note:** with the default sessions the trigger candle closes at 08:00 GMT but the Asia range is not final until 09:00 GMT, so `CSL_ASIA_SESSION` skips with `levels not ready` until then |

---

## 5-DAY ATR

| Input | Default | What it does |
|---|---|---|
| `InpATRDays` | 5 | Completed daily bars averaged. Larger is smoother and slower to react to a volatility change |
| `InpATRSkipSunday` | true | Drops the broker's stunted Sunday candle. FOREX.com prints a 2–3 hour Sunday bar whose tiny range drags a 5-day average down materially and shrinks every target. Leave this on unless your broker has no Sunday bar |

---

## ENTRY FILTERS

| Input | Default | What it does |
|---|---|---|
| `InpBreakoutBufferPoints` | 0 | Extra distance beyond the level the bar must close, on top of the level itself. Use it to reject closes that only just clear the level |
| `InpMaxSpreadPoints` | 30 | Refuse an entry when the spread is wider than this. Raise it for exotics, lower it for majors. **The indicator cannot apply this** — historical spread is not recorded |
| `InpMinRangePoints` | 0 (off) | Skip days whose range is unusually tight — often a holiday, where the breakout is noise |
| `InpMaxRangePoints` | 0 (off) | Skip days whose range is unusually wide. These are the days most likely to trip the `target behind entry` skip anyway |
| `InpMaxSLPoints` | 0 (off) | Skip when the breakout closed so far from the level that the structural stop is unaffordable. The most useful of the three filters |
| `InpNoNewTradesBeforeCloseM` | 30 | No new entries inside this many minutes of the NY close — there is not enough session left for the trade to work |
| `InpTradeMon` … `InpTradeFri` | all on | Weekday filters. Monday and Friday behave differently from midweek on most pairs; the indicator's per-day output will tell you whether that is true for yours |

---

## TRADE CONTROL

| Input | Default | What it does |
|---|---|---|
| `InpMaxTradesPerDay` | 1 | Entries per flavor per day. This is what enforces "one trade a day" on top of the one-at-a-time rule |
| `InpAllowReEntryAfterStop` | false | After a stop-out, allow another entry in the **same** direction if price breaks out again |
| `InpAllowOppositeSameDay` | false | After a stop-out, allow the **opposite** side. Turning this on with `InpMaxTradesPerDay = 2` gives you a stop-and-reverse |
| `InpOneTradeAcrossModes` | true | In `MODE_BOTH`, stop the two flavors being in the market at the same time on the same pair |

The one-trade-at-a-time rule is enforced **per symbol**, by magic number. Two
charts on two pairs will each take a trade — that is by design.

---

## RISK

| Input | Default | What it does |
|---|---|---|
| `InpLotMode` | Fixed | `LOT_FIXED` uses `InpFixedLots`. `LOT_RISK_PERCENT` sizes from the structural stop distance so every trade risks the same fraction of equity |
| `InpFixedLots` | 0.10 | Lot size in fixed mode |
| `InpRiskPercent` | 1.0 | Percent of equity risked in risk mode. **Because the stop is close-based, a realised loss can exceed this** — the structural distance is a planned risk, not a guaranteed one |
| `InpProtectiveSLMode` | ATR % | The disaster stop that goes on the order. `PSL_ATR_PCT` scales with the instrument and works on any pair; `PSL_POINTS` is a fixed distance; `PSL_NONE` sends the order naked |
| `InpProtectiveSLATRPct` | 25 | How far past the structural level the disaster stop sits, as a percent of ATR5. Too tight and it pre-empts your close-based rule; too wide and it stops protecting you. 25% is roughly a third of the way to the target |
| `InpProtectiveSLPoints` | 300 | Same thing as a fixed distance, used when mode is `PSL_POINTS` |

### Why there is a second stop at all

Your stop rule is close-based, so the **EA** decides when a trade is over, not
the broker. If the terminal or the VPS dies with a position open, nothing
limits the loss. The disaster stop is parked far enough past the level that it
cannot fire before your close-based rule under normal conditions, but it will
catch a gap, a flash move, or a dead VPS.

---

## HARD EXIT

| Input | Default | What it does |
|---|---|---|
| `InpNYCloseTZ` | New York | Clock the close time is in. `TZ_NEWYORK` tracks the true 17:00 New York close year-round (21:00 GMT summer, 22:00 GMT winter) |
| `InpNYCloseHour` / `Min` | 17:00 | The hard exit. Everything the EA owns is closed at market at this instant, regardless of P/L and regardless of how near the target is |
| `InpFridayEarlyClose` | false | Use a different, earlier close on Friday |
| `InpFridayCloseHour` / `Min` | 16:00 | The Friday time, when the above is on |

The hard exit also works out which positions have **outlived** their session,
so it still flattens correctly after a terminal or VPS restart.

---

## BROKER CLOCK

The part to get right before anything else.

| Input | Default | What it does |
|---|---|---|
| `InpBrokerOffsetMode` | Auto | `BOFF_AUTO` derives the offset from the terminal on init and prints it. Meaningless in the Strategy Tester, which silently falls back to manual |
| `InpBrokerWinterOffsetHours` | 2 | The server's offset from UTC in **winter**, not right now. FOREX.com and most MT4 servers are UTC+2 winter / UTC+3 summer, so 2 is correct for them |
| `InpBrokerDSTRule` | US | Whether the server clock shifts, and on whose dates. Most MT4 servers follow New York. If your server sits at a fixed offset year-round, set `DST_NONE` and put the real offset in the input above |

**Check this in December.** If your server reads GMT+3 in both summer and
winter it is a fixed-offset server: set `InpBrokerWinterOffsetHours = 3` and
`InpBrokerDSTRule = DST_NONE`.

---

## EXECUTION

| Input | Default | What it does |
|---|---|---|
| `InpSlippagePoints` | 5 | Maximum slippage accepted on a fill |
| `InpOrderRetries` | 3 | Retries on a retryable rejection — requote, off quotes, busy server. Non-retryable errors fail immediately |
| `InpMagicAsia` | 8801 | Identifies the Asia flavor's trades. Change it if another EA on the account already uses it |
| `InpMagicTrigger` | 8802 | Same for the candle flavor. The two must differ |
| `InpTradeComment` | AsiaBO | Prefix on the order comment and in the logs |

---

## DISPLAY AND LOG

| Input | Default | What it does |
|---|---|---|
| `InpDrawObjects` | true | Draw the range box, trigger box, and the live stop and target |
| `InpShowPanel` | true | The status panel — resolved offset, ATR5, today's levels, trades taken, next hard exit, and why the EA is idle |
| `InpWriteCSVLog` | true | Write `MQL4/Files/AsiaBreakout_<symbol>.csv`: every entry, exit and skip with its reason. Exits closed by the broker are reconciled from history, so wins are logged as well as losses |
| `InpColorRange` / `InpColorTP` / `InpColorSL` | — | Chart colours |

---

# Indicator-only inputs

`AsiaBreakout_Visualizer_v1.mq4` takes the same strategy inputs plus these.

| Input | Default | What it does |
|---|---|---|
| `InpDaysToShow` | 60 | Trading days to replay backwards from now. The limit is your chart history, not the EA |
| `InpShowAsiaBox` / `InpShowTriggerBox` | true | Shade the ranges |
| `InpShowLevels` | true | Dotted stop and target lines for each trade |
| `InpShowLabels` | true | The `+1.24R TP` tag at each exit |
| `InpShowSkips` | true | Mark days that produced no trade, with the reason |
| `InpShowPanel` | true | The totals: trades, hit rate, total and average R, best and worst, and the skip breakdown |
| `InpExportCSV` | false | Dump every replayed trade to `MQL4/Files/<tag>_replay_<symbol>_<date>.csv` for analysis in Excel or Python |
| `InpTag` | AsiaBO | Name used in the panel, the log and the CSV filename |

### Reading the chart

| Mark | Meaning |
|---|---|
| Shaded box | The range being broken |
| Up / down arrow | The entry, on the bar the trade would have opened |
| Thick line | Entry price to exit price |
| Green | Exited at the target |
| Red | Exited on a close beyond the structural level |
| Amber | Still open at the NY close, exited there |
| Grey text | A day that was skipped, and why |

### What the replay cannot model

Historical spread, slippage and swap. Entries are drawn at the raw bar open
and exits at the raw level, so the R multiples are slightly kinder than live
trading will be. `InpMaxSpreadPoints` is therefore not applied. Everything
else — the close-based entry, the close-based stop, the touch target, the NY
close, the daily caps, the skip rules — is modelled exactly as the EA runs it.

### Where the target beats the stop

Inside a single bar the **target wins**. That is not an arbitrary tie-break:
the target is a resting order that fills the moment price trades there, while
the stop is not even evaluated until the bar has closed.
