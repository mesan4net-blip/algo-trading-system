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

    # Unguarded `for i = 0 to array.size(x) - 1`.
    # On an EMPTY array that becomes `for 0 to -1`, and Pine counts DOWNWARD
    # rather than skipping - the body runs once with index 0 and array.get
    # throws "index out of bounds". It reads as safe and is not.
    lines = src.split("\n")
    for i, line in enumerate(lines):
        if line.lstrip().startswith("//"):
            continue                      # a comment describing the pattern
        m = re.search(r'for\s+\w+\s*=\s*0\s+to\s+array\.size\((\w+)\)\s*-\s*1', line)
        if m:
            arr = m.group(1)
            # An array built with array.from(...) always has at least one member,
            # so it can never hit the empty case.
            born_full = any(
                re.search(r'\b' + arr + r'\b\s*=\s*.*array\.from\(', l)
                for l in lines[:i])
            guarded = born_full or any(
                (not lines[j].lstrip().startswith("//")) and (
                    re.search(r'array\.size\(\s*' + arr + r'\s*\)\s*>\s*0', lines[j])
                    or re.search(r'\brk_have\b', lines[j]))
                for j in range(max(0, i - 30), i)
            )
            if not guarded:
                problems.append(
                    f"  line {i+1}: `for 0 to array.size({arr}) - 1` is not guarded on size > 0\n"
                    f"      empty array -> `for 0 to -1` -> Pine counts down -> index error")

    # Duplicate top-level declarations. Pine rejects a second `name = ...` at
    # the same scope (CE10095). Easy to introduce when generated text is spliced
    # in and the original declaration sits further down the block.
    seen = {}
    for i, line in enumerate(src.split("\n")):
        m = re.match(r'^([a-zA-Z_]\w*)\s*=(?!=)', line)
        if m:
            n = m.group(1)
            if n in seen:
                problems.append(f"  line {i+1}: `{n}` is declared again (first at line {seen[n]}) - CE10095")
            else:
                seen[n] = i + 1

    code = "\n".join(l for l in src.split("\n") if not l.lstrip().startswith("//"))
    dec = set(re.findall(r'^\s*(?:var\s+\w+\s+|float\[\]\s+|bool\s+|float\s+|int\s+|string\s+|color\s+)?([a-zA-Z_]\w*)\s*:?=', code, re.M))
    for tup in re.findall(r'\[([^\]]+)\]\s*=', code):
        dec |= {x.strip() for x in tup.split(",")}
    # Require a word boundary AFTER the name too. Without it, rk_pT matched the
    # prefix rk_p and reported an undeclared variable that does not exist - a
    # false alarm reported three times before it was worth fixing. A checker
    # that cries wolf gets ignored, which is worse than no checker.
    for v in sorted(set(re.findall(r'(?<![\w.])((?:rk|use|trail|stop|be|tp1|target|giveback|time_stop|entry|peak|risk|traded|armed|go|flip)_[a-z0-9_]+)(?![\w])', code))):
        if v not in dec:
            problems.append(f"  undeclared identifier: {v}")

    print(f"{Path(path).name}: {'OK' if not problems else str(len(problems)) + ' PROBLEM(S)'}")
    for p in problems:
        print(p)
    return not problems

if __name__ == "__main__":
    sys.exit(0 if all([check(a) for a in sys.argv[1:]]) else 1)
