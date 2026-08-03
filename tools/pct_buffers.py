#!/usr/bin/env python3
"""Convert the four absolute price-unit inputs to percent-of-price.

Absolute units do not travel between instruments: a buffer of 2.0 is 0.003% on
BTCUSDT, 0.4% on QQQ and 185% on EURUSD. This rewrites all four to percentages
so one setting is meaningful everywhere.

Handles both wiring styles:
  strategies  X_raw = X_units          -> X_raw = <price> * X_pct / 100
  indicators  X_units used directly    -> X_raw introduced, uses repointed
"""
import re, sys

SPECS = {
    "sl_buffer":    (0.10, "Stop Buffer (%)",
                     "How far beyond the anchor the stop sits, as a percentage of price. "
                     "0.10 means one tenth of one percent. Percent rather than a fixed amount so "
                     "the same setting is meaningful on any instrument."),
    "min_stop":     (0.00, "Min Stop Distance (%)",
                     "Floor on stop distance, as a percentage of price. The stop is never placed "
                     "closer to entry than this. 0 = off."),
    "trail_buffer": (0.10, "  Trail Buffer (%)",
                     "How far beyond the trail anchor the trailing stop sits, as a percentage of price."),
    "be_offset":    (0.00, "  Break-Even Offset (%)",
                     "How far beyond entry the break-even stop sits, as a percentage of price. "
                     "0 = exactly at entry."),
}


def convert(path):
    txt = open(path, encoding="utf-8").read()
    price = "rawC" if "rawC" in txt else "close"
    report = []

    for base, (default, label, tip) in SPECS.items():
        unit, pct, raw = base + "_units", base + "_pct", base + "_raw"

        m = re.search(r"^" + unit + r"\s*=\s*input\.float\((.*)\)\s*$", txt, re.M)
        if not m:
            sys.exit("ANCHOR FAIL [%s]: %s input.float not found in %s" % (base, unit, path))
        args = m.group(1)

        g = re.search(r"group=(\w+)", args)
        if not g:
            sys.exit("ANCHOR FAIL [%s]: group= not found in %s" % (base, path))
        group = g.group(1)

        new_input = ('%s = input.float(%.2f, "%s", minval=0.0, step=0.01, tooltip="%s", group=%s)\n'
                     '%s = %s * %s / 100' % (pct, default, label, tip, group, raw, price, pct))
        txt = txt[:m.start()] + new_input + txt[m.end():]

        # any remaining reference to the old absolute input becomes the derived value
        n_left = len(re.findall(r"\b" + unit + r"\b", txt))
        txt = re.sub(r"\b" + unit + r"\b", raw, txt)

        # kill the now-tautological indirection line the strategies carried
        before = txt
        txt = re.sub(r"^" + raw + r"\s*=\s*" + raw + r"\s*$\n?", "", txt, flags=re.M)
        dropped = before != txt

        report.append((base, n_left, dropped))

    for base in SPECS:
        if re.search(r"\b" + base + r"_units\b", txt):
            sys.exit("ANCHOR FAIL: %s_units survived in %s" % (base, path))
        if not re.search(r"\b" + base + r"_raw\s*=\s*" + price, txt):
            sys.exit("ANCHOR FAIL: %s_raw not derived from %s in %s" % (base, price, path))

    open(path, "w", encoding="utf-8").write(txt)
    print("%-14s price ref=%-5s  %s" % (path.replace(".pine", ""), price,
          "  ".join("%s:%d refs%s" % (b, n, "/dedup" if d else "") for b, n, d in report)))


if __name__ == "__main__":
    for p in sys.argv[1:]:
        convert(p)
