#!/usr/bin/env python3
"""Derive the S/R-filtered variants of 3SHA Price Above All.

Reads two levels from a separate support/resistance indicator via
input.source(), so no third-party code is copied - which also sidesteps the
CC BY-NC-SA ShareAlike terms on the LuxAlgo script.

Entries are DEFERRED, not cancelled, while price sits inside the band: the
armed-entry mechanism already holds the setup, so the trade fires as soon as
price clears the level or the level moves away. Nothing is thrown away.

Usage: derive_sr.py <src_strategy> <dst_strategy> <src_indicator> <dst_indicator>
"""
import re, sys

INPUTS = '''
// ── SUPPORT / RESISTANCE FILTER ─────────────────────────────────────────────
// Reads levels from a SEPARATE indicator on the same chart. Point the two
// sources at that indicator's resistance and support plots; nothing is
// computed here and no third-party code is copied.
//
// The levels lag by design. A pivot needs its right-hand bars before it can be
// confirmed, so the level in force on any bar was established well before it.
// The other script draws its lines shifted BACK to the pivot, which makes them
// look present earlier than they were known - so do not judge this filter by
// eye off the chart. It is honest, it just knows less than the drawing implies.
grp_sr = "\u2468 \u2501\u2501\u2501 S/R FILTER \u2501\u2501\u2501"
use_sr = input.bool(false, "Avoid Entries Near S/R", tooltip="Hold a long while resistance sits just above, and a short while support sits just below. OFF by default: it does nothing until both sources below are pointed at a support/resistance indicator on this chart.", group=grp_sr)
sr_res_src = input.source(close, "  Resistance Source", tooltip="Pick the resistance plot from your support/resistance indicator. Leaving this on close makes the filter meaningless, so it is ignored unless it differs from price.", group=grp_sr)
sr_sup_src = input.source(close, "  Support Source", tooltip="Pick the support plot from the same indicator.", group=grp_sr)
sr_band_pct = input.float(0.30, "  Keep Clear By (%)", minval=0.0, step=0.05, tooltip="How close price has to be to the level before entries are held, as a percentage of price. 0.30 on a $600 instrument is about $1.80.", group=grp_sr)

// A level only counts on the side it is actually on: resistance ABOVE price,
// support BELOW it. A pivot high that price has already cleared is acting as
// support, and holding longs on it would be backwards.
_sr_band  = __PX__ * sr_band_pct / 100.0
_sr_armed = use_sr and sr_res_src != __PX__ and sr_sup_src != __PX__
sr_hold_long  = _sr_armed and not na(sr_res_src) and sr_res_src > __PX__ and (sr_res_src - __PX__) <= _sr_band
sr_hold_short = _sr_armed and not na(sr_sup_src) and sr_sup_src < __PX__ and (__PX__ - sr_sup_src) <= _sr_band
'''


def patch(src, dst, is_strategy):
    t = open(src, encoding="utf-8").read()
    px = "rawC" if "rawC" in t else "close"

    # rename so both variants can sit on one chart
    if is_strategy:
        for a, b in (('strategy("3SHA Price Above All", shorttitle="3SHA-PAA"',
                      'strategy("3SHA Price Above All + S/R", shorttitle="3SHA-PAA-SR"'),
                     ('"PAA"', '"PAASR"'), ('"PAA-stop"', '"PAASR-stop"')):
            if a not in t:
                sys.exit("ANCHOR FAIL [%s]: %r" % (src, a))
            t = t.replace(a, b)
    else:
        for a, b in (('indicator("3SHA Price Above All Alerts", shorttitle="3SHA-PA Alerts"',
                      'indicator("3SHA Price Above All + S/R Alerts", shorttitle="3SHA-PA-SR Alerts"'),):
            if a not in t:
                sys.exit("ANCHOR FAIL [%s]: %r" % (src, a))
            t = t.replace(a, b, 1)

    # inputs go immediately before the armed-entry block, which is where they are read
    m = re.search(r"^// \u2500\u2500 ARMED ENTRY", t, re.M)
    if not m:
        sys.exit("ANCHOR FAIL [%s]: armed entry block" % src)
    t = t[:m.start()] + INPUTS.replace("__PX__", px).strip() + "\n\n" + t[m.start():]

    # gate every entry path; the arm is NOT cleared, so this defers rather than cancels
    n = 0
    for var, cond in (("long_signal", "sr_hold_long"), ("short_signal", "sr_hold_short"),
                      ("rev_long", "sr_hold_long"), ("rev_short", "sr_hold_short"),
                      ("raw_long", "sr_hold_long"), ("raw_short", "sr_hold_short")):
        m = re.search(r"^" + var + r"(\s*)= (.+)$", t, re.M)
        if not m:
            continue
        t = t[:m.start()] + "%s%s= %s and not %s" % (var, m.group(1), m.group(2), cond) + t[m.end():]
        n += 1
    if n < 4:
        sys.exit("ANCHOR FAIL [%s]: only %d entry paths gated" % (src, n))

    # a held entry should be visible, not silent
    m = re.search(r'^    table\.cell\(hud, 0, 8, "Raw Candle".*$', t, re.M)
    if not m:
        sys.exit("ANCHOR FAIL [%s]: HUD raw candle row" % src)
    rows = int(re.search(r"table\.new\(_hp, 2, (\d+),", t).group(1))
    t = re.sub(r"table\.new\(_hp, 2, \d+,", "table.new(_hp, 2, %d," % (rows + 1), t, count=1)
    add = ('\n\n    _srtxt = not _sr_armed ? "off" : (sr_hold_long or sr_hold_short) ? "\u25cf HOLDING" : "clear"\n'
           '    _srcol = (sr_hold_long or sr_hold_short) ? col_stop : _bg\n'
           '    table.cell(hud, 0, %d, "S/R Filter", text_color=color.white, bgcolor=_bg, text_size=size.small)\n'
           '    table.cell(hud, 1, %d, _srtxt, text_color=color.white, bgcolor=_srcol, text_size=size.small)') % (rows, rows)
    # append after the last existing row
    last = max(int(x) for x in re.findall(r"table\.cell\(hud, 0, (\d+),", t))
    m2 = re.search(r'^    table\.cell\(hud, 1, %d,.*$' % last, t, re.M)
    t = t[:m2.end()] + add + t[m2.end():]

    for need in ("sr_hold_long", "sr_hold_short", "input.source", "S/R Filter"):
        if need not in t:
            sys.exit("ANCHOR FAIL [%s]: %r missing" % (src, need))
    L = t.split("\n")
    d = next(i for i, l in enumerate(L) if l.startswith("sr_hold_long"))
    u = next(i for i, l in enumerate(L) if re.match(r"^(long_signal|raw_long)", l))
    if d > u:
        sys.exit("ANCHOR FAIL [%s]: sr_hold_long@%d used@%d" % (src, d, u))

    open(dst, "w", encoding="utf-8").write(t)
    print("%-34s %d entry paths gated, HUD row added" % (dst, n))


if __name__ == "__main__":
    patch(sys.argv[1], sys.argv[2], True)
    patch(sys.argv[3], sys.argv[4], False)
