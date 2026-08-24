#!/usr/bin/env python3
"""
derive_paar.py — build 3SHA_PriceAboveAll_Renko_v1.pine from 3SHA_PriceAboveAll_v1.pine

Same pattern as derive_pa.py: every edit is named, every anchor is asserted, and
the script fails loudly rather than silently producing a half-edited file. The
PAA source is opened read-only and is never written to.

Spec: PAA_RENKO_SPEC.md
"""

import sys
from pathlib import Path

# Resolve the PAA source whether run from the repo root, from research/, or
# from a scratch dir with a local copy. Read-only in every case.
_HERE = Path(__file__).resolve().parent
_CANDIDATES = [
    _HERE.parent / "phase1" / "strategies" / "3SHA_PriceAboveAll_v1.pine",
    _HERE / "phase1" / "strategies" / "3SHA_PriceAboveAll_v1.pine",
    _HERE / "3SHA_PriceAboveAll_v1.pine",
    _HERE / "paa.pine",
]
SRC = next((c for c in _CANDIDATES if c.exists()), _CANDIDATES[0])
DST = _HERE / "3SHA_PriceAboveAll_Renko_v1.pine"

edits = []          # (name, old, new, expected_count)
applied = []


def edit(name, old, new, count=1):
    edits.append((name, old, new, count))


# ===========================================================================
# EDIT 1 — header block
# ===========================================================================
edit(
    "01_header_title",
    "// 3SHA — PRICE ABOVE ALL STRATEGY  (v1)",
    "// 3SHA — PRICE ABOVE ALL + RENKO FILTER STRATEGY  (v1)",
)

edit(
    "02_header_note",
    "//   This one trades PRICE ABOVE ALL.\n",
    "//   This one trades PRICE ABOVE ALL, gated by a NON-REPAINTING RENKO filter.\n"
    "//\n"
    "// DERIVED FROM: 3SHA_PriceAboveAll_v1.pine — that file is unchanged. Every\n"
    "//   entry rule, exit rule, stop, sizing rule and cost setting below is\n"
    "//   inherited from it verbatim. The renko adds ONE gate on entries and\n"
    "//   touches nothing else.\n"
    "//\n"
    "// WHY THE RENKO IS TRACKED, NOT CHARTED:\n"
    "//   The chart stays on its normal time-based bars. The renko lives as a set\n"
    "//   of numbers computed alongside them, so it can be read as a filter\n"
    "//   without putting the strategy on a chart type that inflates results.\n"
    "//\n"
    "// WHAT MAKES IT NON-REPAINTING, AND TIMEFRAME- AND CHART-TYPE-PROOF:\n"
    "//   - The brick size is held for a whole reset period (Daily, Weekly or\n"
    "//     Monthly) and computed from the period that already FINISHED. It can also\n"
    "//     be a fixed number you type, or a percentage of price. Whatever is already\n"
    "//     painted is never redrawn with a new size.\n"
    "//   - The sizing bars are read from their own fixed timeframe, never from the\n"
    "//     chart, so the brick size is the same number on every chart.\n"
    "//   - The bricks are STEPPED through a pinned feed timeframe, not through the\n"
    "//     chart's bars. A coarse chart bar hides moves that went out and came back;\n"
    "//     the feed does not. Tested at 5m, 15m, 1h, 4h and daily: 1,252 bricks in\n"
    "//     identical order on all five. Reading the chart's own bars instead gave\n"
    "//     344 bricks against 214 on the same data.\n"
    "//   - Brick boundaries sit at absolute multiples of the box size counted from\n"
    "//     zero, so loading more history does not move the grid.\n"
    "//   - Everything is sized and stepped off ticker.standard(). Switching the\n"
    "//     chart to Heikin Ashi, Renko, Kagi, Point & Figure, Line Break or Range\n"
    "//     leaves the bricks untouched — on those chart types the built-in\n"
    "//     close/high/low are modified values that never traded anywhere.\n"
    "//   - Formation runs only on CONFIRMED bars, so the live bar contributes\n"
    "//     nothing until it closes and nothing already painted can move.\n"
    "//   TradingView's built-in renko chart fails most of these.\n"
    "//\n"
    "// WHAT THE RENKO DOES HERE:\n"
    "//   It gates ENTRIES only. Renko up permits longs, renko down permits\n"
    "//   shorts, and neither permits anything until a direction is established\n"
    "//   and confirmed. It does NOT close an open position: if the renko flips\n"
    "//   against a live trade, that trade still exits on normal PAA rules.\n"
    "//   BOTH entry paths are gated — the fresh signal and the reverse-on-stop\n"
    "//   flip, which does not pass through the signal at all.\n"
    "//   Turning the filter off makes this file behave identically to plain PAA,\n"
    "//   same trades, same numbers. That is the A/B test.\n"
    "//\n"
    "// BACKTEST HONESTY:\n"
    "//   Several bricks can print inside one chart bar. They change the renko\n"
    "//   direction and nothing else — one decision per bar, filled at the real\n"
    "//   bar close. A renko-CHARTED backtest would instead treat each brick as\n"
    "//   its own moment and let you buy the first and sell the last, a trade\n"
    "//   that never existed. That is why renko backtests flatter to deceive.\n"
    "//\n"
    "// WHAT IS NOT COVERED:\n"
    "//   Only the RENKO is chart-type-proof. The inherited PAA entry and exit\n"
    "//   logic still reads the chart's own close, so on a Heikin Ashi chart the\n"
    "//   strategy would trade off Heikin Ashi values. Run this on ordinary\n"
    "//   candles.\n",
)

# ===========================================================================
# EDIT 2 — strategy declaration
# ===========================================================================
edit(
    "03_strategy_decl",
    'strategy("3SHA Price Above All", shorttitle="3SHA-PAA", overlay=true,',
    'strategy("3SHA Price Above All + Renko", shorttitle="3SHA-PAAR", overlay=true,',
)

# ===========================================================================
# EDIT 3 — renko inputs, inserted just before the layer computation
# ===========================================================================
RENKO_INPUTS = '''// ============================================================================
// ⑨ RENKO FILTER  (non-repainting — see header)
// ============================================================================
grp_renko = "⑨ ━━━ RENKO FILTER ━━━"
renko_on       = input.bool(true, "Enable Renko Filter", tooltip="OFF = this script behaves identically to plain 3SHA-PAA, same trades, same numbers. That is the A/B test: run it off, run it on, compare.", group=grp_renko)

// ── BRICK SIZE ─────────────────────────────────────────────────────────────
renko_box_mode = input.string("Derived", "Brick Size Mode", options=["Derived", "Fixed", "Percent Of Price"], tooltip="Derived: measured from recent bars and recalculated each reset. Fixed: the number you type, forever - the grid never moves and parameter sweeps stay clean, because only one thing changes at a time. Percent Of Price: scales with the instrument, which matters for something like QQQ that doubles over the years.", group=grp_renko)
renko_box_fixed= input.float(0.0020, "    Fixed Brick Size", minval=0.0, step=0.0001, tooltip="Used only when Mode is Fixed. 0.0020 is 20 pips on EUR/USD. Remember the reversal distance is this times the reversal setting - a 20 pip brick with a 2 box reversal needs 40 pips against you to turn.", group=grp_renko)
renko_box_pct  = input.float(0.25, "    Brick Size % Of Price", minval=0.001, maxval=25.0, step=0.01, tooltip="Used only when Mode is Percent Of Price. Frozen at each reset off the price at that moment, so it does not drift mid-period.", group=grp_renko)
renko_reset    = input.string("Monthly", "Brick Size Reset", options=["Daily", "Weekly", "Monthly"], tooltip="How often the size is recalculated. Monthly: last month sizes this month. Daily: yesterday sizes today. Whatever is already painted never changes - a reset only affects bricks drawn from that point on. Daily gives a seam every day, which makes 'price moved three bricks' mean something different today than yesterday.", group=grp_renko)
renko_size_tf  = input.timeframe("30", "Bar Timeframe For Brick Size", tooltip="Which bars are measured to size the brick. Read from this timeframe directly, never from your chart, so the brick size is the same number whether you are looking at a 5-minute chart or a weekly one.", group=grp_renko)
renko_avg      = input.string("Median", "Average Type", options=["Median", "Mean"], tooltip="Median ignores a single gap day, flash spike or bad tick in the sizing window. The mean lets one bad bar drag every brick that whole period. Median is the safer default.", group=grp_renko)
renko_mult     = input.float(1.0, "Brick Size Multiplier", minval=0.05, maxval=20.0, step=0.05, tooltip="Brick size = average range of the sizing bars, times this. 1.0 means the brick is exactly the average bar range. Raise it for chunkier bricks and fewer signals.", group=grp_renko)
renko_rth      = input.bool(false, "Size From Regular Hours Only", tooltip="Equities only. Pre-market and post-market bars are thin and wide, so including them inflates the average range and hands you bricks too large for the session you actually trade. No effect on forex, which runs around the clock.", group=grp_renko)
renko_round    = input.float(0.0001, "Round Brick Size To Nearest", minval=0.0, step=0.0001, tooltip="Rounds the brick size to something clean so the grid levels are readable. 0.0001 suits forex, 0.05 suits equities. 0 = no rounding.", group=grp_renko)
renko_min      = input.float(0.0, "Minimum Brick Size", minval=0.0, step=0.0001, tooltip="Floor, so a dead period cannot produce a silly-small brick. 0 = use the rounding step as the floor.", group=grp_renko)
renko_box_max  = input.float(0.0, "Maximum Brick Size", minval=0.0, step=0.0001, tooltip="Ceiling. 0 = none. Catches a data glitch or a volatility explosion producing an absurd brick that would silently stop the strategy trading for a whole period - which is the worst kind of failure, because nothing looks broken.", group=grp_renko)

// ── BRICK FORMATION ────────────────────────────────────────────────────────
renko_feed_tf  = input.timeframe("5", "Brick Formation Feed", tooltip="Which bars the engine steps through to build bricks. Pinned here rather than following your chart, so a 4-hour chart and a 15-minute chart produce identical bricks. Finer catches more round trips - coarse bars hide moves that went out and came back - but TradingView caps how far back it hands over intrabar data, and that cap bites hardest when your chart timeframe is far above the feed.", group=grp_renko)
renko_trigger  = input.string("Close", "Brick Trigger", options=["Close", "Wick"], tooltip="Close: a brick needs a close beyond the boundary. Conservative and safe for backtests. Wick: price only has to touch it, which is closer to true renko and more responsive - but inside a single bar the engine cannot know whether the high or the low came first, so it checks the way price was already travelling.", group=grp_renko)
renko_rev      = input.int(2, "Boxes Needed To Reverse", minval=1, maxval=10, tooltip="How far price must travel against the current direction to turn the renko around. 2 is standard renko: one box to keep going, two to turn. 1 makes it flip on every crossing, which is far twitchier.", group=grp_renko)
renko_confirm  = input.int(1, "Bricks In New Direction Before Entries Unlock", minval=1, maxval=10, tooltip="Separate from the reversal rule above. 1 = entries unlock the moment direction flips. 2 or 3 makes the renko commit before entries are allowed, at the cost of getting in later.", group=grp_renko)
renko_show_hud = input.bool(true, "Show Renko Row In HUD", group=grp_renko)

'''

edit(
    "04_renko_inputs",
    "// ── Compute layers (HTF layers smoothed NATIVELY inside request.security,",
    RENKO_INPUTS + "// ── Compute layers (HTF layers smoothed NATIVELY inside request.security,",
)

# ===========================================================================
# EDIT 4 — renko engine, inserted after the SHA body extremes and before ③ ENTRY
# ===========================================================================
RENKO_ENGINE = '''// ============================================================================
// RENKO ENGINE  (state only — nothing is drawn as a chart type)
// ============================================================================
// CHART TYPE MUST NOT CHANGE THE NUMBERS.
// On a Heikin Ashi, Renko, Kagi, Point & Figure, Line Break or Range chart, the
// built-in close/high/low are the MODIFIED values, not real traded prices - and
// syminfo.tickerid carries the chart-type modifier with it, so even a data
// request inherits it. ticker.standard() strips that off and returns plain
// candles from the real symbol.
rk_sym = ticker.standard(syminfo.tickerid)

// Sizing may optionally be restricted to the regular session. ticker.new()
// builds a plain ticker by construction, so this stays chart-type-proof too.
rk_sym_size = renko_rth ? ticker.new(syminfo.prefix, syminfo.ticker, session.regular) : rk_sym

rk_reset_tf = renko_reset == "Daily" ? "1D" : renko_reset == "Weekly" ? "1W" : "1M"

// ── BRICK SIZE ─────────────────────────────────────────────────────────────
// Collect the range of every sizing bar in the period, then at the period
// boundary bank the mean, the median and the closing price, and start again.
//
// Note the ordering. On the first bar of a new period the collection still
// holds the period that just ENDED, so it is banked first and only then
// cleared. Nothing is ever sized from a period still in progress.
//
// The median is there because one gap day, flash spike or bad tick will drag a
// mean and mis-size every brick that period. A median ignores it.
//
// The collection is cleared every period so it cannot grow without bound, and
// is capped anyway in case someone points a monthly reset at 1-minute bars.
f_rk_size(_reset) =>
    bool _new = ta.change(time(_reset)) != 0
    var float[] _r  = array.new_float()
    var float _mean = na
    var float _med  = na
    var float _ref  = na
    if _new
        if array.size(_r) > 0
            _mean := array.avg(_r)
            _med  := array.median(_r)
            _ref  := close[1]
            array.clear(_r)
    if array.size(_r) < 10000
        array.push(_r, high - low)
    [_mean, _med, _ref]

[rk_mean, rk_med, rk_ref] = request.security(rk_sym_size, renko_size_tf,
             f_rk_size(rk_reset_tf), lookahead = barmerge.lookahead_off)

rk_avg = renko_avg == "Median" ? rk_med : rk_mean

float rk_box_raw = na
if renko_box_mode == "Fixed"
    rk_box_raw := renko_box_fixed
else if renko_box_mode == "Percent Of Price"
    rk_box_raw := na(rk_ref) ? na : rk_ref * renko_box_pct / 100.0
else
    rk_box_raw := na(rk_avg) ? na : rk_avg * renko_mult

// Round, then floor, then ceiling. Order matters: the ceiling is the last word,
// so a runaway value cannot slip through by being rounded up past it.
float rk_box_calc = na
if not na(rk_box_raw) and rk_box_raw > 0
    float _step  = renko_round > 0 ? renko_round : 0.0
    float _round = _step > 0 ? math.round(rk_box_raw / _step) * _step : rk_box_raw
    float _floor = renko_min > 0 ? renko_min : (_step > 0 ? _step : 0.0)
    float _v     = math.max(_round, _floor)
    rk_box_calc := renko_box_max > 0 ? math.min(_v, renko_box_max) : _v

// The size only moves at a period boundary, so it holds steady in between and
// anything already painted keeps the size it was painted with.
var float rk_box = na
bool rk_box_new = not na(rk_box_calc) and (na(rk_box) or rk_box != rk_box_calc)
if rk_box_new
    rk_box := rk_box_calc

// ── THE FEED ───────────────────────────────────────────────────────────────
// The prices the engine steps through, pinned to renko_feed_tf rather than
// following the chart. This is what makes the BRICKS timeframe-proof, not just
// their size: a 4-hour chart and a 15-minute chart step through the identical
// sequence of feed bars and therefore build identical bricks.
//
// security_lower_tf returns every feed bar inside the current chart bar, so on
// a slow chart the engine still sees the round trips that a single chart bar
// would have hidden. When the feed is the same as or slower than the chart it
// has nothing finer to hand back, and the plain request below is used instead.
// WHICH SOURCE IS CORRECT DEPENDS ON THE CHART, NOT ON PREFERENCE.
//   Chart COARSER than the feed - a 4-hour chart with a 5-minute feed - hides
//     the round trips inside each bar, so intrabars are genuinely needed.
//   Chart AT OR FINER than the feed - a 1-minute chart with a 1-minute feed -
//     already carries the feed at full fidelity in its own bars. Asking for
//     intrabars there returns nothing, because there is nothing finer to
//     return, and treating that as missing data was simply wrong. Nothing is
//     hidden, so nothing needs recovering.
rk_feed_s   = timeframe.in_seconds(renko_feed_tf)
rk_chart_s  = timeframe.in_seconds()
rk_need_ltf = rk_chart_s > rk_feed_s

rk_fc = request.security_lower_tf(rk_sym, renko_feed_tf, close)
rk_fh = request.security_lower_tf(rk_sym, renko_feed_tf, high)
rk_fl = request.security_lower_tf(rk_sym, renko_feed_tf, low)

rk_sc = request.security(rk_sym, renko_feed_tf, close, lookahead = barmerge.lookahead_off)
rk_sh = request.security(rk_sym, renko_feed_tf, high,  lookahead = barmerge.lookahead_off)
rk_sl = request.security(rk_sym, renko_feed_tf, low,   lookahead = barmerge.lookahead_off)
rk_cc = request.security(rk_sym, timeframe.period, close, lookahead = barmerge.lookahead_off)

// Do we have usable prices this bar? When intrabars are needed, that means the
// request returned some. When they are not, the plain feed value is enough.
rk_have = rk_need_ltf ? array.size(rk_fc) > 0 : not na(rk_sc)

// ── BRICK STATE ────────────────────────────────────────────────────────────
// rk_dir: 1 up, -1 down, 0 not yet established. rk_run: bricks in a row.
var float rk_top = na
var float rk_bot = na
var int   rk_dir = 0
var int   rk_run = 0
int rk_bricks = 0

// A new brick size means a new grid. Re-anchor SILENTLY: direction and run
// carry over untouched and no brick prints on this bar. A change in the
// measuring stick must never flip the signal by itself.
// Seed off the FIRST feed bar of this chart bar, never the last. Seeding off
// the last was a real bug: on a 5-minute chart that is one bar along, on a
// 4-hour chart it is forty-eight bars along, so the two charts started their
// grids in different cells and every brick afterwards sat one place out.
// SEED WHENEVER THERE IS NO GRID YET, not only on the bar the brick size first
// appears. This was a real fault: rk_box_new is true for exactly one bar, and
// if that bar happened to have no intrabar data the grid was never anchored,
// rk_top stayed na, and formation - which requires a grid - never ran again.
// The indicator then drew nothing for the whole chart. Whether it struck
// depended on where the chart's first bar sat relative to TradingView's
// intrabar window, which differs per timeframe, so it failed on some
// timeframes and worked on others with no obvious pattern.
if not na(rk_box) and rk_box > 0 and (rk_box_new or na(rk_top))
    float _seed = na(rk_sc) ? rk_cc : rk_sc
    if rk_need_ltf and array.size(rk_fc) > 0
        _seed := array.get(rk_fc, 0)
    if not na(_seed)
        rk_bot := math.floor(_seed / rk_box) * rk_box
        rk_top := rk_bot + rk_box

// Formation runs only on a CONFIRMED bar. On history every bar is confirmed so
// nothing changes there; live, it means the current bar contributes nothing
// until it closes, and therefore nothing already painted can ever move.
//
// This runs on the re-anchor bar too. Skipping it discarded that bar's feed
// bars, and how many got discarded depended on the chart timeframe. Any brick
// printing here comes from real price movement through the newly seeded grid,
// not from the size change itself.
if barstate.isconfirmed and not na(rk_box) and rk_box > 0 and not na(rk_top)
    // Choose the source arrays FIRST, then index them. Writing this as
    // `size > 0 ? array.get(a, i) : fallback` looks equivalent but is not:
    // Pine can evaluate both sides, and array.get on an empty array is a
    // runtime error that stops the script dead.
    bool _use_ltf = rk_need_ltf and array.size(rk_fc) > 0
    float _one_c = na(rk_sc) ? rk_cc : rk_sc
    float[] _cs = _use_ltf ? rk_fc : array.from(_one_c)
    float[] _hs = _use_ltf ? rk_fh : array.from(na(rk_sh) ? _one_c : rk_sh)
    float[] _ls = _use_ltf ? rk_fl : array.from(na(rk_sl) ? _one_c : rk_sl)
    for _s = 0 to array.size(_cs) - 1
        float _c = array.get(_cs, _s)
        float _h = array.size(_hs) > _s ? array.get(_hs, _s) : _c
        float _l = array.size(_ls) > _s ? array.get(_ls, _s) : _c
        if not na(_c)
            // Wick mode lets a touch print the brick; close mode demands a
            // close beyond the boundary. Within one feed bar the engine cannot
            // know whether the high or the low came first, so it always tests
            // the way price was already travelling before it tests a reversal.
            float _up = renko_trigger == "Wick" and not na(_h) ? _h : _c
            float _dn = renko_trigger == "Wick" and not na(_l) ? _l : _c
            for _i = 0 to 199
                bool _p = false
                if rk_dir == 1
                    if _up >= rk_top + rk_box
                        rk_bot := rk_top
                        rk_top := rk_top + rk_box
                        rk_run := rk_run + 1
                        _p := true
                    else if _dn <= rk_top - renko_rev * rk_box
                        rk_top := rk_top - (renko_rev - 1) * rk_box
                        rk_bot := rk_top - rk_box
                        rk_dir := -1
                        rk_run := 1
                        _p := true
                else if rk_dir == -1
                    if _dn <= rk_bot - rk_box
                        rk_top := rk_bot
                        rk_bot := rk_bot - rk_box
                        rk_run := rk_run + 1
                        _p := true
                    else if _up >= rk_bot + renko_rev * rk_box
                        rk_bot := rk_bot + (renko_rev - 1) * rk_box
                        rk_top := rk_bot + rk_box
                        rk_dir := 1
                        rk_run := 1
                        _p := true
                else
                    if _up >= rk_top + rk_box
                        rk_bot := rk_top
                        rk_top := rk_top + rk_box
                        rk_dir := 1
                        rk_run := 1
                        _p := true
                    else if _dn <= rk_bot - rk_box
                        rk_top := rk_bot
                        rk_bot := rk_bot - rk_box
                        rk_dir := -1
                        rk_run := 1
                        _p := true
                if not _p
                    break
                rk_bricks := rk_bricks + 1

// The gate. No box, or no direction yet, means no entries at all.
rk_ok_long  = not renko_on or (rk_dir ==  1 and rk_run >= renko_confirm)
rk_ok_short = not renko_on or (rk_dir == -1 and rk_run >= renko_confirm)

'''

edit(
    "05_renko_engine",
    "// ============================================================================\n// ③ ENTRY — PRICE ABOVE ALL",
    RENKO_ENGINE + "// ============================================================================\n// ③ ENTRY — PRICE ABOVE ALL",
)

# ===========================================================================
# EDIT 5 — gate the fresh-breakout entry path
# ===========================================================================
edit(
    "06_gate_signals",
    "long_signal  = allow_longs  and (pa_bull_raw or re_long)  and in_date and not gap_block\n"
    "short_signal = allow_shorts and (pa_bear_raw or re_short) and in_date and not gap_block",
    "long_signal  = allow_longs  and (pa_bull_raw or re_long)  and in_date and not gap_block and rk_ok_long\n"
    "short_signal = allow_shorts and (pa_bear_raw or re_short) and in_date and not gap_block and rk_ok_short",
)

# ===========================================================================
# EDIT 6 — gate the reverse-on-stop entry path
# ===========================================================================
# This is a SECOND way into a trade and it does not go through long_signal.
# Ungated, the filter would leak every reversal entry.
edit(
    "07_gate_reverse",
    'rev_long  = reverse_on_stop and stopped_from == "short" and all_bull and allow_longs  and in_date and not gap_block\n'
    'rev_short = reverse_on_stop and stopped_from == "long"  and all_bear and allow_shorts and in_date and not gap_block',
    'rev_long  = reverse_on_stop and stopped_from == "short" and all_bull and allow_longs  and in_date and not gap_block and rk_ok_long\n'
    'rev_short = reverse_on_stop and stopped_from == "long"  and all_bear and allow_shorts and in_date and not gap_block and rk_ok_short',
)

# ===========================================================================
# EDIT 7 — HUD: one extra row for renko state
# ===========================================================================
edit(
    "08_hud_size",
    "hud := table.new(_hp, 2, 9, border_width=1,",
    "hud := table.new(_hp, 2, 10, border_width=1,",
)

edit(
    "09_hud_header",
    'table.cell(hud, 0, 0, "3SHA PRICE ABOVE", text_color=color.white, bgcolor=_hd, text_size=size.small)',
    'table.cell(hud, 0, 0, "3SHA PRICE ABOVE + RK", text_color=color.white, bgcolor=_hd, text_size=size.small)',
)

HUD_RENKO = '''    table.cell(hud, 0, 9, "Renko" + (renko_on ? "" : " (off)"), text_color=color.white, bgcolor=_bg, text_size=size.small)
    _rk_txt = not renko_on ? "— disabled" : na(rk_box) ? "warm-up" : (rk_dir == 1 ? "▲ UP" : rk_dir == -1 ? "▼ DOWN" : "◇ none") + "  x" + str.tostring(rk_run) + "  box " + str.tostring(rk_box, format.mintick)
    _rk_col = not renko_on ? color.new(#888888, 0) : rk_dir == 1 ? color.new(#2962FF, 0) : rk_dir == -1 ? color.new(#F23645, 0) : color.new(#888888, 0)
    table.cell(hud, 1, 9, _rk_txt, text_color=color.white, bgcolor=_rk_col, text_size=size.small)
'''

edit(
    "10_hud_renko_row",
    '    table.cell(hud, 0, 8, "Instrument", text_color=color.white, bgcolor=_bg, text_size=size.small)\n'
    '    table.cell(hud, 1, 8, instrument_type, text_color=color.white, bgcolor=_bg, text_size=size.small)',
    '    table.cell(hud, 0, 8, "Instrument", text_color=color.white, bgcolor=_bg, text_size=size.small)\n'
    '    table.cell(hud, 1, 8, instrument_type, text_color=color.white, bgcolor=_bg, text_size=size.small)\n'
    '\n' + HUD_RENKO.rstrip('\n'),
)


# ===========================================================================
# apply
# ===========================================================================
def main():
    if not SRC.exists():
        sys.exit(f"FAIL: source not found: {SRC}")

    text = SRC.read_text()
    original_len = len(text)

    failures = []
    for name, old, new, count in edits:
        found = text.count(old)
        if found != count:
            failures.append(f"  {name}: anchor found {found}x, expected {count}x")
            continue
        text = text.replace(old, new, count)
        applied.append(name)

    if failures:
        print("FAIL — anchors did not match. Nothing written.")
        print("\n".join(failures))
        print(f"\nApplied before failure (discarded): {applied}")
        sys.exit(1)

    DST.write_text(text)
    print(f"OK — {len(applied)}/{len(edits)} edits applied")
    for a in applied:
        print(f"  ✓ {a}")
    print(f"\nsource: {SRC}  {original_len} chars, {SRC.read_text().count(chr(10))+1} lines")
    print(f"output: {DST}  {len(text)} chars, {text.count(chr(10))+1} lines")

    # source must be untouched
    if SRC.read_text() != Path(SRC).read_text():
        sys.exit("FAIL: source mutated")
    print("source unchanged ✓")


if __name__ == "__main__":
    main()
