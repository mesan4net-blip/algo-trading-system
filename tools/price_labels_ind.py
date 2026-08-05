#!/usr/bin/env python3
"""Add entry/exit price labels to the alerts indicators.

Same feature as the strategies, different plumbing: the indicators track their
events with fire_* flags rather than did_enter/did_exit, and they clear pos_dir
in the exit block before the label could read it.
"""
import re, sys

INPUTS = '''show_price_labels = input.bool(true, "Show entry/exit price labels", tooltip="Shows the fill price at each entry and exit, in a label held clear of the candle.", group=grp_disp)
label_offset_pct = input.float(0.30, "  Label distance (%)", minval=0.0, step=0.05, tooltip="How far the label sits from the candle, as a percentage of price. Raise it if labels overlap the bars.", group=grp_disp)
'''

STATE = '''// Held for the labels: the exit block clears entry_price and flips pos_dir to
// "flat" before either can be read.
var float  lbl_entry_px = na
var string pos_dir_prev = "flat"
pos_dir_prev := pos_dir

'''

DRAW = '''
// ── ENTRY / EXIT PRICE LABELS ───────────────────────────────────────────────
// Held clear of the candle by a percentage of price, so the gap looks the same
// on a $20 stock and a $600 one.
_lbl_off = %(px)s * label_offset_pct / 100.0
if show_price_labels and (fire_entry_long or fire_entry_short)
    _up = fire_entry_long
    label.new(bar_index, _up ? %(pl)s - _lbl_off : %(ph)s + _lbl_off,
         text = (_up ? "LONG " : "SHORT ") + str.tostring(%(px)s, format.mintick),
         style = _up ? label.style_label_up : label.style_label_down,
         color = _up ? color.new(#2962FF, 15) : color.new(#F23645, 15),
         textcolor = color.white, size = size.small)

if show_price_labels and (fire_stop_hit or fire_align_break)
    _wasup = pos_dir_prev == "long"
    _why   = fire_stop_hit ? "STOP" : "EXIT"
    label.new(bar_index, _wasup ? %(ph)s + _lbl_off : %(pl)s - _lbl_off,
         text = _why + " " + str.tostring(%(px)s, format.mintick)
                + (na(lbl_entry_px) ? "" : "  (from " + str.tostring(lbl_entry_px, format.mintick) + ")"),
         style = _wasup ? label.style_label_down : label.style_label_up,
         color = fire_stop_hit ? color.new(#F23645, 15) : color.new(#FF9800, 15),
         textcolor = color.white, size = size.small)
'''


def patch(path):
    txt = open(path, encoding="utf-8").read()
    px = "rawC" if "rawC" in txt else "close"
    ph = "rawH" if "rawH" in txt else "high"
    pl = "rawL" if "rawL" in txt else "low"

    m = re.search(r'^show_marks = input\.bool\(true, "Show entry/exit markers", group=grp_disp\)$\n', txt, re.M)
    if not m:
        sys.exit("ANCHOR FAIL [%s]: show_marks input not found" % path)
    txt = txt[:m.end()] + INPUTS + txt[m.end():]

    m = re.search(r'^ev_entry_long  = false$', txt, re.M)
    if not m:
        sys.exit("ANCHOR FAIL [%s]: ev_entry_long declaration not found" % path)
    txt = txt[:m.start()] + STATE + txt[m.start():]

    n = txt.count("        entry_price := %s\n" % px)
    if n != 2:
        sys.exit("ANCHOR FAIL [%s]: expected 2 entry sites, found %d" % (path, n))
    txt = txt.replace("        entry_price := %s\n" % px,
                      "        entry_price := %s\n        lbl_entry_px := %s\n" % (px, px))

    m = re.search(r'^plotshape\(show_marks and fire_stop_hit.*$', txt, re.M)
    if not m:
        sys.exit("ANCHOR FAIL [%s]: stop-hit marker plot not found" % path)
    txt = txt[:m.end()] + "\n" + (DRAW % dict(px=px, ph=ph, pl=pl)) + txt[m.end():]

    if "max_labels_count" not in txt:
        sys.exit("ANCHOR FAIL [%s]: max_labels_count not declared" % path)

    L = txt.split("\n")
    def first(p):
        return next((i for i, l in enumerate(L) if re.match(p, l)), None)
    order = [("inputs", first(r"^show_price_labels = input")),
             ("state", first(r"^var float  lbl_entry_px")),
             ("assign", first(r"^pos_dir_prev :=")),
             ("use", first(r"^_lbl_off ="))]
    if any(v is None for _, v in order) or not all(order[i][1] < order[-1][1] for i in range(3)):
        sys.exit("ANCHOR FAIL [%s]: order %s" % (path, order))
    if txt.count("lbl_entry_px :=") != 2:
        sys.exit("ANCHOR FAIL [%s]: entry capture not applied twice" % path)

    open(path, "w", encoding="utf-8").write(txt)
    print("%-14s price labels added (px=%s)" % (path.replace(".pine", ""), px))


if __name__ == "__main__":
    for p in sys.argv[1:]:
        patch(p)
