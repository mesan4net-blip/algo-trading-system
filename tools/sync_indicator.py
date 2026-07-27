#!/usr/bin/env python3
"""Sync 3SHA_PriceAboveAll_Alerts_v1.pine to the strategy's logic.

Brings the alerts indicator in line with 3SHA_PriceAboveAll_v1.pine: fixes the
sl_price_basis forward reference, completes the entry option set, adds the
eligibility/arming gates and the distance anchors, and turns the layer-flip exit
off by default. Every edit is named and asserted.
"""
import sys

SRC = "ind_in.pine"
DST = "3SHA_PriceAboveAll_Alerts_v1.pine"

lines = open(SRC, encoding="utf-8").read().split("\n")


def seg(a, b):
    return lines[a - 1:b]


def at(n, needle, label):
    if needle not in lines[n - 1]:
        sys.exit("ANCHOR FAIL [%s]: line %d lacks %r\n  got: %r" % (label, n, needle, lines[n - 1]))


at(92,  "ENTRY CONDITION",          "B1")
at(125, "sha_bot_0 = math.min",     "B2")
at(133, "\u2463 ENTRY",             "B3")
at(156, "INITIAL STOP",             "B4")
at(180, "LAST-BAR-BEYOND ANCHORS",  "B5")
at(218, "f_long_stop() =>",         "B6")
at(237, "f_short_stop() =>",        "B7")
at(257, "TRADE MANAGEMENT",         "B8")
at(302, "shab_bot",                 "B9")
at(305, "f_align_broken_long",      "B10")
at(320, "TRADE STATE",              "B11")
at(333, "ev_entry_long",            "B12")
at(339, "manage the open",          "B13")
at(438, "ALERTS",                   "B14")

# ---- E1: entry inputs, pa_layers folded in with the full option set --------
old_entry = "\n".join(seg(132, 153))
for f in ["confirm_mode", "allow_longs", "use_reentry", "gap_thresh", "pa_bull_raw"]:
    if f not in old_entry:
        sys.exit("ANCHOR FAIL [E1]: %s missing" % f)
keep = [l for l in seg(132, 153)
        if l.startswith(("allow_longs", "allow_shorts", "use_reentry",
                         "reentry_needs_base", "reentry_expires", "gap_thresh"))]

E1 = '''// ============================================================================
// \u2463 ENTRY \u2014 PRICE ABOVE ALL
// ============================================================================
grp_entry = "\u2463 \u2501\u2501\u2501 ENTRY: PRICE ABOVE ALL \u2501\u2501\u2501"
pa_layers = input.string("All three", "Price Must Clear", options=["All three","HTF1 + HTF2","Base + HTF1","Base + HTF2","HTF2 only","HTF1 only","Base only","Any two"], tooltip="Which SHA layers price has to close beyond. 'All three' is the strictest. Base only has no higher-timeframe context at all \u2014 it is a control for measuring what HTF1 and HTF2 contribute, not a signal to trade.", group=grp_entry)
confirm_mode = input.string("Confirmed (1-bar)", "Confirmation Mode", options=["Confirmed (1-bar)","Immediate"], tooltip="Confirmed (1-bar): fires the bar AFTER price completes the condition.\\nImmediate: fires on the bar price completes it.", group=grp_entry)
''' + "\n".join(keep)

# ---- E2: stop inputs, three eligible anchors added -------------------------
sl = [l for l in seg(155, 178) if l.startswith("sl_mode")]
if len(sl) != 1:
    sys.exit("ANCHOR FAIL [E2]: sl_mode not unique")
new_sl = sl[0].replace('"Last SHA Bar Beyond Furthest SHA"]',
                       '"Last SHA Bar Beyond Furthest SHA","Closest Eligible SHA","Middle Eligible SHA","Furthest Eligible SHA"]', 1)
if new_sl == sl[0]:
    sys.exit("ANCHOR FAIL [E2]: sl_mode options not extended")
E2 = "\n".join([new_sl if l.startswith("sl_mode") else l for l in seg(155, 178)])

# ---- E3: entry calculation, relocated below sl_price_basis -----------------
E3 = '''
// \u2500\u2500 ENTRY CONDITION: WHERE PRICE SITS, NOT WHICH WAY EACH LAYER POINTS \u2500\u2500\u2500\u2500\u2500
// Sits below the stop inputs because it reads sl_price_basis, and Pine requires
// an input to be declared before it is used.
_pa_body = sl_price_basis == "Body (open/close)"
pa_b_top = _pa_body ? math.max(bO, bC)  : bH
pa_b_bot = _pa_body ? math.min(bO, bC)  : bL
pa_1_top = _pa_body ? math.max(h1O,h1C) : h1H
pa_1_bot = _pa_body ? math.min(h1O,h1C) : h1L
pa_2_top = _pa_body ? math.max(h2O,h2C) : h2H
pa_2_bot = _pa_body ? math.min(h2O,h2C) : h2L

_ab = rawC > pa_b_top
_a1 = rawC > pa_1_top
_a2 = rawC > pa_2_top
_bb = rawC < pa_b_bot
_b1 = rawC < pa_1_bot
_b2 = rawC < pa_2_bot
_n_above = (_ab ? 1 : 0) + (_a1 ? 1 : 0) + (_a2 ? 1 : 0)
_n_below = (_bb ? 1 : 0) + (_b1 ? 1 : 0) + (_b2 ? 1 : 0)

all_bull = all_ready and (pa_layers == "All three"          ? (_ab and _a1 and _a2)
   : pa_layers == "HTF1 + HTF2"        ? (_a1 and _a2)
   : pa_layers == "Base + HTF1"        ? (_ab and _a1)
   : pa_layers == "Base + HTF2"        ? (_ab and _a2)
   : pa_layers == "HTF2 only"          ? _a2
   : pa_layers == "HTF1 only"          ? _a1
   : pa_layers == "Base only"          ? _ab
   :                                     _n_above >= 2)
all_bear = all_ready and (pa_layers == "All three"          ? (_bb and _b1 and _b2)
   : pa_layers == "HTF1 + HTF2"        ? (_b1 and _b2)
   : pa_layers == "Base + HTF1"        ? (_bb and _b1)
   : pa_layers == "Base + HTF2"        ? (_bb and _b2)
   : pa_layers == "HTF2 only"          ? _b2
   : pa_layers == "HTF1 only"          ? _b1
   : pa_layers == "Base only"          ? _bb
   :                                     _n_below >= 2)

pa_bull_raw = confirm_mode == "Confirmed (1-bar)" ? (all_bull[1] and not all_bull[2]) : (all_bull and not all_bull[1])
pa_bear_raw = confirm_mode == "Confirmed (1-bar)" ? (all_bear[1] and not all_bear[2]) : (all_bear and not all_bear[1])

is_new_day = ta.change(time("1D")) != 0
gap_block  = gap_thresh > 0 and is_new_day and gap_pct > gap_thresh
'''

# ---- E4: trade state, eligibility, arming, distance ranking ---------------
E4 = '''
// ============================================================================
// TRADE STATE  (declared here \u2014 eligibility, ranking and the trail all read
// pos_dir before the management block runs)
// ============================================================================
var string pos_dir     = "flat"
var float  entry_price = na
var float  stop_level  = na
var float  risk_unit   = na
var bool   be_moved    = false
var int    bad_bars    = 0
var float  peak_r      = 0.0
var int    entry_bar   = na
var float  rearm_high  = na
var float  rearm_low   = na

// \u2500\u2500 ELIGIBILITY AND ARMING (mirrors the strategy) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
// elig_* : price has CLOSED beyond this layer during the trade. Only an
//          eligible layer may end it.
// arm_*  : this layer has pointed WITH the trade during it. Only an armed layer
//          can be said to have flipped against it.
var bool elig_b = false
var bool elig_1 = false
var bool elig_2 = false
var bool arm_b  = false
var bool arm_1  = false
var bool arm_2  = false

inst_el_b_long  = rawC > pa_b_top
inst_el_1_long  = rawC > pa_1_top
inst_el_2_long  = rawC > pa_2_top
inst_el_b_short = rawC < pa_b_bot
inst_el_1_short = rawC < pa_1_bot
inst_el_2_short = rawC < pa_2_bot

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

// \u2500\u2500 DISTANCE RANKING OF THE ELIGIBLE LAYERS \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
// [closest, middle, furthest] by absolute distance from the close. Two eligible
// \u2192 middle resolves to furthest; one \u2192 all three resolve to it; none \u2192 all na
// and the caller falls back to Swing.
f_rank(_e0, _l0, _e1, _l1, _e2, _l2, _ref) =>
    _lv = array.new_float()
    _ds = array.new_float()
    if _e0 and not na(_l0)
        array.push(_lv, _l0)
        array.push(_ds, math.abs(_ref - _l0))
    if _e1 and not na(_l1)
        array.push(_lv, _l1)
        array.push(_ds, math.abs(_ref - _l1))
    if _e2 and not na(_l2)
        array.push(_lv, _l2)
        array.push(_ds, math.abs(_ref - _l2))
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

[ik_near_L, ik_mid_L, ik_far_L] = f_rank(inst_el_b_long,  sha_bot_0, inst_el_1_long,  sha_bot_1, inst_el_2_long,  sha_bot_2, rawC)
[ik_near_S, ik_mid_S, ik_far_S] = f_rank(inst_el_b_short, sha_top_0, inst_el_1_short, sha_top_1, inst_el_2_short, sha_top_2, rawC)
[rk_near_L, rk_mid_L, rk_far_L] = f_rank(elig_b, sha_bot_0, elig_1, sha_bot_1, elig_2, sha_bot_2, rawC)
[rk_near_S, rk_mid_S, rk_far_S] = f_rank(elig_b, sha_top_0, elig_1, sha_top_1, elig_2, sha_top_2, rawC)
'''

# ---- E5: stop functions ---------------------------------------------------
ls, ss = seg(218, 235), seg(237, 254)
ls[0] = "f_long_stop(_kn, _km, _kf) =>"
ss[0] = "f_short_stop(_kn, _km, _kf) =>"


def splice(block, marker, rows, label):
    for i, l in enumerate(block):
        if marker in l:
            return block[:i + 1] + [rows] + block[i + 1:]
    sys.exit("ANCHOR FAIL [%s]: %r not found" % (label, marker))


ls = splice(ls, "Last SHA Bar Beyond Furthest SHA", (
    '      :    sl_mode == "Closest Eligible SHA"          ? (na(_kn) ? sw_low_lvl : _kn)\n'
    '      :    sl_mode == "Middle Eligible SHA"           ? (na(_km) ? sw_low_lvl : _km)\n'
    '      :    sl_mode == "Furthest Eligible SHA"         ? (na(_kf) ? sw_low_lvl : _kf)'), "E5L")
ss = splice(ss, "Last SHA Bar Beyond Furthest SHA", (
    '      :    sl_mode == "Closest Eligible SHA"          ? (na(_kn) ? sw_high_lvl : _kn)\n'
    '      :    sl_mode == "Middle Eligible SHA"           ? (na(_km) ? sw_high_lvl : _km)\n'
    '      :    sl_mode == "Furthest Eligible SHA"         ? (na(_kf) ? sw_high_lvl : _kf)'), "E5S")
E5 = "\n".join(ls) + "\n\n" + "\n".join(ss)

# ---- E6: management inputs -------------------------------------------------
m = "\n".join(seg(256, 301))
m = m.replace('"Base SHA Body","HTF1 SHA Body","HTF2 SHA Body"]',
              '"Base SHA Body","HTF1 SHA Body","HTF2 SHA Body","Closest Eligible SHA","Middle Eligible SHA","Furthest Eligible SHA"]', 1)
if "Closest Eligible SHA" not in m:
    sys.exit("ANCHOR FAIL [E6]: trail options not extended")
m = m.replace('use_align_exit = input.bool(true, "Alignment-Break Exit", group=grp_mgmt)',
              'use_align_exit = input.bool(false, "Exit: Layer Flips Direction", tooltip="Exit when a SHA layer turns against the trade. OFF by default: entries are based on where PRICE sits, so a layer can point the wrong way at entry. Gated on ELIGIBLE (price closed beyond it during the trade) and ARMED (it pointed with the trade at some point).", group=grp_mgmt)', 1)
if 'use_align_exit = input.bool(false' not in m:
    sys.exit("ANCHOR FAIL [E6]: align default not flipped")
m = m.replace('"  Break Trigger"', '"  Flip Trigger"', 1)
m = m.replace('align_confirm_bars = input.int(1, "  Break Must Hold (bars)"',
              'align_confirm_bars = input.int(1, "  Flip Must Hold (bars)"', 1)
for side, lo, arr in (("low", "sha_bot", "L"), ("high", "sha_top", "S")):
    old = 'trail_%s_anchor  = trail_mode == "Swing (Prev N Bars)" ? trail_sw_%s' % (side, side)
    if old not in m:
        old = 'trail_%s_anchor = trail_mode == "Swing (Prev N Bars)" ? trail_sw_%s' % (side, side)
    idx = m.find(old)
    if idx == -1:
        sys.exit("ANCHOR FAIL [E6]: trail_%s_anchor not found" % side)
    eol = m.find("\n", idx)
    line = m[idx:eol]
    if '"HTF2 SHA Body"' in line:
        newline = line.replace(': %s_2' % lo, ': trail_mode == "HTF2 SHA Body" ? %s_2 : trail_mode == "Closest Eligible SHA" ? rk_near_%s : trail_mode == "Middle Eligible SHA" ? rk_mid_%s : rk_far_%s' % (lo, arr, arr, arr), 1)
    else:
        newline = line.replace(': %s_2' % lo, ': trail_mode == "HTF2 SHA Body" ? %s_2 : trail_mode == "Closest Eligible SHA" ? rk_near_%s : trail_mode == "Middle Eligible SHA" ? rk_mid_%s : rk_far_%s' % (lo, arr, arr, arr), 1)
    if newline == line:
        sys.exit("ANCHOR FAIL [E6]: trail_%s_anchor tail not rewritten\n%s" % (side, line))
    m = m[:idx] + newline + m[eol:]
E6 = m

# ---- E7: flip gating replaces the state-test functions ---------------------
E7 = "\n".join(seg(302, 303)) + '''

// \u2500\u2500 LAYER-FLIP CONDITION (eligible AND armed AND now against the trade) \u2500\u2500\u2500\u2500
flip_b_long  = elig_b and arm_b and not base_bull_bar
flip_1_long  = elig_1 and arm_1 and not htf1_bull_bar
flip_2_long  = elig_2 and arm_2 and not htf2_bull_bar
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

# ---- E8: manage + entries --------------------------------------------------
g = "\n".join(seg(339, 435))
g = g.replace("f_align_broken_long()", "align_broken_long").replace("f_align_broken_short()", "align_broken_short")
if "f_align_broken" in g:
    sys.exit("ANCHOR FAIL [E8]: stale align fn reference")
g = g.replace("_s = f_long_stop()",  "_s = f_long_stop(ik_near_L, ik_mid_L, ik_far_L)", 1)
g = g.replace("_s = f_short_stop()", "_s = f_short_stop(ik_near_S, ik_mid_S, ik_far_S)", 1)
if "f_long_stop(ik_near_L" not in g or "f_short_stop(ik_near_S" not in g:
    sys.exit("ANCHOR FAIL [E8]: stop calls not rewired")
n_clear = g.count('pos_dir := "flat"')
g = g.replace('        pos_dir := "flat"', '        pos_dir := "flat"\n        elig_b := false\n        elig_1 := false\n        elig_2 := false\n        arm_b  := false\n        arm_1  := false\n        arm_2  := false')
g = g.replace('        pos_dir := "long"\n',
              '        elig_b := inst_el_b_long\n        elig_1 := inst_el_1_long\n        elig_2 := inst_el_2_long\n        arm_b  := base_bull_bar\n        arm_1  := htf1_bull_bar\n        arm_2  := htf2_bull_bar\n        pos_dir := "long"\n', 1)
g = g.replace('        pos_dir := "short"\n',
              '        elig_b := inst_el_b_short\n        elig_1 := inst_el_1_short\n        elig_2 := inst_el_2_short\n        arm_b  := not base_bull_bar\n        arm_1  := not htf1_bull_bar\n        arm_2  := not htf2_bull_bar\n        pos_dir := "short"\n', 1)
if g.count("elig_b := inst_el_b_long") != 1 or g.count("elig_b := inst_el_b_short") != 1:
    sys.exit("ANCHOR FAIL [E8]: entry seeding not applied exactly once")
E8 = g

out = "\n".join([
    "\n".join(seg(1, 90)),
    "\n".join(seg(125, 130)), "",
    E1, "",
    E2,
    E3,
    "\n".join(seg(180, 216)),
    E4,
    E5, "",
    E6, "",
    E7,
    "\n".join(seg(333, 337)), "",
    E8, "",
    "\n".join(seg(437, len(lines))),
])
open(DST, "w", encoding="utf-8").write(out)
print("OK  wrote %s  (%d lines, %d exit-clear sites)" % (DST, out.count("\n") + 1, n_clear))
