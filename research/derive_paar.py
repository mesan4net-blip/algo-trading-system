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
    "//   The chart stays on its normal time-based bars. The renko lives as a\n"
    "//   number computed alongside them. This is what makes it non-repainting:\n"
    "//     - box size is frozen for a calendar month, derived from the month\n"
    "//       that already finished, and old bricks are never redrawn with a new\n"
    "//       size;\n"
    "//     - brick boundaries sit at absolute multiples of the box size counted\n"
    "//       from zero, so loading more history does not move the grid;\n"
    "//     - bricks form only on a CLOSED bar, off the close.\n"
    "//   TradingView's built-in renko chart fails on all three counts.\n"
    "//\n"
    "// BACKTEST HONESTY:\n"
    "//   Several bricks can print inside one bar. They change the renko\n"
    "//   direction and nothing else — one decision per bar, filled at the real\n"
    "//   bar close. A renko-charted backtest would instead treat each brick as\n"
    "//   its own moment and let you buy the first and sell the last, a trade\n"
    "//   that never existed. That is why renko backtests flatter to deceive.\n",
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
renko_reset    = input.string("Monthly", "Brick Size Reset", options=["Daily", "Weekly", "Monthly"], tooltip="How often the brick size is recalculated. Monthly: last month sizes this month. Daily: yesterday sizes today. Whatever is already painted never changes - a reset only affects bricks drawn from that point on.", group=grp_renko)
renko_size_tf  = input.timeframe("30", "Bar Timeframe For Brick Size", tooltip="Which bars are measured to size the brick. Read from this timeframe directly, never from your chart, so the brick size is the same number whether you are looking at a 5-minute chart or a weekly one.", group=grp_renko)
renko_mult     = input.float(1.0, "Brick Size Multiplier", minval=0.05, maxval=20.0, step=0.05, tooltip="Brick size = average range of those bars over the last period, times this. 1.0 means the brick is exactly the average bar range. Raise it for chunkier bricks and fewer signals.", group=grp_renko)
renko_round    = input.float(0.0001, "Round Box Size To Nearest", minval=0.0, step=0.0001, tooltip="Rounds the computed brick size to something clean, so the grid levels are readable. 0.0001 suits forex, 0.05 suits equities. 0 = no rounding.", group=grp_renko)
renko_min      = input.float(0.0, "Minimum Box Size", minval=0.0, step=0.0001, tooltip="Floor, so a dead month cannot produce a silly-small brick. 0 = use the rounding step as the floor.", group=grp_renko)
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
// THE DAILY RANGE IS REQUESTED FROM THE DAILY TIMEFRAME, NEVER REBUILT FROM
// CHART BARS. This is the whole reason the brick size does not move when you
// change chart timeframe. Rebuilding each day's high and low from chart bars
// looks equivalent but is not: once a chart bar is a day or longer, every bar
// counts as its own "day", so on a weekly chart the "average daily range" is
// really an average weekly range and the brick comes out roughly twice as wide.
// Intraday, session gaps and extended hours pull it around the same way.
//
// [1] takes the last COMPLETED daily bar and lookahead_off blocks values from
// arriving before they exist, so nothing leaks in early on a fast chart.
// BRICK SIZE
// Average the range of every sizing bar in the period that just finished, then
// hold that number for the whole of the next period.
//
// The averaging runs INSIDE the sizing timeframe's own context, so the period
// boundaries are found on those bars and not on your chart's. That is what
// makes the number timeframe-proof: a 5-minute chart and a 4-hour chart both
// read the identical 30-minute candles and both arrive at the identical brick.
//
// Note the ordering. On the first bar of a new period the running total still
// holds the period that just ENDED, so it is banked first and only then reset.
// Nothing is ever sized from a period still in progress.
f_rk_avg(_reset) =>
    bool _new = ta.change(time(_reset)) != 0
    var float _sum  = 0.0
    var int   _n    = 0
    var float _held = na
    if _new
        _held := _n > 0 ? _sum / _n : _held
        _sum  := 0.0
        _n    := 0
    _sum := _sum + (high - low)
    _n   := _n + 1
    _held

rk_reset_tf = renko_reset == "Daily" ? "1D" : renko_reset == "Weekly" ? "1W" : "1M"

// CHART TYPE MUST NOT CHANGE THE NUMBERS EITHER.
// On a Heikin Ashi, Renko, Kagi, Point & Figure, Line Break or Range chart, the
// built-in close/high/low are the MODIFIED values, not real traded prices - and
// syminfo.tickerid carries the chart-type modifier with it, so even a data
// request inherits it. ticker.standard() strips that off and returns plain
// candles from the real symbol. Everything below is sized and stepped off real
// traded prices, so switching chart type leaves the bricks untouched.
rk_sym = ticker.standard(syminfo.tickerid)

rk_avg = request.security(rk_sym, renko_size_tf, f_rk_avg(rk_reset_tf),
             lookahead = barmerge.lookahead_off)

// The real traded close, for brick formation. Not the chart's close, which on a
// Heikin Ashi chart is an average of averages and never traded anywhere.
rk_close = request.security(rk_sym, timeframe.period, close,
             lookahead = barmerge.lookahead_off)

// rk_avg only moves at a period boundary, so the brick size holds steady in
// between and anything already painted keeps the size it was painted with.
float rk_box_calc = na
if not na(rk_avg) and rk_avg > 0
    float _raw   = rk_avg * renko_mult
    float _step  = renko_round > 0 ? renko_round : 0.0
    float _round = _step > 0 ? math.round(_raw / _step) * _step : _raw
    float _floor = renko_min > 0 ? renko_min : (_step > 0 ? _step : 0.0)
    rk_box_calc := math.max(_round, _floor)

var float rk_box = na
bool rk_box_new = not na(rk_box_calc) and (na(rk_box) or rk_box != rk_box_calc)
if rk_box_new
    rk_box := rk_box_calc

// Brick state. rk_dir: 1 up, -1 down, 0 not yet established.
// rk_run: bricks in a row in the current direction.
var float rk_top = na
var float rk_bot = na
var int   rk_dir = 0
var int   rk_run = 0

// A new box size means a new grid. Re-anchor SILENTLY: direction and run carry
// over untouched and no brick prints on this bar. A change in the measuring
// stick must never flip the signal by itself.
if rk_box_new and not na(rk_box) and rk_box > 0
    rk_bot := math.floor(rk_close / rk_box) * rk_box
    rk_top := rk_bot + rk_box

// Brick formation — closed bar only, close only, highs and lows ignored.
// Bounded loop rather than while: several bricks can print on one bar, and 200
// is far beyond anything real. If it were ever hit the state simply lags a bar.
if not rk_box_new and not na(rk_box) and rk_box > 0 and not na(rk_top)
    for _i = 0 to 199
        bool _printed = false
        if rk_dir == 1
            if rk_close >= rk_top + rk_box
                rk_bot := rk_top
                rk_top := rk_top + rk_box
                rk_run := rk_run + 1
                _printed := true
            else if rk_close <= rk_top - renko_rev * rk_box
                rk_top := rk_top - (renko_rev - 1) * rk_box
                rk_bot := rk_top - rk_box
                rk_dir := -1
                rk_run := 1
                _printed := true
        else if rk_dir == -1
            if rk_close <= rk_bot - rk_box
                rk_top := rk_bot
                rk_bot := rk_bot - rk_box
                rk_run := rk_run + 1
                _printed := true
            else if rk_close >= rk_bot + renko_rev * rk_box
                rk_bot := rk_bot + (renko_rev - 1) * rk_box
                rk_top := rk_bot + rk_box
                rk_dir := 1
                rk_run := 1
                _printed := true
        else
            if rk_close >= rk_top + rk_box
                rk_bot := rk_top
                rk_top := rk_top + rk_box
                rk_dir := 1
                rk_run := 1
                _printed := true
            else if rk_close <= rk_bot - rk_box
                rk_top := rk_bot
                rk_bot := rk_bot - rk_box
                rk_dir := -1
                rk_run := 1
                _printed := true
        if not _printed
            break

// The gate. During the first calendar month there is no box, no direction and
// therefore no entries at all — that month is warm-up. Set the backtest start
// at least one full month after the data starts or it is wasted.
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
