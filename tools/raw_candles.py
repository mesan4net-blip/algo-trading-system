#!/usr/bin/env python3
"""Rewire a 3SHA pine file so ALL price data comes from the standard chart type.

Replaces direct uses of open/high/low/close with rawO/rawH/rawL/rawC, which are
fetched once via request.security on a standard ticker. Skips:
  - string literals   (option values like "Body (open/close)" must not change)
  - comments
  - the f_sha function body (uses its own _o/_h/_l/_c parameters)
  - request.security lines (inner refs already evaluate in the requested context)
"""
import re, sys

MAP = {"open": "rawO", "high": "rawH", "low": "rawL", "close": "rawC"}
TOKEN = re.compile(r"\b(open|high|low|close)\b")


def split_code(line):
    """Return (code_part, tail) where tail is string-literal/comment text left alone."""
    out, i, n = [], 0, len(line)
    in_str = False
    while i < n:
        ch = line[i]
        if in_str:
            out.append(("s", ch))
            if ch == '"' and line[i - 1] != "\\":
                in_str = False
        else:
            if ch == '"':
                in_str = True
                out.append(("s", ch))
            elif ch == "/" and i + 1 < n and line[i + 1] == "/":
                out.append(("c", line[i:]))
                break
            else:
                out.append(("c2", ch))
        i += 1
    return out


def rewrite(line):
    parts, buf, res = split_code(line), "", ""
    for kind, txt in parts:
        if kind == "c2":
            buf += txt
        else:
            res += TOKEN.sub(lambda m: MAP[m.group(1)], buf)
            buf = ""
            res += txt
    res += TOKEN.sub(lambda m: MAP[m.group(1)], buf)
    return res


def process(path, out_path):
    lines = open(path, encoding="utf-8").read().split("\n")

    # locate the f_sha body so we can leave it alone
    start = next(i for i, l in enumerate(lines) if l.startswith("f_sha("))
    end = start
    while end + 1 < len(lines) and (lines[end + 1].startswith(("    ", "\t")) or lines[end + 1].strip() == ""):
        end += 1
    while lines[end].strip() == "":
        end -= 1

    changed = 0
    for i, l in enumerate(lines):
        if start <= i <= end:
            continue
        if "request.security" in l:
            continue
        if l.lstrip().startswith("//"):
            continue
        new = rewrite(l)
        if new != l:
            changed += 1
            lines[i] = new

    txt = "\n".join(lines)

    # standard ticker on every security call
    n_sec = txt.count("request.security(syminfo.tickerid")
    txt = txt.replace("request.security(syminfo.tickerid", "request.security(tStd")

    # base layer must now be built from raw candles (done by the token pass)
    if "f_sha(base_len1, base_len2, rawO, rawH, rawL, rawC)" not in txt:
        sys.exit("ANCHOR FAIL: base f_sha call not rewired to raw candles")

    # insert the raw fetch immediately before the layer computation
    marker = "// \u2500\u2500 Compute layers"
    idx = txt.find(marker)
    if idx == -1:
        sys.exit("ANCHOR FAIL: 'Compute layers' marker not found")
    block = (
        "// \u2500\u2500 RAW CANDLE SOURCE \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        "// Pine's open/high/low/close return whatever the CHART is showing. On a\n"
        "// Renko, Heikin-Ashi, Kagi or Line-Break chart those are synthetic values,\n"
        "// so the SHA layers would be built from bricks instead of from price and\n"
        "// would move every time the chart type changed. Everything below sources\n"
        "// from a standard ticker instead, so the layers are identical on any chart\n"
        "// type. NOTE: this fixes the SIGNALS only. Orders still fill at whatever\n"
        "// price the chart bar reports, so backtests must be run on standard\n"
        "// candles regardless \u2014 fills on Renko/HA are not real prices.\n"
        "tStd = ticker.standard(syminfo.tickerid)\n"
        "[rawO, rawH, rawL, rawC] = request.security(tStd, timeframe.period, [open, high, low, close], barmerge.gaps_off, barmerge.lookahead_off)\n\n"
    )
    txt = txt[:idx] + block + txt[idx:]

    open(out_path, "w", encoding="utf-8").write(txt)
    print("%s: %d lines rewritten, %d security calls retargeted" % (out_path, changed, n_sec))
    return txt


if __name__ == "__main__":
    process(sys.argv[1], sys.argv[2])
