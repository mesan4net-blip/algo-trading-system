#!/usr/bin/env python3
"""Add the two-candle re-entry pattern.

For a short, after a trade has closed:
  1. the setup must be valid again;
  2. TRIGGER CANDLE - the first raw bear candle that closes below the body of
     the chosen SHA layer (Base by default);
  3. TRADE CANDLE - a later raw bear candle that closes below the LOW of the
     trigger candle;
  4. enter at the close of that trade candle.

The trigger candle never moves once set. Later candles closing below the layer
body do not replace it. If the setup goes invalid the pattern is abandoned and
starts again from scratch when the setup returns.

Longs are the mirror image: bull candles, above the layer body, above the
trigger candle's HIGH.

The previous close-beyond-reference rule is kept as the other option on a
Re-Entry Style dropdown so it stays testable.
"""
import re, sys

OLD_RE = '''re_long  = use_reentry and not na(rearm_high) and %(px)s > rearm_high and (not reentry_needs_base or all_bull)
re_short = use_reentry and not na(rearm_low)  and %(px)s < rearm_low  and (not reentry_needs_base or all_bear)'''

NEW_RE = '''// ── RE-ENTRY: TWO-CANDLE PATTERN ────────────────────────────────────────────
// Trigger candle: the first raw candle in the trade's direction that closes
// beyond the chosen SHA layer's body. Trade candle: a later raw candle in the
// same direction that closes beyond the TRIGGER CANDLE'S extreme - its low for
// a short, its high for a long. Entry is at that candle's close.
//
// The trigger never moves. Later candles clearing the layer body do not
// replace it. If the setup goes invalid the pattern is abandoned, and starts
// again from scratch when the setup returns.
rex_bot = reentry_layer == "Base" ? %(bot0)s : reentry_layer == "HTF1" ? sha_bot_1 : sha_bot_2
rex_top = reentry_layer == "Base" ? %(top0)s : reentry_layer == "HTF1" ? sha_top_1 : sha_top_2
raw_is_bull = %(px)s > %(po)s
raw_is_bear = %(px)s < %(po)s

var float trig_high = na
var float trig_low  = na

if na(rearm_high) or not all_bull
    trig_high := na
else if na(trig_high) and raw_is_bull and %(px)s > rex_top
    trig_high := %(ph)s

if na(rearm_low) or not all_bear
    trig_low := na
else if na(trig_low) and raw_is_bear and %(px)s < rex_bot
    trig_low := %(pl)s

pat_long  = not na(trig_high) and raw_is_bull and %(px)s > trig_high
pat_short = not na(trig_low)  and raw_is_bear and %(px)s < trig_low

ref_long  = not na(rearm_high) and %(px)s > rearm_high and (not reentry_needs_base or all_bull)
ref_short = not na(rearm_low)  and %(px)s < rearm_low  and (not reentry_needs_base or all_bear)

re_long  = use_reentry and (reentry_style == "Two-candle pattern" ? pat_long  : ref_long)
re_short = use_reentry and (reentry_style == "Two-candle pattern" ? pat_short : ref_short)'''

NEW_INPUTS = '''reentry_style = input.string("Two-candle pattern", "  Re-Entry Style", options=["Two-candle pattern","Close beyond reference"], tooltip="Two-candle pattern: after the setup is valid again, wait for a candle that closes beyond the SHA layer body below (the trigger candle), then enter at the close of a later candle that closes beyond the TRIGGER CANDLE'S low (short) or high (long).\\n\\nClose beyond reference: the simpler rule - enter on any close beyond the close of the candle the trade exited on, or of the candle that made the setup invalid, whichever came last.", group=grp_entry)
reentry_layer = input.string("Base", "  Re-Entry Trigger Layer", options=["Base","HTF1","HTF2"], tooltip="Which SHA layer's body the trigger candle has to close beyond. This applies to RE-ENTRY ONLY - it does not change what the first entry requires.", group=grp_entry)
'''


def patch(path):
    txt = open(path, encoding="utf-8").read()
    px = "rawC" if "rawC" in txt else "close"
    po = "rawO" if "rawO" in txt else "open"
    ph = "rawH" if "rawH" in txt else "high"
    pl = "rawL" if "rawL" in txt else "low"
    # the Renko strategy builds its base body from bricks, not the SHA arrays
    bot0 = "sha_bot_0" if "sha_bot_0" in txt else "math.min(bO, bC)"
    top0 = "sha_top_0" if "sha_top_0" in txt else "math.max(bO, bC)"
    sub = dict(px=px, po=po, ph=ph, pl=pl, bot0=bot0, top0=top0)

    old = OLD_RE % sub
    if old not in txt:
        sys.exit("ANCHOR FAIL [%s]: re_long/re_short block not found" % path)
    txt = txt.replace(old, NEW_RE % sub, 1)

    m = re.search(r'^reentry_needs_base = input\.bool\(.*$\n', txt, re.M)
    if not m:
        sys.exit("ANCHOR FAIL [%s]: reentry_needs_base input not found" % path)
    txt = txt[:m.end()] + NEW_INPUTS + txt[m.end():]

    for need in ("reentry_style", "reentry_layer", "var float trig_high", "pat_short", "ref_short"):
        if need not in txt:
            sys.exit("ANCHOR FAIL [%s]: %r missing" % (path, need))

    # declaration order: inputs and SHA bodies must precede the pattern block
    L = txt.split("\n")
    def first(pat):
        return next((i for i, l in enumerate(L) if re.search(pat, l)), None)
    for var, decl_pat in (("reentry_style", r"^reentry_style = input"),
                          ("reentry_layer", r"^reentry_layer = input"),
                          ("rearm_high", r"^var float  rearm_high")):
        d = first(decl_pat)
        u = first(r"^\s*(if na\(rearm_high\)|rex_bot =|re_long  = use_reentry)")
        if d is None or u is None or d > u:
            sys.exit("ANCHOR FAIL [%s]: %s declared at %s, pattern block at %s" % (path, var, d, u))

    open(path, "w", encoding="utf-8").write(txt)
    print("%-14s two-candle pattern added (px=%s, base body=%s)" % (path.replace(".pine", ""), px, bot0))


if __name__ == "__main__":
    for p in sys.argv[1:]:
        patch(p)
