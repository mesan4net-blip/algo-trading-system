#!/usr/bin/env python3
"""
renko_repaint_test.py — does the PAAR renko engine actually not repaint?

The Pine engine is ported here line-for-line. The test that matters is the one
the built-in TradingView renko fails: load a different amount of history and see
whether the bricks at a given bar change.

Three properties are checked:
  A. GRID STABILITY   — brick boundaries at the same bar, different history load
  B. FROZEN HISTORY   — state at bar N never changes as later bars arrive
  C. COLD-START CONVERGENCE — how long two different start dates take to agree
"""

import math
import random
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Engine — mirrors the Pine block in 3SHA_PriceAboveAll_Renko_v1.pine
# ---------------------------------------------------------------------------
class Renko:
    def __init__(self, mult=0.25, round_step=0.0001, min_box=0.0, rev=2, confirm=1):
        self.mult, self.round_step, self.min_box = mult, round_step, min_box
        self.rev, self.confirm = rev, confirm
        self.day_hi = self.day_lo = None
        self.sum_r, self.n_days = 0.0, 0
        self.box = None
        self.top = self.bot = None
        self.dir = 0
        self.run = 0
        self.prev_day = self.prev_month = None
        self.month_ok = False

    def step(self, ts, h, l, c):
        day, month = ts.date(), (ts.year, ts.month)
        new_day = self.prev_day is not None and day != self.prev_day
        new_month = self.prev_month is not None and month != self.prev_month

        prev_hi, prev_lo = self.day_hi, self.day_lo

        # bank the completed day BEFORE the month rollover
        if new_day and self.month_ok and prev_hi is not None and prev_lo is not None:
            self.sum_r += prev_hi - prev_lo
            self.n_days += 1

        if new_month:
            self.month_ok = True

        self.day_hi = h if (new_day or self.day_hi is None) else max(self.day_hi, h)
        self.day_lo = l if (new_day or self.day_lo is None) else min(self.day_lo, l)

        box_new = False
        if new_month and self.n_days > 0:
            raw = self.sum_r / self.n_days * self.mult
            step = self.round_step if self.round_step > 0 else 0.0
            rounded = round(raw / step) * step if step > 0 else raw
            floor_v = self.min_box if self.min_box > 0 else (step if step > 0 else 0.0)
            self.box = max(rounded, floor_v)
            box_new = True
            self.sum_r, self.n_days = 0.0, 0

        # silent re-anchor: direction and run carry over, no brick prints
        if box_new and self.box and self.box > 0:
            self.bot = math.floor(c / self.box) * self.box
            self.top = self.bot + self.box

        bricks = 0
        if (not box_new) and self.box and self.box > 0 and self.top is not None:
            for _ in range(200):
                printed = False
                if self.dir == 1:
                    if c >= self.top + self.box:
                        self.bot = self.top
                        self.top += self.box
                        self.run += 1
                        printed = True
                    elif c <= self.top - self.rev * self.box:
                        self.top = self.top - (self.rev - 1) * self.box
                        self.bot = self.top - self.box
                        self.dir, self.run = -1, 1
                        printed = True
                elif self.dir == -1:
                    if c <= self.bot - self.box:
                        self.top = self.bot
                        self.bot -= self.box
                        self.run += 1
                        printed = True
                    elif c >= self.bot + self.rev * self.box:
                        self.bot = self.bot + (self.rev - 1) * self.box
                        self.top = self.bot + self.box
                        self.dir, self.run = 1, 1
                        printed = True
                else:
                    if c >= self.top + self.box:
                        self.bot = self.top
                        self.top += self.box
                        self.dir, self.run = 1, 1
                        printed = True
                    elif c <= self.bot - self.box:
                        self.top = self.bot
                        self.bot -= self.box
                        self.dir, self.run = -1, 1
                        printed = True
                if not printed:
                    break
                bricks += 1

        self.prev_day, self.prev_month = day, month
        return dict(box=self.box, top=self.top, bot=self.bot,
                    dir=self.dir, run=self.run, bricks=bricks)


# ---------------------------------------------------------------------------
# Synthetic EUR/USD-like 15m series with drifting volatility
# ---------------------------------------------------------------------------
def make_series(n=30000, seed=7):
    rnd = random.Random(seed)
    t = datetime(2024, 1, 1)
    px = 1.0850
    vol = 0.00035
    out = []
    for i in range(n):
        # volatility regime drifts so monthly box sizes actually change
        vol *= math.exp(rnd.gauss(0, 0.004))
        vol = min(max(vol, 0.00012), 0.0012)
        px *= math.exp(rnd.gauss(0, vol))
        hi = px * (1 + abs(rnd.gauss(0, vol * 0.6)))
        lo = px * (1 - abs(rnd.gauss(0, vol * 0.6)))
        out.append((t, hi, lo, px))
        t += timedelta(minutes=15)
    return out


def run(series):
    r = Renko()
    return [r.step(*b) for b in series]


def main():
    S = make_series()
    print(f"series: {len(S)} bars, {S[0][0].date()} → {S[-1][0].date()}")

    full = run(S)
    boxes = sorted({round(f["box"], 6) for f in full if f["box"]})
    print(f"distinct monthly box sizes: {len(boxes)}  "
          f"min {min(boxes):.4f}  max {max(boxes):.4f}\n")

    # --- B. FROZEN HISTORY --------------------------------------------------
    # Truncate the series and re-run. State at every surviving bar must be
    # byte-identical: later bars must never reach back and change earlier ones.
    ok = True
    for cut in (5000, 12000, 21000):
        part = run(S[:cut])
        for i in range(cut):
            if (part[i]["dir"] != full[i]["dir"] or part[i]["box"] != full[i]["box"]
                    or part[i]["top"] != full[i]["top"]):
                print(f"  B FAIL at cut={cut} bar={i}")
                ok = False
                break
    print(f"B. FROZEN HISTORY        {'PASS' if ok else 'FAIL'} — "
          "adding later bars never alters an earlier bar")

    # --- A + C. DIFFERENT HISTORY LOAD -------------------------------------
    # Start the walk later, as if less history were loaded on the chart.
    print("\nA/C. DIFFERENT HISTORY LOAD (later start = less history loaded)")
    print(f"  {'start bar':>10} {'grid identical':>15} {'dir agrees':>12} "
          f"{'converged after':>16}")
    for start in (3000, 6000, 10000, 15000):
        late = run(S[start:])
        # compare only where BOTH have an established box
        pairs = [(full[start + i], late[i]) for i in range(len(late))
                 if full[start + i]["box"] and late[i]["box"]]
        grid_same = sum(1 for a, b in pairs
                        if a["box"] == b["box"] and a["top"] == b["top"])
        dir_same = sum(1 for a, b in pairs if a["dir"] == b["dir"])
        # first index after which direction agrees for the whole remainder
        conv = None
        for i in range(len(pairs)):
            if all(a["dir"] == b["dir"] for a, b in pairs[i:]):
                conv = i
                break
        print(f"  {start:>10} {grid_same}/{len(pairs):<14} "
              f"{dir_same}/{len(pairs):<11} {str(conv) + ' bars':>16}")


if __name__ == "__main__":
    main()
