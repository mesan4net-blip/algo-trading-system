#!/usr/bin/env python3
"""Add a daily cutoff: force-close open trades and block new entries after a
set time in EXCHANGE time.

Exchange time (syminfo.timezone) rather than a fixed offset, so it tracks
daylight saving automatically and is correct for non-US instruments. For a
24-hour instrument like EURUSD there is no session close, so the cutoff is just
set to whatever the desired one is (e.g. NY close).

Ships OFF so no existing behaviour changes until enabled.
"""
import re, sys

INPUTS = '''
// \u2500\u2500 DAILY CUTOFF \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
// Closes any open trade at a set time each day and stops new entries for the
// rest of that day, so nothing is carried overnight. The clock is EXCHANGE
// time, so it follows daylight saving on its own and is right for whichever
// market the instrument trades on. On a 24-hour instrument there is no session
// close, so set the time to whichever close matters (e.g. the NY close).
use_eod    = input.bool(false, "Daily Cutoff", tooltip="Close any open trade at the cutoff time and take no new trades until the next day. Off by default.", group=grp_date)
eod_hour   = input.int(15, "  Cutoff Hour (exchange time, 0-23)", minval=0, maxval=23, tooltip="24-hour clock in the exchange's own time zone. 15 = 3 PM. For a US stock, 15:55 is five minutes before the close.", group=grp_date)
eod_minute = input.int(55, "  Cutoff Minute", minval=0, maxval=59, group=grp_date)
eod_block_entries = input.bool(true, "  Block New Entries After Cutoff", tooltip="Stops new trades opening in the minutes after the cutoff only to be closed straight away. Leave on unless you specifically want late entries.", group=grp_date)

// Minutes since midnight, exchange time, compared against the cutoff.
_now_min = hour(time, syminfo.timezone) * 60 + minute(time, syminfo.timezone)
_eod_min = eod_hour * 60 + eod_minute
past_cutoff = use_eod and _now_min >= _eod_min
eod_entry_block = past_cutoff and eod_block_entries
'''


def patch(path):
    txt = open(path, encoding="utf-8").read()

    # 1. inputs go at the end of the date-filter group
    m = re.search(r"^in_date = not use_date.*$", txt, re.M)
    if not m:
        sys.exit("ANCHOR FAIL [%s]: in_date line not found" % path)
    txt = txt[:m.end()] + "\n" + INPUTS + txt[m.end():]

    # 2. force-close joins the other exit conditions, one per side
    n_exit = 0
    for side, cmp_ in (("long", None), ("short", None)):
        pass
    hits = list(re.finditer(r"^(\s*)_other_out = (.+)$", txt, re.M))
    if len(hits) != 2:
        sys.exit("ANCHOR FAIL [%s]: expected 2 _other_out lines, found %d" % (path, len(hits)))
    for h in reversed(hits):
        indent, rhs = h.group(1), h.group(2)
        new = ("%s_eod_out   = past_cutoff\n%s_other_out = %s or _eod_out" % (indent, indent, rhs))
        txt = txt[:h.start()] + new + txt[h.end():]
        n_exit += 1

    # 3. name the reason so it is distinguishable in the trade list
    n_why = txt.count('_time_out ? "Time" : "SHA Cross"')
    if n_why != 2:
        sys.exit("ANCHOR FAIL [%s]: expected 2 reason ladders, found %d" % (path, n_why))
    txt = txt.replace('_time_out ? "Time" : "SHA Cross"',
                      '_time_out ? "Time" : _eod_out ? "Daily Cutoff" : "SHA Cross"')

    # 4. block entries after the cutoff
    n_gate = 0
    for var in ("long_signal", "short_signal", "rev_long", "rev_short"):
        m = re.search(r"^" + var + r"(\s*)= (.+)$", txt, re.M)
        if not m:
            sys.exit("ANCHOR FAIL [%s]: %s not found" % (path, var))
        txt = txt[:m.start()] + "%s%s= %s and not eod_entry_block" % (var, m.group(1), m.group(2)) + txt[m.end():]
        n_gate += 1

    open(path, "w", encoding="utf-8").write(txt)
    print("%-14s exits:%d  reasons:%d  entry gates:%d" % (path.replace(".pine", ""), n_exit, n_why, n_gate))


if __name__ == "__main__":
    for p in sys.argv[1:]:
        patch(p)
