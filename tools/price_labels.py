#!/usr/bin/env python3
"""Add price labels at entry and exit, held clear of the candles.

The strategies already draw small markers. This adds readable labels showing
the actual entry and exit price, offset away from the bar so they do not sit on
top of it. Offset is a percentage of price, so one setting works on any
instrument.

Markers and labels get separate toggles - either can be shown without the
other.
"""
import re, sys

INPUTS = '''show_price_labels = input.bool(true, "Entry / Exit Price Labels", tooltip="Shows the actual fill price at each entry and exit, in a label held clear of the candle.", group=grp_disp)
label_offset_pct = input.float(0.30, "  Label Distance (%)", minval=0.0, step=0.05, tooltip="How far the label sits from the candle, as a percentage of price. Raise it if labels overlap the bars.", group=grp_disp)
'''

CAPTURE = '''
// Entry price has to be captured before the exit block clears it, or the exit
// label has nothing to report.
var float lbl_entry_px = na
'''

DRAW = '''
// ── ENTRY / EXIT PRICE LABELS ───────────────────────────────────────────────
// Held clear of the candle by a percentage of price, so the gap looks the same
// on a $20 stock and a $600 one.
_lbl_off = %(px)s * label_offset_pct / 100.0
if show_price_labels and did_enter
    _up = pos_dir == "long"
    label.new(bar_index, _up ? %(pl)s - _lbl_off : %(ph)s + _lbl_off,
         text = (_up ? "LONG " : "SHORT ") + str.tostring(entry_price, format.mintick),
         style = _up ? label.style_label_up : label.style_label_down,
         color = _up ? color.new(#2962FF, 15) : color.new(#F23645, 15),
         textcolor = color.white, size = size.small)

if show_price_labels and did_exit
    _wasup = not na(lbl_entry_px) and %(px)s >= 0 and pos_dir_prev == "long"
    label.new(bar_index, _wasup ? %(ph)s + _lbl_off : %(pl)s - _lbl_off,
         text = exit_reason + " " + str.tostring(%(px)s, format.mintick),
         style = _wasup ? label.style_label_down : label.style_label_up,
         color = exit_reason == "STOP" ? color.new(#F23645, 15) : color.new(#FF9800, 15),
         textcolor = color.white, size = size.small)
'''


def patch(path):
    txt = open(path, encoding="utf-8").read()
    px = "rawC" if "rawC" in txt else "close"
    ph = "rawH" if "rawH" in txt else "high"
    pl = "rawL" if "rawL" in txt else "low"

    # 1. inputs, after the existing markers toggle
    m = re.search(r'^show_markers = input\.bool\(true, "Entry / Exit Markers", group=grp_disp\)$\n', txt, re.M)
    if not m:
        sys.exit("ANCHOR FAIL [%s]: show_markers input not found" % path)
    txt = txt[:m.end()] + INPUTS + txt[m.end():]

    # 2. state: remember the entry price and which way the trade was facing,
    #    both of which are wiped by the exit block before the label can read them
    m = re.search(r'^did_exit  = false$', txt, re.M)
    if not m:
        sys.exit("ANCHOR FAIL [%s]: did_exit declaration not found" % path)
    txt = txt[:m.start()] + CAPTURE.strip() + "\nvar string pos_dir_prev = \"flat\"\npos_dir_prev := pos_dir\n\n" + txt[m.start():]

    # 3. record the entry price at both entry sites
    n = txt.count("        entry_price := %s\n" % px)
    if n != 2:
        sys.exit("ANCHOR FAIL [%s]: expected 2 entry sites, found %d" % (path, n))
    txt = txt.replace("        entry_price := %s\n" % px,
                      "        entry_price := %s\n        lbl_entry_px := %s\n" % (px, px))

    # 4. drawing goes after the existing marker plots
    m = re.search(r'^plotshape\(show_markers and did_exit.*\n.*size=size\.tiny\)$', txt, re.M)
    if not m:
        sys.exit("ANCHOR FAIL [%s]: exit marker plot not found" % path)
    txt = txt[:m.end()] + "\n" + (DRAW % dict(px=px, ph=ph, pl=pl)) + txt[m.end():]

    for need in ("show_price_labels", "label_offset_pct", "lbl_entry_px", "pos_dir_prev", "label.new"):
        if need not in txt:
            sys.exit("ANCHOR FAIL [%s]: %r missing" % (path, need))

    L = txt.split("\n")
    def first(p):
        return next((i for i, l in enumerate(L) if re.match(p, l)), None)
    d_in = first(r"^show_price_labels = input")
    d_prev = first(r"^var string pos_dir_prev")
    d_use = first(r"^_lbl_off =")
    if None in (d_in, d_prev, d_use) or not (d_in < d_use and d_prev < d_use):
        sys.exit("ANCHOR FAIL [%s]: order in=%s prev=%s use=%s" % (path, d_in, d_prev, d_use))

    open(path, "w", encoding="utf-8").write(txt)
    print("%-14s price labels added (px=%s)" % (path.replace(".pine", ""), px))


if __name__ == "__main__":
    for p in sys.argv[1:]:
        patch(p)
