#!/usr/bin/env python3
"""Add the daily cutoff to the alerts indicators, matching the strategies.

The indicators have no date-filter group and use `_other` rather than
`_other_out`, so the wiring differs from eod_cutoff.py even though the
behaviour is identical.
"""
import re, sys

BLOCK = '''
// \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
// DAILY CUTOFF  (mirrors the strategy)
// \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
// Closes the tracked trade at a set time each day and stops new entries for
// the rest of that day, so the alerts agree with the strategy. The clock is
// EXCHANGE time, so it follows daylight saving on its own and is right for
// whichever market the instrument trades on. On a 24-hour instrument set it to
// whichever close matters (e.g. the NY close).
grp_eod = "\u2460 \u2501\u2501\u2501 DAILY CUTOFF \u2501\u2501\u2501"
use_eod    = input.bool(false, "Daily Cutoff", tooltip="Close the tracked trade at the cutoff time and take no new trades until the next day. Off by default.", group=grp_eod)
eod_hour   = input.int(15, "  Cutoff Hour (exchange time, 0-23)", minval=0, maxval=23, tooltip="24-hour clock in the exchange's own time zone. 15 = 3 PM. For a US stock, 15:55 is five minutes before the close.", group=grp_eod)
eod_minute = input.int(55, "  Cutoff Minute", minval=0, maxval=59, group=grp_eod)
eod_block_entries = input.bool(true, "  Block New Entries After Cutoff", tooltip="Stops new trades opening in the minutes after the cutoff only to be closed straight away.", group=grp_eod)

_now_min = hour(time, syminfo.timezone) * 60 + minute(time, syminfo.timezone)
_eod_min = eod_hour * 60 + eod_minute
past_cutoff = use_eod and _now_min >= _eod_min
eod_entry_block = past_cutoff and eod_block_entries
'''


def patch(path):
    txt = open(path, encoding="utf-8").read()

    # The exit block sits ABOVE the entry signals in the indicators, so the
    # inputs must go before the earlier of the two: the trade-state section.
    m = re.search(r"^// =+\n// TRADE STATE.*$", txt, re.M)
    if not m:
        m = re.search(r"^var string pos_dir", txt, re.M)
    if not m:
        sys.exit("ANCHOR FAIL [%s]: trade-state anchor not found" % path)
    txt = txt[:m.start()] + BLOCK + "\n" + txt[m.start():]

    # force close joins the other exit conditions
    hits = list(re.finditer(r"^(\s*)_other = (.+)$", txt, re.M))
    if len(hits) != 2:
        sys.exit("ANCHOR FAIL [%s]: expected 2 _other lines, found %d" % (path, len(hits)))
    for h in reversed(hits):
        txt = txt[:h.start()] + "%s_other = (%s) or past_cutoff" % (h.group(1), h.group(2)) + txt[h.end():]

    # block entries after the cutoff
    n = 0
    for var in ("long_signal", "short_signal", "rev_long", "rev_short"):
        m = re.search(r"^" + var + r"(\s*)= (.+)$", txt, re.M)
        if not m:
            sys.exit("ANCHOR FAIL [%s]: %s not found" % (path, var))
        txt = txt[:m.start()] + "%s%s= %s and not eod_entry_block" % (var, m.group(1), m.group(2)) + txt[m.end():]
        n += 1

    open(path, "w", encoding="utf-8").write(txt)
    print("%-10s exits:2  entry gates:%d" % (path.replace(".pine", ""), n))


if __name__ == "__main__":
    for p in sys.argv[1:]:
        patch(p)
