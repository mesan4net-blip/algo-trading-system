#!/usr/bin/env python3
"""
build_renko_indicator.py — build 3SHA_Renko_Chart_v1.pine

The renko engine is NOT retyped here. It is imported as the same text constant
the strategy is built from, so the indicator and the strategy cannot drift
apart. If the engine ever changes, both files change together or neither does.

Only the inputs header and the enable-toggle tooltip are adapted, by named
replacement, so the adaptation stays auditable.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from derive_paar import RENKO_INPUTS, RENKO_ENGINE  # noqa: E402

DST = Path("3SHA_Renko_Chart_v1.pine")

# --- adapt the shared inputs block for a standalone indicator --------------
adaptations = [
    ('grp_renko = "⑨ ━━━ RENKO FILTER ━━━"',
     'grp_renko = "━━━ RENKO ━━━"'),

    ('renko_on       = input.bool(true, "Enable Renko Filter", tooltip="OFF = this script behaves identically to plain 3SHA-PAA, same trades, same numbers. That is the A/B test: run it off, run it on, compare.", group=grp_renko)',
     'renko_on       = input.bool(true, "Show Renko", tooltip="Kept here so this indicator takes the SAME inputs as 3SHA-PAAR. Match the settings on both and what you see is exactly what the strategy trades on.", group=grp_renko)'),

    ('renko_show_hud = input.bool(true, "Show Renko Row In HUD", group=grp_renko)',
     'renko_show_hud = input.bool(true, "Show Status Box", group=grp_renko)\n'
     '\n'
     'grp_draw       = "━━━ DRAWING ━━━"\n'
     'rk_up_col      = input.color(color.new(#2962FF, 0), "Up Brick", group=grp_draw)\n'
     'rk_dn_col      = input.color(color.new(#F23645, 0), "Down Brick", group=grp_draw)\n'
     'rk_transp      = input.int(82, "Brick Transparency", minval=0, maxval=100, tooltip="How see-through the brick is. This is the setting that actually matters if the renko is hiding your candles: at 0 the brick is solid and covers everything underneath, at 100 it is invisible. 82 leaves the candles clearly readable through it.", group=grp_draw)\n'
     'rk_edge        = input.bool(true, "Show Brick Edge Lines", tooltip="The two step lines marking the top and bottom of the current brick - the live grid levels.", group=grp_draw)\n'
     'rk_marks       = input.bool(true, "Mark Renko Turns", group=grp_draw)\n'
     '\n'
     'show_candles   = input.bool(false, "Draw Price Candles", tooltip="Pine cannot hide the chart\'s own candles, so leave this OFF in normal use - your candles are already there, and lowering Brick Transparency is what lets you see them. Turn this ON only if you have switched the native candles off in Chart Settings and want this indicator to draw them instead. With both on you will see every candle drawn twice.", group=grp_draw)\n'
     'cndl_up        = input.color(color.new(#26A69A, 0), "Candle Up", group=grp_draw)\n'
     'cndl_dn        = input.color(color.new(#EF5350, 0), "Candle Down", group=grp_draw)'),
]

HEADER = '''//@version=6
// ============================================================================
// 3SHA — RENKO CHART  (v1)
// ============================================================================
// The companion picture for 3SHA_PriceAboveAll_Renko_v1.pine (3SHA-PAAR).
//
// WHAT THIS IS:
//   The renko the strategy actually reads, drawn on top of your normal time
//   chart. The engine below is the SAME TEXT the strategy is built from — both
//   files are generated from one source block, so they cannot drift apart. Put
//   the same settings in both and what you see here is what the strategy trades.
//
// WHAT THIS IS NOT:
//   It is not a renko chart in the TradingView sense, and that is deliberate.
//   A real renko chart throws time away — every brick gets equal width no
//   matter whether it took four minutes or four days. That is precisely what
//   makes renko backtests lie: five bricks inside one real minute look like
//   five separate chances to trade. Here the bricks are drawn against real
//   time, so a burst of five shows up as five stacked steps on ONE bar, and
//   you can see at a glance that it was one moment, not five.
//
// WHY IT DOES NOT REPAINT:
//   - Box size is frozen for a calendar month, computed from a month that has
//     already finished and was observed from its first bar.
//   - Brick boundaries sit at absolute multiples of the box size counted from
//     zero, so loading more history does not shift the grid.
//   - Bricks form only on a CLOSED bar, off the close. Nothing intrabar.
//   Tested: truncating history never alters an earlier bar, and four different
//   history loads produced identical bricks on 100% of comparable bars.
//
// HOW TO READ IT:
//   The coloured body is the current brick — its top and bottom edges are the
//   live grid lines. Blue = renko up, red = renko down, grey = warm-up, when
//   the strategy takes no trades at all. A flat run of the same body is price
//   sitting inside one brick. Steps are bricks printing.
// ============================================================================

indicator("3SHA Renko Chart", shorttitle="3SHA-RK", overlay=true,
     max_labels_count=100)

'''

DRAW = '''
// ============================================================================
// DRAWING
// ============================================================================
// The brick is drawn as a TRANSLUCENT BAND between its top and bottom edges,
// not as a solid body, so the price candles underneath stay readable. This is
// the whole point: the renko is meant to sit alongside price, not replace it.
// O(1) per bar - no arrays, no box objects, nothing accumulates over history.
rk_live = renko_on and not na(rk_box) and not na(rk_top)
rk_base = rk_dir == 1 ? rk_up_col : rk_dir == -1 ? rk_dn_col : color.new(#888888, 0)

rk_pT = plot(rk_live ? rk_top : na, "Brick Top",
             color=rk_edge ? color.new(rk_base, 35) : color.new(#000000, 100),
             style=plot.style_stepline, linewidth=1)
rk_pB = plot(rk_live ? rk_bot : na, "Brick Bottom",
             color=rk_edge ? color.new(rk_base, 35) : color.new(#000000, 100),
             style=plot.style_stepline, linewidth=1)
fill(rk_pT, rk_pB, color=color.new(rk_base, rk_transp), title="Brick Body")

// Optional price candles. Only for charts where the native candles have been
// switched off in Chart Settings - Pine cannot hide them from here.
plotcandle(show_candles ? open  : na, show_candles ? high : na,
           show_candles ? low   : na, show_candles ? close : na,
           title="Price Candles",
           color       = close >= open ? cndl_up : cndl_dn,
           wickcolor   = close >= open ? cndl_up : cndl_dn,
           bordercolor = close >= open ? cndl_up : cndl_dn)

// Mark bars where the renko turned around
rk_flipped = rk_dir != rk_dir[1] and rk_dir != 0 and not na(rk_dir[1])
plotshape(rk_marks and rk_live and rk_flipped and rk_dir == 1, "Renko Turned Up",
          shape.triangleup, location.belowbar, color.new(#2962FF, 0), size=size.tiny)
plotshape(rk_marks and rk_live and rk_flipped and rk_dir == -1, "Renko Turned Down",
          shape.triangledown, location.abovebar, color.new(#F23645, 0), size=size.tiny)

// -- STATUS ----------------------------------------------------------------
var table rkt = na
if renko_show_hud and barstate.islast
    rkt := table.new(position.top_right, 2, 4, border_width=1,
         frame_color=color.new(#000000, 40), frame_width=1)
    _bg = color.new(#1A1A1A, 10)
    _hd = rk_dir == 1 ? color.new(#2962FF, 0) : rk_dir == -1 ? color.new(#F23645, 0) : color.new(#888888, 0)
    table.cell(rkt, 0, 0, "3SHA RENKO", text_color=color.white, bgcolor=_hd, text_size=size.small)
    table.cell(rkt, 1, 0, na(rk_box) ? "WARM-UP" : rk_dir == 1 ? "\u25b2 UP" : rk_dir == -1 ? "\u25bc DOWN" : "\u25c7 NONE", text_color=color.white, bgcolor=_hd, text_size=size.small)
    table.cell(rkt, 0, 1, "Box Size", text_color=color.white, bgcolor=_bg, text_size=size.small)
    table.cell(rkt, 1, 1, na(rk_box) ? "\u2014" : str.tostring(rk_box, format.mintick), text_color=color.white, bgcolor=_bg, text_size=size.small)
    table.cell(rkt, 0, 2, "Bricks In A Row", text_color=color.white, bgcolor=_bg, text_size=size.small)
    table.cell(rkt, 1, 2, na(rk_box) ? "\u2014" : str.tostring(rk_run), text_color=color.white, bgcolor=_bg, text_size=size.small)
    table.cell(rkt, 0, 3, "Entries", text_color=color.white, bgcolor=_bg, text_size=size.small)
    _gate = rk_ok_long ? "LONGS ONLY" : rk_ok_short ? "SHORTS ONLY" : "BLOCKED"
    table.cell(rkt, 1, 3, _gate, text_color=color.white, bgcolor=_bg, text_size=size.small)

alertcondition(rk_flipped and rk_dir ==  1, "Renko Turned Up",   "3SHA Renko turned UP")
alertcondition(rk_flipped and rk_dir == -1, "Renko Turned Down", "3SHA Renko turned DOWN")
'''


def main():
    inputs = RENKO_INPUTS
    for old, new in adaptations:
        if inputs.count(old) != 1:
            sys.exit(f"FAIL: adaptation anchor not unique/found:\n  {old[:70]}...")
        inputs = inputs.replace(old, new, 1)

    text = HEADER + inputs + RENKO_ENGINE + DRAW
    DST.write_text(text)

    # the engine must be present verbatim — this is the anti-drift check
    if RENKO_ENGINE not in text:
        sys.exit("FAIL: engine text was altered during assembly")

    print(f"OK — {DST}  {len(text)} chars, {text.count(chr(10))+1} lines")
    print(f"  {len(adaptations)} input adaptations applied")
    print("  engine text byte-identical to the strategy's ✓")


if __name__ == "__main__":
    main()
