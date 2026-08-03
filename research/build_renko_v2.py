#!/usr/bin/env python3
"""
build_renko_v2.py — builds the two v2 files from one shared engine text:

    3SHA_Renko_Chart_v2.pine       indicator
    Renko_Strategy_v1.pine         standalone strategy (no 3SHA, no PAA)

WHAT V2 CHANGES
The v1 engine silently falls back to the chart bar's own close when intrabar
data is unavailable. TradingView only serves roughly the most recent 100k
intrabars, and that window slides forward with time, so a bar that has fine
feed data today will be recomputed from coarse data months from now — and the
bricks change. A backtest that quietly rewrites its own past.

V2 refuses. No intrabar data means no bricks, no direction, no trades. The
usable range becomes visible instead of silent.

V1 files are untouched. This builder writes new filenames only.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from derive_paar import RENKO_INPUTS, RENKO_ENGINE  # noqa: E402

HERE = Path(__file__).resolve().parent


# ===========================================================================
# Shared engine, adapted to strict mode
# ===========================================================================
def strict_engine():
    e = RENKO_ENGINE

    edits = [
        # 1. no single-bar fallback series
        ("""rk_sc = request.security(rk_sym, renko_feed_tf, close, lookahead = barmerge.lookahead_off)
rk_cc = request.security(rk_sym, timeframe.period, close, lookahead = barmerge.lookahead_off)""",
         """// V2: NO FALLBACK SERIES.
// v1 kept a single chart-bar close to fall back on when the intrabar request
// came back empty. That fallback is exactly the repainting problem: the
// intrabar window slides forward with time, so a bar computed from fine data
// today gets recomputed from coarse data later, and the bricks change. Here
// there is nothing to fall back to, so a bar with no intrabar data simply
// produces no bricks and the state stops advancing.
rk_have = array.size(rk_fc) > 0"""),

        # 2. seed only from real intrabar data
        ("""if rk_box_new and not na(rk_box) and rk_box > 0
    float _seed = na(rk_sc) ? rk_cc : rk_sc
    if array.size(rk_fc) > 0
        _seed := array.get(rk_fc, 0)
    if not na(_seed)
        rk_bot := math.floor(_seed / rk_box) * rk_box
        rk_top := rk_bot + rk_box""",
         """// Seed off the FIRST feed bar of this chart bar, never the last: on a 5-minute
// chart that is one bar along, on a 4-hour chart forty-eight bars along, so
// seeding off the last would start the grid in a different cell on each chart.
// V2 seeds only from real intrabar data. No data, no grid.
if rk_box_new and rk_have and not na(rk_box) and rk_box > 0
    float _seed = array.get(rk_fc, 0)
    if not na(_seed)
        rk_bot := math.floor(_seed / rk_box) * rk_box
        rk_top := rk_bot + rk_box"""),

        # 3. formation gated on having intrabar data
        ("""if barstate.isconfirmed and not na(rk_box) and rk_box > 0 and not na(rk_top)
    // Choose the source arrays FIRST, then index them. Writing this as
    // `size > 0 ? array.get(a, i) : fallback` looks equivalent but is not:
    // Pine can evaluate both sides, and array.get on an empty array is a
    // runtime error that stops the script dead.
    float[] _cs = array.size(rk_fc) > 0 ? rk_fc : array.from(na(rk_sc) ? rk_cc : rk_sc)
    float[] _hs = array.size(rk_fh) > 0 ? rk_fh : array.from(na(rk_sh) ? rk_cc : rk_sh)
    float[] _ls = array.size(rk_fl) > 0 ? rk_fl : array.from(na(rk_sl) ? rk_cc : rk_sl)
    for _s = 0 to array.size(_cs) - 1
        float _c = array.get(_cs, _s)
        float _h = array.size(_hs) > _s ? array.get(_hs, _s) : _c
        float _l = array.size(_ls) > _s ? array.get(_ls, _s) : _c""",
         """if barstate.isconfirmed and rk_have and not na(rk_box) and rk_box > 0 and not na(rk_top)
    for _s = 0 to array.size(rk_fc) - 1
        float _c = array.get(rk_fc, _s)
        float _h = array.size(rk_fh) > _s ? array.get(rk_fh, _s) : _c
        float _l = array.size(rk_fl) > _s ? array.get(rk_fl, _s) : _c"""),

        # 4. gate also requires live intrabar data
        ("""rk_ok_long  = not renko_on or (rk_dir ==  1 and rk_run >= renko_confirm)
rk_ok_short = not renko_on or (rk_dir == -1 and rk_run >= renko_confirm)""",
         """// V2: entries also require intrabar data on THIS bar. Past the edge of the
// intrabar window the renko is not merely stale, it is unknown, and an unknown
// filter must not authorise a trade.
rk_ok_long  = not renko_on or (rk_have and rk_dir ==  1 and rk_run >= renko_confirm)
rk_ok_short = not renko_on or (rk_have and rk_dir == -1 and rk_run >= renko_confirm)"""),
    ]

    # rk_sh / rk_sl were only ever read by the removed fallback. Leaving them
    # would burn two of the forty permitted security calls for nothing.
    dead = """rk_sh = request.security(rk_sym, renko_feed_tf, high,  lookahead = barmerge.lookahead_off)
rk_sl = request.security(rk_sym, renko_feed_tf, low,   lookahead = barmerge.lookahead_off)
"""
    if dead in e:
        e = e.replace(dead, "")
    elif "rk_sh" in e:
        sys.exit("FAIL: rk_sh present but not in the expected form")

    for old, new in edits:
        if e.count(old) != 1:
            sys.exit(f"FAIL: engine anchor not unique/found:\n---\n{old[:110]}...")
        e = e.replace(old, new, 1)
    return e


STRICT_ENGINE = strict_engine()


# ===========================================================================
# Shared inputs, adapted
# ===========================================================================
def strict_inputs(standalone):
    i = RENKO_INPUTS
    if standalone:
        i = i.replace('// ⑨ RENKO FILTER  (non-repainting — see header)',
                      '// RENKO SETTINGS')
        i = i.replace('grp_renko = "⑨ ━━━ RENKO FILTER ━━━"',
                      'grp_renko = "━━━ RENKO ━━━"')
        i = i.replace(
            'renko_on       = input.bool(true, "Enable Renko Filter", tooltip="OFF = this script behaves identically to plain 3SHA-PAA, same trades, same numbers. That is the A/B test: run it off, run it on, compare.", group=grp_renko)',
            'renko_on       = input.bool(true, "Enable Renko", group=grp_renko)')
    return i


# Each engine leaves a different gap, so a small shim declares what is missing.
#
#   rk_have  - was there real intrabar data on this bar? A pure measurement,
#              true in both versions, used for the coverage figure and shading.
#   rk_valid - is the renko state trustworthy enough to trade on? In v2 that
#              means having intrabar data. In v1 it is always true, because v1
#              deliberately keeps forming bricks from coarser prices - gating v1
#              on rk_have would quietly turn it into v2 and make the two
#              versions identical, which is not what v1 is for.
SHIM_V1 = """
// ── COVERAGE SHIM (v1) ─────────────────────────────────────────────────────
// v1 keeps forming bricks when intrabar data runs out, so it never needed to
// know whether it had any. It is still worth measuring: the shading and the
// coverage figure show which stretches were built from coarse fallback prices
// and will therefore change as the intrabar window slides forward.
rk_have  = array.size(rk_fc) > 0
rk_valid = true
"""

SHIM_V2 = """
// ── COVERAGE SHIM (v2) ─────────────────────────────────────────────────────
// rk_have is declared by the strict engine above. Trading validity is the same
// thing here: no intrabar data means the renko is unknown, not merely stale.
rk_valid = rk_have
"""

DIAG = '''
// ── DATA COVERAGE ──────────────────────────────────────────────────────────
// How much of the visible history actually had intrabar data. This is the
// number that tells you whether what you are looking at means anything.
var int rk_bars_ok   = 0
var int rk_bars_none = 0
if barstate.isconfirmed
    if rk_have
        rk_bars_ok := rk_bars_ok + 1
    else
        rk_bars_none := rk_bars_none + 1
rk_cover = rk_bars_ok + rk_bars_none > 0 ? 100.0 * rk_bars_ok / (rk_bars_ok + rk_bars_none) : 0.0
'''


def write(path, text):
    Path(path).write_text(text)
    print(f"  wrote {path}  {len(text)} chars, {text.count(chr(10)) + 1} lines")


if __name__ == "__main__":
    print("shared strict engine built:", len(STRICT_ENGINE), "chars")


# ===========================================================================
# FILE 1 — indicator
# ===========================================================================
IND_HEADER = '''//@version=6
// ============================================================================
// 3SHA — RENKO CHART  (v2)
// ============================================================================
// Companion picture for Renko_Strategy_v1.pine. v1 of this file is unchanged.
//
// WHAT CHANGED FROM v1 — THE ONLY REASON v2 EXISTS:
//   v1 quietly fell back to the chart bar's own close whenever intrabar data
//   was unavailable. TradingView serves roughly the most recent 100,000
//   intrabars, and that window SLIDES FORWARD with time. So a bar computed
//   from fine feed data today gets recomputed from coarse chart data some
//   months from now, and its bricks change. Because the engine carries state
//   forward, one changed brick back there alters everything after it. The
//   practical effect: run a backtest today and again in three months, same
//   settings and same dates, and you get different trades. A backtest that
//   rewrites its own past is worse than a short one.
//
//   v2 refuses. No intrabar data means no bricks, no direction, and no trades.
//   Old history renders BLANK rather than wrong, and the Coverage figure in
//   the status box tells you how much of what you are looking at is real.
//
// HOW TO READ IT:
//   The shaded band is the CURRENT brick; its edges are the live grid lines.
//   It is translucent so your candles stay readable underneath — if it hides
//   them, raise Brick Transparency rather than reaching for the candle toggle.
//   Blue is renko up, red is renko down, grey is warm-up. A flat run is price
//   sitting inside one brick. A step is a brick printing; a tall step means
//   several printed on that bar, a burst you could not have traded piecemeal.
//   A GAP means no intrabar data was available for those bars.
//
//   Only the brick current at each bar's close is drawn, so on a high chart
//   timeframe you see where price ended up rather than the path it took. The
//   engine knows every brick either way. To see them all, drop the chart to a
//   lower timeframe — the bricks are identical, there is simply more room to
//   draw them.
//
// WHAT MAKES IT NON-REPAINTING, TIMEFRAME- AND CHART-TYPE-PROOF:
//   - Brick size holds for a whole reset period and is computed from the
//     period that already FINISHED. It can also be a fixed number, or a
//     percent of price. Anything painted is never redrawn with a new size.
//   - Sizing bars are read from their own fixed timeframe, never the chart.
//   - Bricks are stepped through a pinned feed timeframe, not the chart's
//     bars. Tested at 5m, 15m, 1h, 4h and daily: 1,252 bricks in identical
//     order on all five. Reading the chart's bars gave 344 against 214.
//   - Grid boundaries sit at absolute multiples of the box size from zero, so
//     loading more history never shifts them.
//   - Everything is sized and stepped off ticker.standard(), so Heikin Ashi,
//     Renko, Kagi, P&F, Line Break and Range charts leave the bricks alone.
//   - Formation runs only on CONFIRMED bars.
//
// TWO SETTINGS PEOPLE CONFUSE:
//   "Bar Timeframe For Brick Size" measures HOW TALL a brick is. It is used
//   once per reset period and has no say in when bricks appear.
//   "Brick Formation Feed" is HOW OFTEN price is checked. It has no say in
//   how tall bricks are. They do not interact.
// ============================================================================

indicator("3SHA Renko Chart v2", shorttitle="3SHA-RK2", overlay=true)

'''

IND_DRAW = '''
// ============================================================================
// DRAWING
// ============================================================================
// The brick is a TRANSLUCENT BAND between its edges, not a solid body, so the
// candles underneath stay readable. O(1) per bar - no arrays, no box objects,
// nothing accumulates over history.
rk_live = renko_on and rk_have and not na(rk_box) and not na(rk_top)
rk_base = rk_dir == 1 ? rk_up_col : rk_dir == -1 ? rk_dn_col : color.new(#888888, 0)

rk_pT = plot(rk_live ? rk_top : na, "Brick Top",
             color=rk_edge ? color.new(rk_base, 35) : color.new(#000000, 100),
             style=plot.style_stepline, linewidth=1)
rk_pB = plot(rk_live ? rk_bot : na, "Brick Bottom",
             color=rk_edge ? color.new(rk_base, 35) : color.new(#000000, 100),
             style=plot.style_stepline, linewidth=1)
fill(rk_pT, rk_pB, color=color.new(rk_base, rk_transp), title="Brick Body")

// Shade bars with no intrabar data. These are not neutral - they are unknown,
// and the difference matters.
bgcolor(renko_on and not rk_have and rk_nodata_bg ? color.new(#F23645, 92) : na,
        title="No Intrabar Data")

// Optional price candles. Only for charts where the native candles have been
// switched off in Chart Settings - Pine cannot hide them from here.
plotcandle(show_candles ? open  : na, show_candles ? high : na,
           show_candles ? low   : na, show_candles ? close : na,
           title="Price Candles",
           color       = close >= open ? cndl_up : cndl_dn,
           wickcolor   = close >= open ? cndl_up : cndl_dn,
           bordercolor = close >= open ? cndl_up : cndl_dn)

rk_flipped = rk_dir != rk_dir[1] and rk_dir != 0 and not na(rk_dir[1])
plotshape(rk_marks and rk_live and rk_flipped and rk_dir == 1, "Renko Turned Up",
          shape.triangleup, location.belowbar, color.new(#2962FF, 0), size=size.tiny)
plotshape(rk_marks and rk_live and rk_flipped and rk_dir == -1, "Renko Turned Down",
          shape.triangledown, location.abovebar, color.new(#F23645, 0), size=size.tiny)

// -- STATUS ----------------------------------------------------------------
var table rkt = na
if renko_show_hud and barstate.islast
    rkt := table.new(position.top_right, 2, 6, border_width=1,
         frame_color=color.new(#000000, 40), frame_width=1)
    _bg = color.new(#1A1A1A, 10)
    _hd = not rk_have ? color.new(#F23645, 0) : rk_dir == 1 ? color.new(#2962FF, 0) : rk_dir == -1 ? color.new(#F23645, 0) : color.new(#888888, 0)
    table.cell(rkt, 0, 0, "3SHA RENKO v2", text_color=color.white, bgcolor=_hd, text_size=size.small)
    table.cell(rkt, 1, 0, not rk_have ? "NO DATA" : na(rk_box) ? "WARM-UP" : rk_dir == 1 ? "UP" : rk_dir == -1 ? "DOWN" : "NONE", text_color=color.white, bgcolor=_hd, text_size=size.small)
    table.cell(rkt, 0, 1, "Brick Size", text_color=color.white, bgcolor=_bg, text_size=size.small)
    table.cell(rkt, 1, 1, na(rk_box) ? "-" : str.tostring(rk_box, format.mintick), text_color=color.white, bgcolor=_bg, text_size=size.small)
    table.cell(rkt, 0, 2, "Bricks In A Row", text_color=color.white, bgcolor=_bg, text_size=size.small)
    table.cell(rkt, 1, 2, na(rk_box) ? "-" : str.tostring(rk_run), text_color=color.white, bgcolor=_bg, text_size=size.small)
    table.cell(rkt, 0, 3, "Feed Bars / Chart Bar", text_color=color.white, bgcolor=_bg, text_size=size.small)
    table.cell(rkt, 1, 3, str.tostring(array.size(rk_fc)), text_color=color.white, bgcolor=_bg, text_size=size.small)
    table.cell(rkt, 0, 4, "Data Coverage", text_color=color.white, bgcolor=_bg, text_size=size.small)
    _cvc = rk_cover > 99 ? color.new(#1D9E75, 0) : rk_cover > 80 ? color.new(#B8860B, 0) : color.new(#F23645, 0)
    table.cell(rkt, 1, 4, str.tostring(rk_cover, "#.#") + "% of bars", text_color=color.white, bgcolor=_cvc, text_size=size.small)
    table.cell(rkt, 0, 5, "Avg Range", text_color=color.white, bgcolor=_bg, text_size=size.small)
    table.cell(rkt, 1, 5, na(rk_avg) ? "na" : str.tostring(rk_avg, format.mintick), text_color=color.white, bgcolor=_bg, text_size=size.small)

alertcondition(rk_flipped and rk_dir ==  1, "Renko Turned Up",   "Renko turned UP")
alertcondition(rk_flipped and rk_dir == -1, "Renko Turned Down", "Renko turned DOWN")
'''

IND_EXTRA_INPUTS = '''
grp_draw       = "━━━ DRAWING ━━━"
rk_up_col      = input.color(color.new(#2962FF, 0), "Up Brick", group=grp_draw)
rk_dn_col      = input.color(color.new(#F23645, 0), "Down Brick", group=grp_draw)
rk_transp      = input.int(82, "Brick Transparency", minval=0, maxval=100, tooltip="How see-through the brick is. This is the setting that matters if the renko is hiding your candles: 0 is solid and covers everything, 100 is invisible.", group=grp_draw)
rk_edge        = input.bool(true, "Show Brick Edge Lines", group=grp_draw)
rk_marks       = input.bool(true, "Mark Renko Turns", group=grp_draw)
rk_nodata_bg   = input.bool(true, "Shade Bars With No Intrabar Data", tooltip="Marks the stretches where TradingView had no intrabar data to give, so no bricks could be formed. Those bars are unknown, not neutral.", group=grp_draw)
show_candles   = input.bool(false, "Draw Price Candles", tooltip="Pine cannot hide the chart's own candles, so leave this OFF in normal use. Turn it on only if you have switched the native candles off in Chart Settings. With both on you will see every candle drawn twice.", group=grp_draw)
cndl_up        = input.color(color.new(#26A69A, 0), "Candle Up", group=grp_draw)
cndl_dn        = input.color(color.new(#EF5350, 0), "Candle Down", group=grp_draw)

'''

ind = (IND_HEADER
       + strict_inputs(True).replace('renko_show_hud = input.bool(true, "Show Renko Row In HUD", group=grp_renko)',
                                     'renko_show_hud = input.bool(true, "Show Status Box", group=grp_renko)')
       + IND_EXTRA_INPUTS + STRICT_ENGINE + DIAG + IND_DRAW)
write(HERE / "3SHA_Renko_Chart_v2.pine", ind)
if STRICT_ENGINE not in ind:
    sys.exit("FAIL: engine altered during assembly")
print("  engine text verified byte-identical")


# ===========================================================================
# FILE 2 — standalone strategy
# ===========================================================================
STR_HEADER = '''//@version=6
// ============================================================================
// RENKO STRATEGY  (v1)
// ============================================================================
// A standalone renko strategy. It is NOT part of the 3SHA system: there are no
// smoothed Heikin Ashi layers here, no Price Above All, no alignment. The renko
// direction is the entire signal. Nothing in this file affects, or is affected
// by, any other strategy in the repository.
//
// Companion picture: 3SHA_Renko_Chart_v2.pine. Same engine text, so give both
// the same settings and what you see is what this trades.
//
// THE RULE:
//   Renko turns up   -> go long.
//   Renko turns down -> go short.
//   Optionally wait for a number of bricks to confirm before acting.
//   The position closes when the renko turns back, or at the daily cut-off.
//
// NO STOP, NO TRAIL, NO TARGET - DELIBERATELY:
//   Those were built and then removed. With them in place a result reflects the
//   renko signal and the trade management tangled together, and there is no way
//   to tell which is doing the work. Stripped back, the test measures one thing:
//   what the renko turn is worth on its own. Management can be layered back on
//   afterwards, against a baseline that means something.
//
//   The consequence is that a position is exposed to whatever happens between
//   one turn and the next, capped only by the daily cut-off. Position sizing is
//   percent of equity from the strategy properties, because risk-based sizing
//   divides by the entry-to-stop distance and there is no stop to measure.
//   Set commission before reading anything into the equity curve.
//
// WHY IT REFUSES TO TRADE WITHOUT INTRABAR DATA:
//   TradingView serves roughly the most recent 100,000 intrabars, and that
//   window slides forward with time. A bar computed from fine feed data today
//   would be recomputed from coarse chart data months from now, changing its
//   bricks - and because the engine carries state forward, one changed brick
//   back there alters everything after it. Same settings, same dates, different
//   results, months apart. So where there is no intrabar data there are no
//   bricks, no direction and no trades. The Coverage figure in the status box
//   shows how much of the tested range was real.
//
// BACKTEST HONESTY:
//   This runs on ORDINARY CANDLES and must stay that way. Putting a strategy on
//   a renko chart is what produces those absurd equity curves: the engine treats
//   each brick close as a separate tradable moment, so a burst of five bricks in
//   one real minute becomes five chances to trade at five prices, and it will
//   happily buy the first and sell the last. That trade never existed.
//   Here, several bricks inside one bar change the direction and nothing else -
//   one decision per bar, filled at the real bar close.
//
// WHAT THIS IS FOR:
//   Measuring what the renko signal is worth on its own, so that its value as a
//   filter elsewhere can be judged against something. Treat the numbers as a
//   starting point for testing, not as a finished system.
// ============================================================================

strategy("Renko Strategy", shorttitle="RENKO-S", overlay=true,
     initial_capital       = 10000,
     default_qty_type      = strategy.percent_of_equity,
     default_qty_value     = 100,
     pyramiding            = 0,
     calc_on_every_tick    = false,
     process_orders_on_close = true)

'''

STR_INPUTS = '''
// ============================================================================
// TRADE SETTINGS
// ============================================================================
// There is no stop, no trail and no profit target here by design. A position is
// opened when the renko turns and closed when it turns back, or at the daily
// cut-off, and nothing else touches it. That makes the test measure one thing:
// what the renko signal is worth on its own. Trade management can be layered on
// afterwards, once there is a baseline to compare it against.
grp_trade = "━━━ TRADES ━━━"
allow_longs   = input.bool(true,  "Allow Longs",  group=grp_trade)
allow_shorts  = input.bool(true,  "Allow Shorts", group=grp_trade)
close_on_flip = input.bool(true,  "Close On Renko Flip", tooltip="On a flip, close the open trade. With the opposite direction also allowed, the position reverses on the same bar. With this OFF the only exit left is the daily cut-off.", group=grp_trade)
show_diag     = input.bool(true, "Show Diagnostics Panel", tooltip="Shows every gate an entry has to pass, with its live value, so a strategy taking no trades tells you WHICH condition is stopping it instead of leaving you to guess.", group=grp_trade)
use_reentry_confirm = input.bool(true, "Confirm Re-Entry With A Push", tooltip="Applies to entries that follow an exit, not the first entry of the chart. A long then needs the bar to CLOSE above the previous bar's high, and a short to close below the previous bar's low - price actually pushing, not merely the renko still pointing that way. It can fire on the exit bar itself if that bar already closes beyond.", group=grp_trade)
reenter_same  = input.bool(false, "Re-Enter The Same Swing", tooltip="OFF (default): one entry per renko swing. Once a swing has been traded and exited - by the cut-off, say - it waits for the next turn rather than climbing back in. ON: it may re-open the same swing.", group=grp_trade)

// ── DAILY SESSION CUT-OFF ──────────────────────────────────────────────────
grp_cut = "━━━ DAILY CUT-OFF ━━━"
use_cutoff  = input.bool(true, "Close Everything At A Fixed Time Daily", tooltip="Flattens any open position at the cut-off, whatever its state. Runs on the first bar that CLOSES at or after the cut-off, so on a chart whose bars do not land exactly on it the exit is the first bar to finish past it. On a 1-hour chart a 12:45 cut-off therefore fires at 13:00.", group=grp_cut)
cutoff_hour = input.int(12, "  Hour (24h)", minval=0, maxval=23, group=grp_cut)
cutoff_min  = input.int(45, "  Minute", minval=0, maxval=59, group=grp_cut)
cutoff_tz   = input.string("America/Los_Angeles", "  Timezone", options=["America/Los_Angeles", "America/New_York", "America/Chicago", "Europe/London", "Asia/Kolkata", "Asia/Tokyo", "UTC", "UTC-8", "UTC-5"], tooltip="America/Los_Angeles follows Pacific time and shifts with daylight saving, so the cut-off stays at 12:45 local all year. Pick UTC-8 instead only if you want a fixed offset that does not move - that lands at 12:45 in winter and 11:45 in summer.", group=grp_cut)
cutoff_block= input.bool(true, "  Block New Entries Until Next Day", tooltip="ON: once flattened, nothing new opens until the clock passes midnight in the chosen timezone, so the cut-off is not undone a bar later. OFF: it may re-enter straight away, which usually defeats the point of having a cut-off.", group=grp_cut)

grp_date = "━━━ DATE RANGE ━━━"
use_dates     = input.bool(false, "Limit Date Range", group=grp_date)
date_from     = input.time(timestamp("01 Jan 2020 00:00"), "From", group=grp_date)
date_to       = input.time(timestamp("01 Jan 2030 00:00"), "To", group=grp_date)

grp_cost = "━━━ COSTS ━━━"
comm_pct      = input.float(0.0, "Commission %", minval=0.0, step=0.001, tooltip="Set this before believing any result. Left at zero, the equity curve is fiction - and with no stop in place, position sizes here are large.", group=grp_cost)
slip_ticks    = input.int(0, "Slippage (ticks)", minval=0, group=grp_cost)

'''

STR_LOGIC = '''
// ============================================================================
// TRADING
// ============================================================================
in_date = not use_dates or (time >= date_from and time <= date_to)

// ── DAILY CUT-OFF ──────────────────────────────────────────────────────────
// Measured on the bar's CLOSING time, not its opening time. A bar that opens at
// 12:30 and closes at 13:00 has already carried the position through the
// cut-off, so it is the close that has to be tested.
cut_mins   = cutoff_hour * 60 + cutoff_min
bar_mins   = hour(time_close, cutoff_tz) * 60 + minute(time_close, cutoff_tz)
past_cut   = use_cutoff and bar_mins >= cut_mins
cut_blocks = cutoff_block and past_cut

// ── THE SIGNAL IS AN EVENT, NOT A STATE ────────────────────────────────────
// Testing "flat and renko is up" fires on EVERY bar the renko happens to be up.
// Exited mid-trend, it would pile straight back in on the next bar, and the
// next, producing a stream of trades that have nothing to do with the renko
// turning. The signal has to be the TURN itself.
//
// traded_dir remembers which way this swing was already traded. It clears only
// when the renko actually changes direction, so one swing gives one entry.
flip_up   = rk_dir ==  1 and rk_dir[1] == -1 and rk_valid
flip_down = rk_dir == -1 and rk_dir[1] ==  1 and rk_valid
rk_turned = rk_dir != rk_dir[1] and rk_valid

var int traded_dir = 0
if rk_turned
    traded_dir := 0

armed_long  = rk_ok_long  and rk_dir ==  1
armed_short = rk_ok_short and rk_dir == -1

go_long  = armed_long  and allow_longs  and in_date and (traded_dir != 1  or reenter_same)
go_short = armed_short and allow_shorts and in_date and (traded_dir != -1 or reenter_same)

// ── TRADE STATE ────────────────────────────────────────────────────────────
var float entry_px  = na
var int   entry_bar = na

// Re-entry confirmation. had_exit latches on the first exit and stays set, so
// the very first entry of the chart is unconfirmed and every later one is not.
// exited_now lets an exit and a fresh entry share a bar: strategy.position_size
// does not update until the next bar, so without it the entry block would think
// the position was still open and skip the bar entirely.
var bool  had_exit   = false
bool      exited_now = false

// ── EXITS ──────────────────────────────────────────────────────────────────
// Two, and only two: the renko turning back, and the daily cut-off. Nothing
// else can close a position.
if strategy.position_size > 0 and close_on_flip and flip_down
    strategy.close("L", comment="Flip")
    exited_now := true
    had_exit   := true

if strategy.position_size < 0 and close_on_flip and flip_up
    strategy.close("S", comment="Flip")
    exited_now := true
    had_exit   := true

// Unconditional. It ignores the renko entirely. Skipped only if this bar has
// already exited, so the same bar cannot close the position twice.
if past_cut and strategy.position_size != 0 and not exited_now
    strategy.close_all(comment="Cut-Off")
    exited_now := true
    had_exit   := true

// ── ENTRIES ────────────────────────────────────────────────────────────────
// One decision per bar, filled at the real bar close. Several bricks inside one
// bar move the direction and nothing else.
//
// Size comes from the strategy properties (percent of equity by default). With
// no stop there is no risk distance to size against, so risk-based sizing would
// have nothing to divide by.
confirm_long  = not use_reentry_confirm or not had_exit or close > high[1]
confirm_short = not use_reentry_confirm or not had_exit or close < low[1]

if (strategy.position_size == 0 or exited_now) and not cut_blocks and not na(rk_box) and rk_box > 0
    if go_long and confirm_long
        strategy.entry("L", strategy.long)
        entry_px   := close
        entry_bar  := bar_index
        traded_dir := 1
    else if go_short and confirm_short
        strategy.entry("S", strategy.short)
        entry_px   := close
        entry_bar  := bar_index
        traded_dir := -1

// ── ACTIVITY COUNTERS ──────────────────────────────────────────────────────
// Bricks and flips since the chart began. If flips is 0 or 1 the renko is not
// turning, and a strategy that enters once and holds is behaving correctly -
// the setting to change is the brick size or the reversal, not the code.
var int dg_bricks = 0
var int dg_flips  = 0
if barstate.isconfirmed
    dg_bricks := dg_bricks + rk_bricks
    if rk_dir != rk_dir[1] and rk_dir != 0 and not na(rk_dir[1]) and rk_dir[1] != 0
        dg_flips := dg_flips + 1

// ── STATUS ─────────────────────────────────────────────────────────────────
var table st = na
if renko_show_hud and barstate.islast
    st := table.new(position.top_right, 2, 6, border_width=1,
         frame_color=color.new(#000000, 40), frame_width=1)
    _bg = color.new(#1A1A1A, 10)
    _hd = not rk_valid ? color.new(#F23645, 0) : not rk_have ? color.new(#B8860B, 0) : rk_dir == 1 ? color.new(#2962FF, 0) : rk_dir == -1 ? color.new(#F23645, 0) : color.new(#888888, 0)
    table.cell(st, 0, 0, "RENKO STRATEGY", text_color=color.white, bgcolor=_hd, text_size=size.small)
    table.cell(st, 1, 0, not rk_valid ? "NO DATA" : not rk_have ? "COARSE" : na(rk_box) ? "WARM-UP" : rk_dir == 1 ? "UP" : rk_dir == -1 ? "DOWN" : "NONE", text_color=color.white, bgcolor=_hd, text_size=size.small)
    table.cell(st, 0, 1, "Brick Size", text_color=color.white, bgcolor=_bg, text_size=size.small)
    table.cell(st, 1, 1, na(rk_box) ? "-" : str.tostring(rk_box, format.mintick), text_color=color.white, bgcolor=_bg, text_size=size.small)
    table.cell(st, 0, 2, "Bricks In A Row", text_color=color.white, bgcolor=_bg, text_size=size.small)
    table.cell(st, 1, 2, na(rk_box) ? "-" : str.tostring(rk_run), text_color=color.white, bgcolor=_bg, text_size=size.small)
    table.cell(st, 0, 3, "Position", text_color=color.white, bgcolor=_bg, text_size=size.small)
    _pos = strategy.position_size > 0 ? "LONG" : strategy.position_size < 0 ? "SHORT" : traded_dir != 0 ? "FLAT - swing traded" : "FLAT - waiting for turn"
    table.cell(st, 1, 3, _pos, text_color=color.white, bgcolor=_bg, text_size=size.small)
    table.cell(st, 0, 4, "Data Coverage", text_color=color.white, bgcolor=_bg, text_size=size.small)
    _cvc = rk_cover > 99 ? color.new(#1D9E75, 0) : rk_cover > 80 ? color.new(#B8860B, 0) : color.new(#F23645, 0)
    table.cell(st, 1, 4, str.tostring(rk_cover, "#.#") + "% of bars", text_color=color.white, bgcolor=_cvc, text_size=size.small)
    table.cell(st, 0, 5, "Costs Set", text_color=color.white, bgcolor=_bg, text_size=size.small)
    _cc = comm_pct > 0 ? color.new(#1D9E75, 0) : color.new(#B8860B, 0)
    table.cell(st, 1, 5, comm_pct > 0 ? "yes" : "NO - results are fiction", text_color=color.white, bgcolor=_cc, text_size=size.small)

// ── DIAGNOSTICS ────────────────────────────────────────────────────────────
// Every condition an entry must pass, with its live value. Read top to bottom:
// the first BLOCKED row is what is stopping the strategy trading.
var table dg = na
if show_diag and barstate.islast
    dg := table.new(position.bottom_right, 3, 13, border_width=1,
         frame_color=color.new(#000000, 40), frame_width=1)
    _ok = color.new(#1D9E75, 0)
    _no = color.new(#F23645, 0)
    _nu = color.new(#1A1A1A, 10)
    _hd = color.new(#333333, 0)
    table.cell(dg, 0, 0, "ENTRY GATE", text_color=color.white, bgcolor=_hd, text_size=size.small)
    table.cell(dg, 1, 0, "value",      text_color=color.white, bgcolor=_hd, text_size=size.small)
    table.cell(dg, 2, 0, "",           text_color=color.white, bgcolor=_hd, text_size=size.small)

    _lbl = array.from("Feed bars this bar", "Brick size", "Grid anchored", "Renko direction", "Bricks in a row", "Swing already traded", "In date range", "Re-entry push", "Daily cut-off", "Position", "Bricks formed", "Renko flips")
    _val = array.from(
         str.tostring(array.size(rk_fc)) + (array.size(rk_fc) > 0 ? "" : "  none - fallback"),
         na(rk_box) ? "na - no size yet" : str.tostring(rk_box, format.mintick),
         na(rk_top) ? "na - not anchored" : str.tostring(rk_bot, format.mintick) + " to " + str.tostring(rk_top, format.mintick),
         rk_dir == 1 ? "UP" : rk_dir == -1 ? "DOWN" : "0 - not established",
         str.tostring(rk_run) + " of " + str.tostring(renko_confirm) + " needed",
         traded_dir == 0 ? "no" : traded_dir == 1 ? "yes - long" : "yes - short",
         in_date ? "yes" : "no",
         not use_reentry_confirm ? "off" : not had_exit ? "first entry - not needed" : rk_dir == 1 ? (confirm_long ? "yes - closed above prev high" : "waiting - need close > " + str.tostring(high[1], format.mintick)) : rk_dir == -1 ? (confirm_short ? "yes - closed below prev low" : "waiting - need close < " + str.tostring(low[1], format.mintick)) : "-",
         not use_cutoff ? "off" : str.tostring(cutoff_hour) + ":" + (cutoff_min < 10 ? "0" : "") + str.tostring(cutoff_min) + " " + cutoff_tz + (past_cut ? "  PAST - flat until midnight" : "  before"),
         strategy.position_size == 0 ? "flat - can enter" : strategy.position_size > 0 ? "long - holding" : "short - holding",
         str.tostring(dg_bricks),
         str.tostring(dg_flips) + "   (" + str.tostring(strategy.closedtrades) + " closed trades)")
    _pass = array.from(
         array.size(rk_fc) > 0,
         not na(rk_box) and rk_box > 0,
         not na(rk_top),
         rk_dir != 0,
         rk_run >= renko_confirm,
         traded_dir == 0 or reenter_same,
         in_date,
         rk_dir == 1 ? confirm_long : rk_dir == -1 ? confirm_short : true,
         not cut_blocks,
         true,
         dg_bricks > 0,
         dg_flips > 0)
    for _i = 0 to array.size(_lbl) - 1
        bool _p = array.get(_pass, _i)
        // Rows 0-8 are gates an entry must pass. Rows 9-11 are activity
        // readings: being in a position is not a fault, so they never read
        // BLOCKED.
        bool _info = _i >= 9
        table.cell(dg, 0, _i + 1, array.get(_lbl, _i), text_color=color.white, bgcolor=_nu, text_size=size.small)
        table.cell(dg, 1, _i + 1, array.get(_val, _i), text_color=color.white, bgcolor=_nu, text_size=size.small)
        table.cell(dg, 2, _i + 1, _p ? "ok" : _info ? "none yet" : "BLOCKED",
             text_color=color.white,
             bgcolor = _p ? _ok : _info ? color.new(#B8860B, 0) : _no,
             text_size=size.small)
'''

# ---------------------------------------------------------------------------
# Emit BOTH strategy versions from the same body text.
#
# The only difference between them is which engine goes in. Strategy vN pairs
# with indicator vN by construction: same engine text, asserted below, so the
# picture always matches the trades.
#
#   v1 = permissive engine. Falls back to the chart bar's close when intrabar
#        data runs out. Longer history, but the intrabar window slides forward
#        with time, so old bars get recomputed from coarse data later and their
#        bricks change. Same settings and dates, different results months apart.
#
#   v2 = strict engine. No intrabar data means no bricks and no trades. Shorter
#        tested range, but it does not rewrite its own past.
# ---------------------------------------------------------------------------
V1_NOTE = """// VERSION 1 - PERMISSIVE.
//   Where TradingView has no intrabar data to give, this version falls back to
//   the chart bar's own close and keeps forming bricks from coarser prices.
//   That buys history at a real cost: the intrabar window slides forward with
//   time, so a bar computed from fine data today is recomputed from coarse data
//   months from now and its bricks change. Because the engine carries state
//   forward, one changed brick back there alters everything after it. Run the
//   same backtest today and in three months, same settings and same dates, and
//   the older portion will not reproduce.
//
//   Version 2 refuses to form bricks without intrabar data. Shorter range, but
//   it does not rewrite its own past. Prefer v2 unless you specifically need
//   the extra history and understand what it costs.
//
//   Pair this with 3SHA_Renko_Chart_v1.pine. Same engine text, so the picture
//   matches the trades. Do not mix a v1 chart with a v2 strategy."""

V2_NOTE = """// VERSION 2 - STRICT.
//   TradingView serves roughly the most recent 100,000 intrabars, and that
//   window SLIDES FORWARD with time. Version 1 fell back to the chart bar's own
//   close past its edge, which meant a bar computed from fine data today got
//   recomputed from coarse data months later, changing its bricks - and because
//   the engine carries state forward, one changed brick back there altered
//   everything after it. Same settings, same dates, different results.
//
//   This version refuses. No intrabar data means no bricks, no direction and no
//   trades. The tested range gets shorter, sometimes much shorter, and the
//   Coverage figure in the status box tells you how much of it was real. A
//   backtest that rewrites its own past is worse than a short one.
//
//   Pair this with 3SHA_Renko_Chart_v2.pine. Same engine text, so the picture
//   matches the trades. Do not mix a v2 chart with a v1 strategy."""


def build_strategy(ver, engine, note):
    head = (STR_HEADER
            .replace("// RENKO STRATEGY  (v1)", f"// RENKO STRATEGY  (v{ver})")
            .replace('strategy("Renko Strategy", shorttitle="RENKO-S"',
                     f'strategy("Renko Strategy v{ver}", shorttitle="RENKO-S{ver}"')
            .replace("// Companion picture: 3SHA_Renko_Chart_v2.pine. Same engine text, so give both\n// the same settings and what you see is what this trades.",
                     f"// Companion picture: 3SHA_Renko_Chart_v{ver}.pine. Same engine text, so give\n// both the same settings and what you see is what this trades."))

    # the version note replaces the v2-specific intrabar section wholesale
    old_sec = head[head.index("// WHY IT REFUSES TO TRADE WITHOUT INTRABAR DATA:"):
                   head.index("// BACKTEST HONESTY:")]
    head = head.replace(old_sec, note + "\n//\n")

    logic = STR_LOGIC.replace('"RENKO STRATEGY"', f'"RENKO STRATEGY v{ver}"')
    shim = SHIM_V1 if ver == 1 else SHIM_V2
    body = head + strict_inputs(True) + STR_INPUTS + engine + shim + DIAG + logic
    if engine not in body:
        sys.exit(f"FAIL: engine altered while building v{ver}")
    return body


v1 = build_strategy(1, RENKO_ENGINE, V1_NOTE)
v2 = build_strategy(2, STRICT_ENGINE, V2_NOTE)
write(HERE / "Renko_Strategy_v1.pine", v1)
write(HERE / "Renko_Strategy_v2.pine", v2)

# pair check: each strategy must carry EXACTLY its indicator's engine
pairs = [("Renko_Strategy_v1.pine", "3SHA_Renko_Chart_v1.pine", RENKO_ENGINE),
         ("Renko_Strategy_v2.pine", "3SHA_Renko_Chart_v2.pine", STRICT_ENGINE)]
for sf, inf, eng in pairs:
    st = (HERE / sf).read_text()
    ip = HERE / inf
    ok_s = eng in st
    ok_i = eng in ip.read_text() if ip.exists() else None
    print(f"  pair check {sf} <-> {inf}: strategy {'ok' if ok_s else 'FAIL'}, "
          f"indicator {'ok' if ok_i else ('missing' if ok_i is None else 'FAIL')}")
    if not ok_s:
        sys.exit("FAIL: pair mismatch")

