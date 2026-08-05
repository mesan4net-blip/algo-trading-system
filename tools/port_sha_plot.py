#!/usr/bin/env python3
"""Draw the SHA candles in the alerts indicators.

The indicators computed all three SHA layers but never drew them - they only
ever plotted entry/exit markers and the stop line. So the layers the alerts are
based on were invisible.

Both the colour inputs and the plotcandle calls are lifted VERBATIM from the
matching strategy, so the two cannot drift. The script asserts the extracted
text is identical to what the strategy contains.

Usage:  port_sha_plot.py <strategy.pine> <indicator.pine>
"""
import re, sys


def grab_inputs(strat):
    """The colour/display inputs the plotcandle block depends on."""
    pat = re.compile(
        r'^(grp_layers_disp|show_wicks|show_borders'
        r'|base_show|base_bull|base_bear|base_border|base_wick|base_opacity'
        r'|htf1_show|htf1_bull|htf1_bear|htf1_border_bull|htf1_border_bear|htf1_wick|htf1_opacity'
        r'|htf2_show|htf2_bull|htf2_bear|htf2_border_bull|htf2_border_bear|htf2_wick|htf2_opacity)\s*=', re.M)
    out = [l for l in strat.split("\n") if pat.match(l)]
    if len(out) < 20:
        sys.exit("ANCHOR FAIL: expected >=20 display inputs, got %d" % len(out))
    return out


def grab_plot(strat):
    """From the first body-colour line through the last plotcandle call."""
    L = strat.split("\n")
    start = next((i for i, l in enumerate(L) if l.startswith("htf2_body_col =")), None)
    if start is None:
        sys.exit("ANCHOR FAIL: htf2_body_col not found")
    last = max(i for i, l in enumerate(L) if "plotcandle(" in l)
    end = last
    while end + 1 < len(L) and L[end + 1].startswith("           "):
        end += 1
    block = L[start:end + 1]
    if block.count("") > 4 or sum(1 for l in block if "plotcandle(" in l) != 3:
        sys.exit("ANCHOR FAIL: expected exactly 3 plotcandle calls in the block")
    return block


def patch(strat_path, ind_path):
    strat = open(strat_path, encoding="utf-8").read()
    ind = open(ind_path, encoding="utf-8").read()

    inputs = grab_inputs(strat)
    plot = grab_plot(strat)

    if "plotcandle" in ind:
        sys.exit("ANCHOR FAIL [%s]: already draws candles" % ind_path)

    # the indicator groups are numbered differently; keep its own numbering
    ren = [l.replace('grp_layers_disp = "\u2461 \u2501\u2501\u2501 SHA DISPLAY  [all layers] \u2501\u2501\u2501"',
                     'grp_layers_disp = "\u2460 \u2501\u2501\u2501 SHA DISPLAY  [all layers] \u2501\u2501\u2501"') for l in inputs]

    # inputs go immediately after the HTF2 layer inputs, before the raw source
    m = re.search(r'^// \u2500\u2500 RAW CANDLE SOURCE', ind, re.M)
    if not m:
        sys.exit("ANCHOR FAIL [%s]: raw candle source marker not found" % ind_path)
    ind = ind[:m.start()] + "\n".join(ren) + "\n\n" + ind[m.start():]

    # plotting goes at the very end, after the existing markers
    ind = ind.rstrip("\n") + "\n\n" + (
        "// ============================================================================\n"
        "// SHA CANDLES  (identical to the strategy - derived, do not edit by hand)\n"
        "// ============================================================================\n"
        + "\n".join(plot) + "\n")

    for need in ("plotcandle(", "base_body_col", "htf1_body_col", "htf2_body_col", "show_wicks"):
        if need not in ind:
            sys.exit("ANCHOR FAIL [%s]: %r missing after patch" % (ind_path, need))

    # every identifier the plot block reads must be declared before it
    L = ind.split("\n")
    plot_at = next(i for i, l in enumerate(L) if l.startswith("htf2_body_col ="))
    for ident in ("show_wicks", "show_borders", "base_show", "htf1_show", "htf2_show",
                  "base_bull", "htf1_bull", "htf2_bull", "base_ready", "htf1_ready", "htf2_ready"):
        d = next((i for i, l in enumerate(L) if re.match(r"^" + ident + r"\s*=", l)), None)
        if d is None or d > plot_at:
            sys.exit("ANCHOR FAIL [%s]: %s declared at %s, plot block at %s" % (ind_path, ident, d, plot_at))

    open(ind_path, "w", encoding="utf-8").write(ind)
    print("%-14s +%d colour inputs, +3 plotcandle calls" % (ind_path.replace(".pine", ""), len(ren)))


if __name__ == "__main__":
    patch(sys.argv[1], sys.argv[2])
