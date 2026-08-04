#!/usr/bin/env python3
"""Revise the re-entry rule.

Before: if the setup broke before price cleared the exit candle, the armed
re-entry was deleted outright. After a stop-out near the highs the setup is
almost always broken on the very next bar, so the token died before the move it
existed to catch had even started. The only route back in was a fresh
transition, which cannot happen while price stays beyond the layers.

After: the token is never deleted. When the setup breaks, the trigger level
moves to the most recent swing point - real structure rather than an arbitrary
bar - and it only ever moves in the trade's favour, so a stall cannot lower the
bar for getting back in.

Pullback-and-resume falls out of this with no extra machinery: with 'Setup Must
Still Hold' on, re-entry needs the setup back AND price beyond the ratcheted
level.
"""
import re, sys

OLD_INPUT_RE = re.compile(
    r'^reentry_expires = input\.bool\(true, "  Cancel If Setup Breaks".*$', re.M)

NEW_INPUT = ('reentry_reset = input.bool(true, "  Raise Bar On Setup Break", '
             'tooltip="If the condition fails before price clears the exit candle, move the re-entry trigger to the most recent swing point instead of dropping it. '
             'The trigger only ever moves in the trade\'s favour, so a stall cannot make getting back in easier. '
             'Off: the trigger stays at the exit candle\'s extreme however long the setup is broken.", group=grp_entry)')

OLD_WIPE = '''if reentry_expires and not na(rearm_high) and not all_bull
    rearm_high := na
if reentry_expires and not na(rearm_low) and not all_bear
    rearm_low := na'''

NEW_WIPE = '''// The armed re-entry is never dropped. If the setup breaks, the trigger moves
// up to the most recent swing point (down, for a short) and stays there - it
// ratchets one way only, so a sideways stretch cannot lower the bar.
if reentry_reset and not na(rearm_high) and not all_bull
    rearm_high := math.max(rearm_high, sw_high_lvl)
if reentry_reset and not na(rearm_low) and not all_bear
    rearm_low := math.min(rearm_low, sw_low_lvl)'''


def patch(path):
    txt = open(path, encoding="utf-8").read()

    m = OLD_INPUT_RE.search(txt)
    if not m:
        sys.exit("ANCHOR FAIL [%s]: reentry_expires input not found" % path)
    txt = txt[:m.start()] + NEW_INPUT + txt[m.end():]

    if OLD_WIPE not in txt:
        sys.exit("ANCHOR FAIL [%s]: wipe block not found verbatim" % path)
    txt = txt.replace(OLD_WIPE, NEW_WIPE, 1)

    if "reentry_expires" in txt:
        sys.exit("ANCHOR FAIL [%s]: reentry_expires survived" % path)
    for need in ("math.max(rearm_high, sw_high_lvl)", "math.min(rearm_low, sw_low_lvl)"):
        if need not in txt:
            sys.exit("ANCHOR FAIL [%s]: %s missing" % (path, need))

    # sw_high_lvl / sw_low_lvl must be declared before the ratchet uses them
    L = txt.split("\n")
    for lvl in ("sw_high_lvl", "sw_low_lvl"):
        decl = next((i for i, l in enumerate(L) if re.match(r"^" + lvl + r"\s*=", l)), None)
        use = next((i for i, l in enumerate(L) if "math." in l and lvl in l), None)
        if decl is None or use is None or use < decl:
            sys.exit("ANCHOR FAIL [%s]: %s declared at %s, used at %s" % (path, lvl, decl, use))

    open(path, "w", encoding="utf-8").write(txt)
    print("%-14s re-entry revised (no expiry, ratcheting swing reset)" % path.replace(".pine", ""))


if __name__ == "__main__":
    for p in sys.argv[1:]:
        patch(p)
