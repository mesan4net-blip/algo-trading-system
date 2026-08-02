#!/usr/bin/env python3
"""Structural checks the repo validator does not cover. Run on every Pine file
before pushing.

The string check exists because a tooltip written with an escaped newline in a
Python builder can collapse into a REAL newline, splitting the Pine string
across lines. Pine rejects that (CE10017) and it is invisible in a diff.
"""
import re, sys
from pathlib import Path

def check(path):
    src = Path(path).read_text()
    problems = []

    for i, line in enumerate(src.split("\n"), 1):
        n, esc = 0, False
        for ch in line:
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
                continue
            if ch == '"':
                n += 1
        if n % 2:
            problems.append(f"  line {i}: unterminated string (CE10017)\n      {line.strip()[:110]}")

    for name, o, c in [("parens", "(", ")"), ("brackets", "[", "]")]:
        d = src.count(o) - src.count(c)
        if d:
            problems.append(f"  {name} unbalanced by {d:+d}")

    code = "\n".join(l for l in src.split("\n") if not l.lstrip().startswith("//"))
    dec = set(re.findall(r'^\s*(?:var\s+\w+\s+|float\[\]\s+|bool\s+|float\s+|int\s+|string\s+|color\s+)?([a-zA-Z_]\w*)\s*:?=', code, re.M))
    for tup in re.findall(r'\[([^\]]+)\]\s*=', code):
        dec |= {x.strip() for x in tup.split(",")}
    for v in sorted(set(re.findall(r'(?<![\w.])((?:rk|use|trail|stop|be|tp1|target|giveback|time_stop|entry|peak|risk|traded|armed|go|flip)_[a-z0-9_]+)', code))):
        if v not in dec:
            problems.append(f"  undeclared identifier: {v}")

    print(f"{Path(path).name}: {'OK' if not problems else str(len(problems)) + ' PROBLEM(S)'}")
    for p in problems:
        print(p)
    return not problems

if __name__ == "__main__":
    sys.exit(0 if all([check(a) for a in sys.argv[1:]]) else 1)
