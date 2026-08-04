#!/usr/bin/env python3
"""Re-entry, simplified to one rule.

Re-enter when BOTH are true:
  1. the setup is valid again, and
  2. a candle closes beyond the reference level.

The reference level is the CLOSE of whichever candle came last:
  - the candle the trade exited on, or
  - the candle that made the setup invalid.

No ratchet, no expiry, no cap. The most recent of those two events simply sets
the level.
"""
import re, sys

OLD_RESET_INPUT = re.compile(r'^reentry_reset = input\.bool\(true, "  Raise Bar On Setup Break".*$\n', re.M)

OLD_BLOCK = '''// The armed re-entry is never dropped. If the setup breaks, the trigger moves
// up to the most recent swing point (down, for a short) and stays there - it
// ratchets one way only, so a sideways stretch cannot lower the bar.
if reentry_reset and not na(rearm_high) and not all_bull
    rearm_high := math.max(rearm_high, sw_high_lvl)
if reentry_reset and not na(rearm_low) and not all_bear
    rearm_low := math.min(rearm_low, sw_low_lvl)'''

NEW_BLOCK = '''// RE-ENTRY REFERENCE LEVEL
// The level to beat is the CLOSE of whichever candle came last: the one the
// trade exited on, or the one that made the setup invalid. When the setup
// breaks, the level moves to that breaking candle's close. It is not dropped
// and it is not carried over - the most recent event simply sets it.
if not na(rearm_high) and all_bull[1] and not all_bull
    rearm_high := __PX__
if not na(rearm_low) and all_bear[1] and not all_bear
    rearm_low := __PX__'''


def patch(path):
    txt = open(path, encoding="utf-8").read()

    # 1. the reference is now a CLOSE, not the candle's extreme
    px = "rawC" if "rawC" in txt else "close"
    hi = "rawH" if "rawH" in txt else "high"
    lo = "rawL" if "rawL" in txt else "low"
    for old, new, label in (("        rearm_high := %s" % hi, "        rearm_high := %s" % px, "long exit ref"),
                            ("        rearm_low := %s" % lo,  "        rearm_low := %s" % px,  "short exit ref")):
        if txt.count(old) != 1:
            sys.exit("ANCHOR FAIL [%s]: %s found %d times" % (path, label, txt.count(old)))
        txt = txt.replace(old, new, 1)

    # 2. setup-break behaviour: move the level to the breaking candle's close
    if OLD_BLOCK not in txt:
        sys.exit("ANCHOR FAIL [%s]: ratchet block not found verbatim" % path)
    txt = txt.replace(OLD_BLOCK, NEW_BLOCK.replace("__PX__", px), 1)

    # 3. the toggle is gone - the rule is unconditional now
    m = OLD_RESET_INPUT.search(txt)
    if not m:
        sys.exit("ANCHOR FAIL [%s]: reentry_reset input not found" % path)
    txt = txt[:m.start()] + txt[m.end():]

    # 4. comments on the declarations still said "high"/"low"
    txt = txt.replace("// exit candle's high \u2014 long re-entry trigger",
                      "// re-entry level, long  \u2014 a close must beat it")
    txt = txt.replace("// exit candle's low  \u2014 short re-entry trigger",
                      "// re-entry level, short \u2014 a close must beat it")

    # 5. the master-switch tooltip described the old candle-extreme rule
    txt = re.sub(r'(use_reentry = input\.bool\(false, "Re-Enter After Exit", tooltip=")[^"]*(")',
                 r'\1After a trade closes, arm the setup again. It fires when the setup is valid AND a candle CLOSES beyond the reference level. '
                 r'The reference is the close of whichever candle came last: the one the trade exited on, or the one that made the setup invalid.\2',
                 txt, count=1)

    for bad in ("reentry_reset", "rearm_high := %s" % hi, "rearm_low := %s" % lo, "math.max(rearm_high"):
        if bad in txt:
            sys.exit("ANCHOR FAIL [%s]: %r survived" % (path, bad))
    for need in ("rearm_high := %s" % px, "all_bull[1] and not all_bull"):
        if need not in txt:
            sys.exit("ANCHOR FAIL [%s]: %r missing" % (path, need))

    open(path, "w", encoding="utf-8").write(txt)
    print("%-14s re-entry simplified (close-based, reference follows last event)" % path.replace(".pine", ""))


if __name__ == "__main__":
    for p in sys.argv[1:]:
        patch(p)
