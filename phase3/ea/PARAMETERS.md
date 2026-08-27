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

---

# v2 changes

`AsiaBreakout_EA_v2.mq4` and `AsiaBreakout_Visualizer_v2.mq4` supersede the v1
files. The v1 pair still works and is unchanged; v2 adds the following.

## Three independent timeframes

They were always separate inputs, but v1 buried them in three different
groups. v2 puts them together so it is obvious they do not have to match.

| Input | Default | What it governs |
|---|---|---|
| `InpSignalTF` | H1 | The bars whose **closes** confirm a breakout entry and a close-based stop |
| `InpTriggerTF` | H1 | The candle whose high/low become the levels in trigger-candle mode. Nothing else uses it |
| `InpRangeTF` | M15 | The bars the Asia high/low are measured from. Never generates a signal |

An H4 trigger candle broken by an M15 close is valid, and so is the reverse.

## Scaled exit

| Input | Default | What it does |
|---|---|---|
| `InpPartialClosePct` | 50 | Percent of the position closed **at the target, on touch**. The remainder runs to the NY close |
| `InpMoveStopAfterPartial` | false | After the slice is taken, move the runner's close-based stop to the entry price |

- **100** — the whole position goes at the target, as in v1.
- **0** — nothing happens at the target; everything runs to the stop or the NY close.
- **Anything between** — the slice is taken, the runner continues.

The close-based stop still governs the runner. If a bar closes back beyond the
structural level after the slice has been taken, the remainder exits there
rather than at the NY close.

### The trade-off you are accepting

A broker take-profit closes a **whole** position, so a scaled exit cannot be a
resting TP order. When `InpPartialClosePct` is between 0 and 100 the EA watches
the target itself, tick by tick. **If the terminal is offline when price
reaches the target, the slice is not taken.** The disaster stop stays
broker-side either way. At exactly 100 the target goes back to being a real TP
order, because nothing needs slicing.

There is also a lot-size floor: both the slice and the runner must clear the
broker's minimum lot. At 0.10 lots with a 50% split each leg is 0.05, which is
fine on most accounts. If the split is impossible the EA logs it loudly and the
target closes the whole position instead.

## Repeat entries

| Input | Default | What it does |
|---|---|---|
| `InpMaxTradesPerDay` | 4 | Entries per flavor per day (was 1) |
| `InpMaxOpenPerDirection` | 1 | Positions open at once per direction. This build tracks one; larger values are treated as 1 |
| `InpRequireReset` | false | Price must close back **inside** the range before that direction can trigger again |

A long and a short can now be live at the same time — they are separate trades
with their own stop, target and partial state. Two longs at once is what the
rule forbids.

`InpAllowReEntryAfterStop` and `InpAllowOppositeSameDay` are gone; the two
inputs above replace them.

### Two consequences worth understanding

**The runner blocks the slot.** While a runner is open, that direction is
full, so the next long cannot start until the previous one has finished. With
a scaled exit the runner usually lives until the NY close, which in practice
caps most days at one trade per direction — not four. Set
`InpPartialClosePct = 100` if you would rather targets free the slot again.

**Every close beyond the level is a signal.** With `InpRequireReset` off, four
consecutive bars closing above the Asia high are four valid entries, subject
only to the slot being free. Turning it on demands price return inside the
range first, which is usually what people mean by "the next setup".

## Indicator: the history fix

v1 built the replay once, in `OnInit`, before MT4 had loaded the other
timeframes it reads. Those reads failed, nearly every day was discarded as
"no data", and the next attempt did not come until a signal bar closed. The
symptom was an indicator that only seemed to know about the last day or two.

v2 watches how many bars each timeframe holds and rebuilds whenever that grows,
so the picture fills in as history streams down. New display inputs:

| Input | Default | What it does |
|---|---|---|
| `InpIncludeToday` | true | Also replay the day in progress, up to the last closed bar |

The panel now reports the depth of every timeframe the replay depends on and
flags any marked `SHORT`. If days are still missing, open that timeframe's
chart once, or raise **Tools → Options → Charts → Max bars in history**.

### Reading a scaled exit on the chart

| Mark | Meaning |
|---|---|
| Green dot mid-trade | The target was touched and the slice was taken |
| Green leg then coloured leg | Entry to the slice, then the runner to its own exit |
| `TP* +0.90R` | The star means part was scaled out; the R blends slice and runner |

---

# The two stops — read this if the stop looks wrong

The most common confusion with this EA, and the one worth spelling out.

**There are two different stops on every trade, and they are not in the same
place.**

| | Where it sits | Who holds it | What fires it |
|---|---|---|---|
| **Structural stop** | Exactly on the level — the trigger candle low, or the Asia low | The **EA**, in memory | A signal bar **closing** beyond it |
| **Disaster stop** | Well **beyond** the level (default 25% of ATR5 further) | The **broker** | Price **touching** it |

So in the terminal, the **S/L column on your order shows the disaster stop, not
the trigger candle low.** That is not a bug — a broker stop fills on a touch,
which is precisely what a close-based rule rejects, so the structural stop
cannot be a broker order.

Two things follow, and they are the two ways this looks like a broken stop:

1. **Price trades below the trigger low and the trade stays open.** Correct
   behaviour for `STOP_ON_CLOSE`. The bar has to *close* beyond the level. A
   wick through it is not an exit, by the same logic that a wick through the
   high is not an entry.
2. **The trade closes far below the trigger low.** That was the disaster stop,
   not the structural one. In trigger-candle mode this is the sharp edge: the
   structural stop is one candle deep, so a pad sized off the daily ATR can sit
   much further away than the trade's own risk, and a small planned loss
   becomes a large real one.

## `InpStopStyle`

| Value | Behaviour |
|---|---|
| `STOP_ON_CLOSE` (default) | As specified: a bar must close beyond the level. The EA holds the stop; the broker holds a disaster stop further out |
| `STOP_ON_TOUCH` | The broker stop sits **on the level** and fills the moment price reaches it. The close-based rule and the disaster-stop settings are switched off |

If what you actually want is "my stop is the trigger candle low and I want it
respected the moment price gets there", that is `STOP_ON_TOUCH`. Run the
visualiser both ways over the same history before choosing — the two produce
very different trade sets, and the touch stop is hit far more often.

## `PSL_STRUCT_PCT`

A fourth disaster-stop mode, added because the ATR-based pad is the wrong shape
for trigger-candle mode.

| Mode | Pad |
|---|---|
| `PSL_ATR_PCT` | `InpProtectiveSLATRPct`% of the 5-day ATR |
| `PSL_POINTS` | `InpProtectiveSLPoints` points |
| `PSL_STRUCT_PCT` | `InpProtectiveSLStructPct`% of the **entry-to-level distance** |
| `PSL_NONE` | No broker stop at all |

`PSL_STRUCT_PCT` at 50 puts the disaster stop half again as far as the trade's
own risk — so a tight one-candle stop gets a tight pad and a wide Asia-range
stop gets a wide one. Recommended whenever you trade `MODE_TRIGGER_CANDLE`.

## What was actually broken

One real bug, fixed: if the EA lost its remembered stop level for an open
position — a restart after the terminal's global variables were cleared, a
recompile with different magic numbers — it printed a warning and carried on
with **no structural stop at all**, leaving the position to the disaster stop
and the NY close. It now rebuilds the level from the flavor's current levels
and says so, and raises a visible alert if even that is impossible.

The entry log, the panel and the init messages now name the two stops
separately, so the broker's S/L field can no longer be mistaken for the
structural stop.

---

# Timeframes: one candle, not three

**Changed.** `InpSignalTF` and `InpRangeTF` are gone, replaced by a single
`InpEntryTF`.

| Input | Default | What it does |
|---|---|---|
| `InpEntryTF` | H1 | Measures the Asia high and low, **and** its close beyond the range is the entry, **and** its close back beyond the level is the stop |
| `InpTriggerTF` | H1 | The trigger candle in trigger-candle mode. Nothing else uses it |

The first `InpEntryTF` candle that closes beyond the range is the trade. Set it
to M5 and the first M5 close beyond the range takes it; set it to H1 and you
wait for an hourly close.

## Why the old split was wrong

`InpRangeTF` measured the box; a separate `InpSignalTF` decided the breakout.
With the shipped defaults that meant M15 boxes and H1 entries — so entries
landed on candles that had nothing to do with the boxes on screen, and looked
arbitrary. That was a design error, not a fault in the trading logic.

The split also bought nothing. When the session boundaries fall on candle
boundaries — which they do for every default session here — **the high and low
of a window are identical whether you read them from M5 candles or H1 candles**,
because an H1 high simply *is* the highest of its M15 highs. Measuring finer
was never changing the box. All it did was decouple the box from the entry.

The one case where the measuring timeframe still matters: a session boundary
that does **not** land on a candle boundary, such as a 09:15 Asia end with
`InpEntryTF = H1`. The straddling candle is excluded, so the range is measured
to 09:00. Keep session times on the boundaries of your entry timeframe and this
never arises.
