#!/usr/bin/env python3
"""Apply the agreed PAA fixes to 3SHA_PriceAboveAll_v1.pine.

Every edit is named and asserted. A missing anchor aborts the run rather than
silently half-applying.
"""
import sys

SRC = "paa_orig.pine"
DST = "3SHA_PriceAboveAll_v1.pine"

with open(SRC, encoding="utf-8") as fh:
    lines = fh.read().split("\n")

def seg(a, b):
    """1-indexed inclusive slice."""
    return lines[a - 1:b]

def assert_at(n, needle, label):
    if needle not in lines[n - 1]:
        sys.exit("ANCHOR FAIL [%s]: line %d does not contain %r\n  got: %r"
                 % (label, n, needle, lines[n - 1]))

# ---- verify every boundary before building anything ----------------------
assert_at(1,   "//@version=6",                      "B01 version")
assert_at(26,  'strategy("3SHA Price Above All"',   "B02 strategy decl")
assert_at(33,  "SHA FUNCTION",                      "B03 f_sha header")
assert_at(51,  "=========",                         "B04 instrument header")
assert_at(116, "htf2_bull_bar = h2C >= h2O",        "B05 bull bars")
assert_at(118, "ENTRY CONDITION",                   "B06 entry cond block")
assert_at(153, "_n_below >= 2)",                    "B07 end entry cond")
assert_at(155, "SHA body extremes",                 "B08 sha extremes")
assert_at(161, "sha_bot_2 = math.min(h2O, h2C)",    "B09 end sha extremes")
assert_at(163, "=========",                         "B10 sec3 header")
assert_at(182, "pa_bear_raw",                       "B11 end sec3")
assert_at(185, "INITIAL STOP LOSS",                 "B12 sec4 header")
assert_at(196, "min_stop_raw  = min_stop_units",    "B13 end sec4")
assert_at(198, "Body extremes for the current bar", "B14 body extremes")
assert_at(263, "near_is_h1_short",                  "B15 end near flags")
assert_at(265, "f_long_stop() =>",                  "B16 long stop")
assert_at(301, "min_stop_raw > 0 ?",                "B17 end short stop")
assert_at(303, "=========",                         "B18 sizing header")
assert_at(316, "math.max(0.0, math.min",            "B19 end sizing")
assert_at(318, "=========",                         "B20 mgmt header")
assert_at(367, "use_align_exit",                    "B21 align exit input")
assert_at(385, "trail_high_ref",                    "B22 end trail refs")
assert_at(387, "=========",                         "B23 date header")
assert_at(403, "hud_pos",                           "B24 end display")
assert_at(406, "TRADE STATE MACHINE",               "B25 state vars")
assert_at(419, "rearm_low",                         "B26 end state vars")
assert_at(421, "Drop an armed re-entry",            "B27 rearm block")
assert_at(464, "all_bull",                          "B28 end align fns")
assert_at(466, "MANAGE OPEN POSITION",              "B29 mgmt block")
assert_at(626, "did_enter := true",                 "B30 end entries")
assert_at(628, "=========",                         "B31 visuals header")

# ---- E01: header comment -------------------------------------------------
E01 = '''//@version=6
// ============================================================================
// 3SHA — PRICE ABOVE ALL STRATEGY  (v1)
// ============================================================================
// PART OF: the per-entry-type rebuild of 3SHA_Strategy_v6. Each entry type gets
//   its own script, owning its stop, sizing and trade management end to end.
//   This one trades PRICE ABOVE ALL.
//
// SIGNAL:
//   Not "which way is each layer pointing" — that is Full Alignment. This asks
//   WHERE PRICE IS SITTING relative to the three SHA layers. A layer can point
//   down while price sits above it, and the reverse, so the two fire at quite
//   different moments. "Price Must Clear" chooses how many layers price has to
//   close beyond; the single-layer options are the HTF price-cross signals from
//   the plan, folded in here.
//
// ELIGIBILITY — the rule that keeps the exits honest:
//   A SHA layer cannot end a trade until price has CLOSED beyond it during that
//   trade. Whatever the entry required is eligible from the entry bar; any other
//   layer joins the moment price closes past it, and stays for the rest of the
//   trade. Without this, a layer price never cleared could close the position on
//   the very next bar — a layer the setup never asked about.
//
// EXIT ANCHORS — the stop IS the exit:
//   Alongside the fixed layer anchors, three anchors rank the ELIGIBLE layers by
//   distance from price: Closest, Middle, Furthest. The ranking is recomputed
//   every bar, so "closest" always means the line price would reach first. Both
//   the initial stop and the trail can use them. Which edge of the SHA body the
//   level sits on follows the existing convention: the far edge, i.e. the body
//   bottom for a long and the body top for a short.
//
// LAYER-FLIP EXIT (optional, off by default):
//   A layer only counts as flipped if it was pointing WITH the trade at some
//   point during it and then turned. A layer already pointing against the trade
//   at entry is dormant — it never flipped, it was just sitting there. A flip
//   INTO the trade's direction arms a layer; it never exits one.
//
// EXIT PHILOSOPHY: all exits are CLOSE-BASED (mental-stop style) by default,
//   with an optional hard stop, and every exit path closes the position.
//
// TRADING COSTS: Pine requires these to be constants in the strategy() call, so
//   they cannot be script inputs. Set them below or override in the Properties
//   tab. They ship at zero — a zero-cost backtest is fine for reconciliation
//   against TradingView, but is not a tradeable result.
// ============================================================================'''

# ---- E02: strategy() declaration -----------------------------------------
E02 = '''strategy("3SHA Price Above All", shorttitle="3SHA-PAA", overlay=true,
     initial_capital=100000, currency=currency.USD,
     default_qty_type=strategy.percent_of_equity, default_qty_value=10,
     calc_on_every_tick=false, process_orders_on_close=true, pyramiding=0,
     max_bars_back=5000, max_labels_count=500, max_lines_count=500,
     commission_type=strategy.commission.percent, commission_value=0.0,
     slippage=0)'''

# ---- E03: section 3, entry inputs (pa_layers folded in, retitled) --------
old_sec3 = "\n".join(seg(163, 182))
for frag in ["use_reentry", "reentry_needs_base", "reentry_expires", "gap_thresh"]:
    if frag not in old_sec3:
        sys.exit("ANCHOR FAIL [E03]: %r missing from section 3" % frag)

keep3 = [l for l in seg(163, 182)
         if l.startswith(("use_reentry", "reentry_needs_base",
                          "reentry_expires", "gap_thresh"))]
keep3 = [l.replace('group=grp_entry', 'group=grp_entry') for l in keep3]

E03 = '''// ============================================================================
// ③ ENTRY — PRICE ABOVE ALL
// ============================================================================
grp_entry = "③ ━━━ ENTRY: PRICE ABOVE ALL ━━━"
pa_layers = input.string("All three", "Price Must Clear", options=["All three","Both higher layers","HTF2 only","HTF1 only","Any two"], tooltip="Which SHA layers price has to close beyond. 'All three' is the strictest. The single-layer options are the HTF price-cross signals from the plan, folded in here.", group=grp_entry)
confirm_mode = input.string("Confirmed (1-bar)", "Confirmation Mode", options=["Confirmed (1-bar)","Immediate"], tooltip="Confirmed (1-bar): fires the bar AFTER price completes the condition. One bar of confirmation lag.\\nImmediate: fires on the bar price completes it. Earlier, slightly noisier.", group=grp_entry)
allow_longs  = input.bool(true, "Allow Longs", group=grp_entry)
allow_shorts = input.bool(true, "Allow Shorts", group=grp_entry)
// ── RE-ENTRY AFTER AN EXIT ─────────────────────────────────────────────────
// The entry signal fires once, on the FIRST breakout into the condition, and
// never again while it stays true. So a trade stopped out mid-trend leaves the
// rest of the move untaken. This arms the setup again after an exit: price has
// to prove it is resuming by CLOSING beyond the exit candle itself.
''' + "\n".join(keep3)

# ---- E04: section 4, stop inputs (three eligible-SHA anchors added) ------
old_sec4 = seg(184, 196)
sl_line = [l for l in old_sec4 if l.startswith("sl_mode")]
if len(sl_line) != 1:
    sys.exit("ANCHOR FAIL [E04]: expected one sl_mode line")
new_sl = sl_line[0].replace(
    '"Last SHA Bar Beyond Furthest SHA"]',
    '"Last SHA Bar Beyond Furthest SHA","Closest Eligible SHA","Middle Eligible SHA","Furthest Eligible SHA"]', 1)
if new_sl == sl_line[0]:
    sys.exit("ANCHOR FAIL [E04]: sl_mode options list not extended")
new_sl = new_sl.replace(
    'tooltip="Last Bar Beyond',
    'tooltip="Closest / Middle / Furthest Eligible SHA: rank the SHA layers that price has CLOSED beyond during this trade, by distance from price, and anchor on the chosen rung. Recomputed every bar. With two eligible layers Middle resolves to Furthest; with one, all three rungs resolve to it; with none, the anchor falls back to Swing.\\n\\nLast Bar Beyond', 1)

E04 = "\n".join([
    "// ============================================================================",
    "// ④ INITIAL STOP  (invalidation level + sizing anchor)",
    "// ============================================================================",
] + [new_sl if l.startswith("sl_mode") else l for l in old_sec4[3:]])

# ---- E05: entry calculation, relocated below sl_price_basis -------------
E05 = '''
// ── ENTRY CONDITION: WHERE PRICE SITS, NOT WHICH WAY EACH LAYER POINTS ─────
// Which edge counts follows the Anchor Uses setting, so Body ignores wicks on
// both sides — the same convention the stop anchors use. This block sits below
// the stop inputs because it reads sl_price_basis, and Pine requires an input
// to be declared before it is used.
_pa_body = sl_price_basis == "Body (open/close)"
pa_b_top = _pa_body ? math.max(bO, bC)  : bH
pa_b_bot = _pa_body ? math.min(bO, bC)  : bL
pa_1_top = _pa_body ? math.max(h1O,h1C) : h1H
pa_1_bot = _pa_body ? math.min(h1O,h1C) : h1L
pa_2_top = _pa_body ? math.max(h2O,h2C) : h2H
pa_2_bot = _pa_body ? math.min(h2O,h2C) : h2L

_ab = close > pa_b_top
_a1 = close > pa_1_top
_a2 = close > pa_2_top
_bb = close < pa_b_bot
_b1 = close < pa_1_bot
_b2 = close < pa_2_bot
_n_above = (_ab ? 1 : 0) + (_a1 ? 1 : 0) + (_a2 ? 1 : 0)
_n_below = (_bb ? 1 : 0) + (_b1 ? 1 : 0) + (_b2 ? 1 : 0)

all_bull = all_ready and (pa_layers == "All three"          ? (_ab and _a1 and _a2)
   : pa_layers == "Both higher layers" ? (_a1 and _a2)
   : pa_layers == "HTF2 only"          ? _a2
   : pa_layers == "HTF1 only"          ? _a1
   :                                     _n_above >= 2)
all_bear = all_ready and (pa_layers == "All three"          ? (_bb and _b1 and _b2)
   : pa_layers == "Both higher layers" ? (_b1 and _b2)
   : pa_layers == "HTF2 only"          ? _b2
   : pa_layers == "HTF1 only"          ? _b1
   :                                     _n_below >= 2)

// Entry fires on the transition INTO the condition, not while it persists.
pa_bull_raw = confirm_mode == "Confirmed (1-bar)" ? (all_bull[1] and not all_bull[2]) : (all_bull and not all_bull[1])
pa_bear_raw = confirm_mode == "Confirmed (1-bar)" ? (all_bear[1] and not all_bear[2]) : (all_bear and not all_bear[1])
'''

# ---- E06: trade state + eligibility + arming + distance ranking ----------
E06 = '''
// ============================================================================
// TRADE STATE  (declared here because eligibility, ranking and the trail all
// read pos_dir before the management block runs)
// ============================================================================
var string pos_dir     = "flat"
var float  entry_price = na
var float  init_stop   = na
var float  stop_level  = na
var float  risk_unit   = na    // |entry - init_stop|, the R denominator
var int    entry_bar   = na
var bool   be_moved    = false
var bool   tp1_taken   = false
var int    bad_bars    = 0     // consecutive bars the flip condition has held
var float  peak_r      = 0.0   // best R reached, for the give-back exit
var float  rearm_high  = na    // exit candle's high — long re-entry trigger
var float  rearm_low   = na    // exit candle's low  — short re-entry trigger

// ── ELIGIBILITY AND ARMING ─────────────────────────────────────────────────
// elig_*  : price has CLOSED beyond this layer at some point during the trade.
//           Only an eligible layer may end the trade.
// arm_*   : this layer has pointed WITH the trade at some point during it.
//           Only an armed layer can be said to have flipped against it.
var bool elig_b = false
var bool elig_1 = false
var bool elig_2 = false
var bool arm_b  = false
var bool arm_1  = false
var bool arm_2  = false

// Instantaneous test — also what seeds the flags on the entry bar.
inst_el_b_long  = close > pa_b_top
inst_el_1_long  = close > pa_1_top
inst_el_2_long  = close > pa_2_top
inst_el_b_short = close < pa_b_bot
inst_el_1_short = close < pa_1_bot
inst_el_2_short = close < pa_2_bot

// Running update, before anything downstream reads the flags. Once set, a flag
// holds for the rest of the trade; both sets are cleared on entry and on exit.
if pos_dir == "long"
    elig_b := elig_b or inst_el_b_long
    elig_1 := elig_1 or inst_el_1_long
    elig_2 := elig_2 or inst_el_2_long
    arm_b  := arm_b  or base_bull_bar
    arm_1  := arm_1  or htf1_bull_bar
    arm_2  := arm_2  or htf2_bull_bar
else if pos_dir == "short"
    elig_b := elig_b or inst_el_b_short
    elig_1 := elig_1 or inst_el_1_short
    elig_2 := elig_2 or inst_el_2_short
    arm_b  := arm_b  or not base_bull_bar
    arm_1  := arm_1  or not htf1_bull_bar
    arm_2  := arm_2  or not htf2_bull_bar

// ── DISTANCE RANKING OF THE ELIGIBLE LAYERS ────────────────────────────────
// Returns [closest, middle, furthest] by absolute distance from the close.
// Collapse: two eligible → middle resolves to furthest; one → all three resolve
// to it; none → all na, and the caller falls back to Swing.
// Everything is passed in; the function reads no outer-scope series.
f_rank(_e0, _l0, _e1, _l1, _e2, _l2) =>
    _lv = array.new_float()
    _ds = array.new_float()
    if _e0 and not na(_l0)
        array.push(_lv, _l0)
        array.push(_ds, math.abs(close - _l0))
    if _e1 and not na(_l1)
        array.push(_lv, _l1)
        array.push(_ds, math.abs(close - _l1))
    if _e2 and not na(_l2)
        array.push(_lv, _l2)
        array.push(_ds, math.abs(close - _l2))
    _n = array.size(_lv)
    float _near = na
    float _mid  = na
    float _far  = na
    if _n > 0
        _ix = array.sort_indices(_ds, order.ascending)
        _near := array.get(_lv, array.get(_ix, 0))
        _far  := array.get(_lv, array.get(_ix, _n - 1))
        _mid  := _n >= 3 ? array.get(_lv, array.get(_ix, 1)) : _far
    [_near, _mid, _far]

// Entry-bar ranking, from the instantaneous test — used by the initial stop.
[ik_near_L, ik_mid_L, ik_far_L] = f_rank(inst_el_b_long,  sha_bot_0, inst_el_1_long,  sha_bot_1, inst_el_2_long,  sha_bot_2)
[ik_near_S, ik_mid_S, ik_far_S] = f_rank(inst_el_b_short, sha_top_0, inst_el_1_short, sha_top_1, inst_el_2_short, sha_top_2)
// In-trade ranking, from the running flags — used by the trail.
[rk_near_L, rk_mid_L, rk_far_L] = f_rank(elig_b, sha_bot_0, elig_1, sha_bot_1, elig_2, sha_bot_2)
[rk_near_S, rk_mid_S, rk_far_S] = f_rank(elig_b, sha_top_0, elig_1, sha_top_1, elig_2, sha_top_2)
'''

# ---- E07: stop functions, three new branches, ranks passed in -----------
long_stop  = seg(265, 282)
short_stop = seg(284, 301)
if not long_stop[0].startswith("f_long_stop() =>"):
    sys.exit("ANCHOR FAIL [E07]: f_long_stop signature")
if not short_stop[0].startswith("f_short_stop() =>"):
    sys.exit("ANCHOR FAIL [E07]: f_short_stop signature")

long_stop[0] = "f_long_stop(_kn, _km, _kf) =>"
short_stop[0] = "f_short_stop(_kn, _km, _kf) =>"
NEW_L = ('      :    sl_mode == "Closest Eligible SHA"          ? (na(_kn) ? sw_low_lvl : _kn)\n'
         '      :    sl_mode == "Middle Eligible SHA"           ? (na(_km) ? sw_low_lvl : _km)\n'
         '      :    sl_mode == "Furthest Eligible SHA"         ? (na(_kf) ? sw_low_lvl : _kf)')
NEW_S = ('      :    sl_mode == "Closest Eligible SHA"          ? (na(_kn) ? sw_high_lvl : _kn)\n'
         '      :    sl_mode == "Middle Eligible SHA"           ? (na(_km) ? sw_high_lvl : _km)\n'
         '      :    sl_mode == "Furthest Eligible SHA"         ? (na(_kf) ? sw_high_lvl : _kf)')

def splice_branch(block, marker, new_rows):
    for i, l in enumerate(block):
        if marker in l:
            return block[:i + 1] + [new_rows] + block[i + 1:]
    sys.exit("ANCHOR FAIL [E07]: marker %r not found" % marker)

long_stop = splice_branch(long_stop, 'Last SHA Bar Beyond Furthest SHA"   ? (na(_lchF)', NEW_L)
short_stop = splice_branch(short_stop, 'Last SHA Bar Beyond Furthest SHA"   ? (na(_hchF)', NEW_S)
E07 = "\n".join(long_stop) + "\n\n" + "\n".join(short_stop)

# ---- E08: management inputs (trail options, align default, wording) -----
mgmt = seg(318, 385)
mtxt = "\n".join(mgmt)
if 'trail_mode = input.string' not in mtxt:
    sys.exit("ANCHOR FAIL [E08]: trail_mode missing")
mtxt = mtxt.replace(
    '"Base SHA Body","HTF1 SHA Body","HTF2 SHA Body"], tooltip="Same anchor choices',
    '"Base SHA Body","HTF1 SHA Body","HTF2 SHA Body","Closest Eligible SHA","Middle Eligible SHA","Furthest Eligible SHA"], tooltip="Same anchor choices', 1)
mtxt = mtxt.replace("Locks the trade to no-loss once the trend proves itself.",
                    "Locks the trade to break-even once the trend proves itself.", 1)
mtxt = mtxt.replace(
    'use_align_exit = input.bool(true, "Alignment-Break Exit", tooltip="The signature Full-Alignment rule: the whole thesis is that all three timeframes agree, so exit when they stop agreeing. Close-based."',
    'use_align_exit = input.bool(false, "Exit: Layer Flips Direction", tooltip="Exit when a SHA layer turns against the trade. OFF by default: this strategy enters on where PRICE sits, so a layer can be pointing the wrong way at entry and this exit would fire immediately. Two gates prevent that — a layer must be ELIGIBLE (price closed beyond it during the trade) and ARMED (it pointed with the trade at some point). A layer that never came onside can never exit the trade, and a flip INTO the trade\\x27s direction only arms a layer. Close-based."', 1)
if 'use_align_exit = input.bool(false' not in mtxt:
    sys.exit("ANCHOR FAIL [E08]: use_align_exit default not flipped")
mtxt = mtxt.replace(
    'trail_low_anchor  = trail_mode == "Swing (Prev N Bars)" ? trail_sw_low  : trail_mode == "Base SHA Body" ? sha_bot_0 : trail_mode == "HTF1 SHA Body" ? sha_bot_1 : sha_bot_2',
    'trail_low_anchor  = trail_mode == "Swing (Prev N Bars)" ? trail_sw_low  : trail_mode == "Base SHA Body" ? sha_bot_0 : trail_mode == "HTF1 SHA Body" ? sha_bot_1 : trail_mode == "HTF2 SHA Body" ? sha_bot_2 : trail_mode == "Closest Eligible SHA" ? rk_near_L : trail_mode == "Middle Eligible SHA" ? rk_mid_L : rk_far_L', 1)
mtxt = mtxt.replace(
    'trail_high_anchor = trail_mode == "Swing (Prev N Bars)" ? trail_sw_high : trail_mode == "Base SHA Body" ? sha_top_0 : trail_mode == "HTF1 SHA Body" ? sha_top_1 : sha_top_2',
    'trail_high_anchor = trail_mode == "Swing (Prev N Bars)" ? trail_sw_high : trail_mode == "Base SHA Body" ? sha_top_0 : trail_mode == "HTF1 SHA Body" ? sha_top_1 : trail_mode == "HTF2 SHA Body" ? sha_top_2 : trail_mode == "Closest Eligible SHA" ? rk_near_S : trail_mode == "Middle Eligible SHA" ? rk_mid_S : rk_far_S', 1)
if 'rk_near_L' not in mtxt or 'rk_near_S' not in mtxt:
    sys.exit("ANCHOR FAIL [E08]: trail anchors not extended")
mtxt = mtxt.replace('align_break_level = input.string("HTF1 Flips", "  Break Trigger"',
                    'align_break_level = input.string("HTF1 Flips", "  Flip Trigger"', 1)
mtxt = mtxt.replace('align_confirm_bars = input.int(1, "  Break Must Hold (bars)"',
                    'align_confirm_bars = input.int(1, "  Flip Must Hold (bars)"', 1)
E08 = mtxt

# ---- E09: flip gating replaces the old state-test functions -------------
pre = seg(421, 452)   # rearm block, gates, event flags, crosses, shab edges
pretxt = "\n".join(pre)
if "cross_dn = ta.crossunder" not in pretxt:
    sys.exit("ANCHOR FAIL [E09]: cross calc missing")
pretxt = pretxt.replace(
    'stopped_from = ""   // "long"/"short" when a STOP (not an align break) closed a trade this bar',
    'stopped_from = ""   // "long"/"short" when a STOP (not another exit) closed a trade this bar', 1)

E09 = pretxt + '''

// ── LAYER-FLIP CONDITION (eligible AND armed AND now against the trade) ────
// A layer that price never cleared cannot exit the trade. Neither can a layer
// that never pointed with it — that layer never flipped, it was always offside.
flip_b_long = elig_b and arm_b and not base_bull_bar
flip_1_long = elig_1 and arm_1 and not htf1_bull_bar
flip_2_long = elig_2 and arm_2 and not htf2_bull_bar
flip_b_short = elig_b and arm_b and base_bull_bar
flip_1_short = elig_1 and arm_1 and htf1_bull_bar
flip_2_short = elig_2 and arm_2 and htf2_bull_bar
n_elig      = (elig_b ? 1 : 0) + (elig_1 ? 1 : 0) + (elig_2 ? 1 : 0)
n_flip_long = (flip_b_long ? 1 : 0) + (flip_1_long ? 1 : 0) + (flip_2_long ? 1 : 0)
n_flip_shrt = (flip_b_short ? 1 : 0) + (flip_1_short ? 1 : 0) + (flip_2_short ? 1 : 0)

align_broken_long = align_break_level == "Base Flips"      ? flip_b_long
   : align_break_level == "HTF1 Flips"      ? flip_1_long
   : align_break_level == "HTF2 Flips"      ? flip_2_long
   : align_break_level == "Any Layer Flips" ? (n_flip_long > 0)
   :                                          (n_elig > 0 and n_flip_long == n_elig)
align_broken_short = align_break_level == "Base Flips"      ? flip_b_short
   : align_break_level == "HTF1 Flips"      ? flip_1_short
   : align_break_level == "HTF2 Flips"      ? flip_2_short
   : align_break_level == "Any Layer Flips" ? (n_flip_shrt > 0)
   :                                          (n_elig > 0 and n_flip_shrt == n_elig)
'''

# ---- E10: management + entry blocks -------------------------------------
mgr = "\n".join(seg(466, 626))
mgr = mgr.replace("bad_bars := f_align_broken_long() ? bad_bars + 1 : 0",
                  "bad_bars := align_broken_long ? bad_bars + 1 : 0", 1)
mgr = mgr.replace("bad_bars := f_align_broken_short() ? bad_bars + 1 : 0",
                  "bad_bars := align_broken_short ? bad_bars + 1 : 0", 1)
if "f_align_broken" in mgr:
    sys.exit("ANCHOR FAIL [E10]: stale f_align_broken reference")
mgr = mgr.replace('_align_out ? "Align Break"', '_align_out ? "Layer Flip"')
mgr = mgr.replace('strategy.close("PA", qty_percent=tp1_pct', 'strategy.close("PAA", qty_percent=tp1_pct')
mgr = mgr.replace('strategy.exit("FA-stop", from_entry="PA", stop=stop_level)',
                  'strategy.exit("PAA-stop", from_entry="PAA", stop=stop_level)')
mgr = mgr.replace('strategy.entry("PA", strategy.long', 'strategy.entry("PAA", strategy.long')
mgr = mgr.replace('strategy.entry("PA", strategy.short', 'strategy.entry("PAA", strategy.short')
if '"PA"' in mgr:
    sys.exit("ANCHOR FAIL [E10]: stale PA entry id remains")
mgr = mgr.replace("    _stop = f_long_stop()\n",  "    _stop = f_long_stop(ik_near_L, ik_mid_L, ik_far_L)\n", 1)
mgr = mgr.replace("    _stop = f_short_stop()\n", "    _stop = f_short_stop(ik_near_S, ik_mid_S, ik_far_S)\n", 1)
if "f_long_stop(ik_near_L" not in mgr or "f_short_stop(ik_near_S" not in mgr:
    sys.exit("ANCHOR FAIL [E10]: stop calls not rewired")

# reconcile block uses 4-space indent — clear there too
mgr = mgr.replace("""    be_moved := false
    tp1_taken := false""", """    be_moved := false
    tp1_taken := false
    elig_b := false
    elig_1 := false
    elig_2 := false
    arm_b  := false
    arm_1  := false
    arm_2  := false""", 1)
if mgr.count("    elig_b := false") < 1:
    sys.exit("ANCHOR FAIL [E10]: reconcile clear not applied")

# clear flags on every exit, seed them on every entry
mgr = mgr.replace("""        be_moved := false
        tp1_taken := false""", """        be_moved := false
        tp1_taken := false
        elig_b := false
        elig_1 := false
        elig_2 := false
        arm_b  := false
        arm_1  := false
        arm_2  := false""")
mgr = mgr.replace("""        pos_dir     := "long"
""", """        elig_b      := inst_el_b_long
        elig_1      := inst_el_1_long
        elig_2      := inst_el_2_long
        arm_b       := base_bull_bar
        arm_1       := htf1_bull_bar
        arm_2       := htf2_bull_bar
        pos_dir     := "long"
""", 1)
mgr = mgr.replace("""        pos_dir     := "short"
""", """        elig_b      := inst_el_b_short
        elig_1      := inst_el_1_short
        elig_2      := inst_el_2_short
        arm_b       := not base_bull_bar
        arm_1       := not htf1_bull_bar
        arm_2       := not htf2_bull_bar
        pos_dir     := "short"
""", 1)
if mgr.count("elig_b      := inst_el_b_long") != 1 or mgr.count("elig_b      := inst_el_b_short") != 1:
    sys.exit("ANCHOR FAIL [E10]: entry seeding not applied exactly once")
E10 = mgr

# ---- E10b: sizing tooltip, FA language removed --------------------------
SIZ = "\n".join(seg(303, 316))
SIZ = SIZ.replace("Full Alignment is the highest-conviction signal, so this defaults to the top of the normal band. ",
                  "Price Above All clears a structural level rather than waiting for three layers to agree, so this defaults to the middle of the normal band. ", 1)
if "Full Alignment" in SIZ:
    sys.exit("ANCHOR FAIL [E10b]: sizing tooltip not swept")

# ---- E11: visuals, HUD, alerts ------------------------------------------
vis = "\n".join(seg(628, len(lines)))
vis = vis.replace('plot(all_bull ? 1 : all_bear ? -1 : 0, "Alignment", display=display.data_window)',
                  'plot(all_bull ? 1 : all_bear ? -1 : 0, "Price Position", display=display.data_window)', 1)
vis = vis.replace('hud := table.new(_hp, 2, 8,', 'hud := table.new(_hp, 2, 9,', 1)
vis = vis.replace('_align_txt = all_bull ? "▲ ALL BULL" : all_bear ? "▼ ALL BEAR" : "◇ MIXED"',
                  '_align_txt = all_bull ? "▲ ABOVE ALL" : all_bear ? "▼ BELOW ALL" : "◇ MIXED"', 1)
vis = vis.replace('table.cell(hud, 0, 1, "Alignment"', 'table.cell(hud, 0, 1, "Price vs SHA"', 1)
vis = vis.replace('''    table.cell(hud, 0, 7, "Instrument"''',
'''    table.cell(hud, 0, 7, "Eligible B/1/2", text_color=color.white, bgcolor=_bg, text_size=size.small)
    table.cell(hud, 1, 7, (elig_b?"●":"○")+" "+(elig_1?"●":"○")+" "+(elig_2?"●":"○"), text_color=color.white, bgcolor=_bg, text_size=size.small)

    table.cell(hud, 0, 8, "Instrument"''', 1)
vis = vis.replace('table.cell(hud, 1, 7, instrument_type', 'table.cell(hud, 1, 8, instrument_type', 1)
if 'table.cell(hud, 0, 8, "Instrument"' not in vis:
    sys.exit("ANCHOR FAIL [E11]: HUD row not added")
vis = vis.replace("// Entry markers — filled arrows (▲▼), matching v6's Full Alignment glyphs",
                  '// Entry markers — filled arrows (▲▼), carried over from v6', 1)
vis = vis.replace('alertcondition(did_enter and pos_dir == "long",  "FA Long Entry",  "3SHA Full Alignment — LONG entry")',
                  'alertcondition(did_enter and pos_dir == "long",  "PAA Long Entry",  "3SHA Price Above All — LONG entry")', 1)
vis = vis.replace('alertcondition(did_enter and pos_dir == "short", "FA Short Entry", "3SHA Full Alignment — SHORT entry")',
                  'alertcondition(did_enter and pos_dir == "short", "PAA Short Entry", "3SHA Price Above All — SHORT entry")', 1)
vis = vis.replace('alertcondition(did_exit, "FA Exit", "3SHA Full Alignment — position closed")',
                  'alertcondition(did_exit, "PAA Exit", "3SHA Price Above All — position closed")', 1)
if "Full Alignment" in vis or '"FA ' in vis:
    sys.exit("ANCHOR FAIL [E11]: stale FA text in visuals")
vis = vis.replace('exit_reason == "STOP" ? color.new(#8B0000, 0) : color.new(#000000, 0)',
                  'exit_reason == "STOP" ? color.new(#8B0000, 0) : color.new(#000000, 0)', 1)
E11 = vis

# ---- assemble ------------------------------------------------------------
out = "\n".join([
    E01, "",
    E02, "",
    "\n".join(seg(32, 49)), "",
    "\n".join(seg(51, 116)), "",
    "\n".join(seg(155, 161)), "",
    E03, "",
    E04,
    E05,
    "\n".join(seg(198, 263)),
    E06,
    E07, "",
    SIZ, "",
    E08, "",
    "\n".join(seg(387, 403)), "",
    E09,
    E10, "",
    E11,
])

with open(DST, "w", encoding="utf-8") as fh:
    fh.write(out)

print("OK  wrote %s  (%d lines)" % (DST, out.count("\n") + 1))
