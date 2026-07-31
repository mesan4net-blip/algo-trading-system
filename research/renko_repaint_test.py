#!/usr/bin/env python3
"""
renko_repaint_test.py — properties the PAAR renko engine must hold.

The Pine engine is ported here so the claims made about it can be checked
rather than asserted. Four properties:

  A. TIMEFRAME-PROOF BRICKS — the pinned feed means the chart timeframe cannot
     change the bricks, not merely their size. This is the one that failed
     before the feed was pinned: 344 bricks on 1m data against 214 on 4h.
  B. FROZEN HISTORY        — state at bar N never changes as later bars arrive.
  C. GATE NEVER LOOSENS    — less history can only ever be more conservative.
  D. BOX MODES             — Derived, Fixed and Percent behave as specified.
"""

import math
import random
import statistics
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Engine — mirrors the Pine block in 3SHA_PriceAboveAll_Renko_v1.pine
# ---------------------------------------------------------------------------
class Renko:
    def __init__(self, box_mode="Derived", box_fixed=0.0020, box_pct=0.25,
                 avg_type="Median", mult=1.0, round_step=0.0001, min_box=0.0,
                 max_box=0.0, rev=2, confirm=1, trigger="Close"):
        self.box_mode, self.box_fixed, self.box_pct = box_mode, box_fixed, box_pct
        self.avg_type, self.mult = avg_type, mult
        self.round_step, self.min_box, self.max_box = round_step, min_box, max_box
        self.rev, self.confirm, self.trigger = rev, confirm, trigger
        self.box = None
        self.top = self.bot = None
        self.dir = 0
        self.run = 0
        self.bricks = 0

    def _size(self, mean, med, ref):
        if self.box_mode == "Fixed":
            raw = self.box_fixed
        elif self.box_mode == "Percent Of Price":
            raw = None if ref is None else ref * self.box_pct / 100.0
        else:
            a = med if self.avg_type == "Median" else mean
            raw = None if a is None else a * self.mult
        if raw is None or raw <= 0:
            return None
        step = self.round_step if self.round_step > 0 else 0.0
        val = round(raw / step) * step if step > 0 else raw
        floor_v = self.min_box if self.min_box > 0 else (step if step > 0 else 0.0)
        val = max(val, floor_v)
        return min(val, self.max_box) if self.max_box > 0 else val

    def bar(self, feed, sizing):
        """feed: list of (h,l,c) for this chart bar. sizing: (mean,med,ref)."""
        calc = self._size(*sizing)
        box_new = calc is not None and (self.box is None or calc != self.box)
        if box_new:
            self.box = calc
            seed = feed[0][2] if feed else None      # FIRST feed bar, not last
            if seed is not None:
                self.bot = math.floor(seed / self.box) * self.box
                self.top = self.bot + self.box

        if self.box is None or self.top is None:
            return []

        # Return the direction of EVERY brick as it prints. Returning a count
        # and stamping them all with the bar's final direction loses the order
        # inside a bar, which is exactly what a slow chart bar contains most of.
        printed = []
        for h, l, c in feed:
            up = h if self.trigger == "Wick" else c
            dn = l if self.trigger == "Wick" else c
            for _ in range(200):
                p = False
                if self.dir == 1:
                    if up >= self.top + self.box:
                        self.bot = self.top
                        self.top += self.box
                        self.run += 1
                        p = True
                    elif dn <= self.top - self.rev * self.box:
                        self.top = self.top - (self.rev - 1) * self.box
                        self.bot = self.top - self.box
                        self.dir, self.run = -1, 1
                        p = True
                elif self.dir == -1:
                    if dn <= self.bot - self.box:
                        self.top = self.bot
                        self.bot -= self.box
                        self.run += 1
                        p = True
                    elif up >= self.bot + self.rev * self.box:
                        self.bot = self.bot + (self.rev - 1) * self.box
                        self.top = self.bot + self.box
                        self.dir, self.run = 1, 1
                        p = True
                else:
                    if up >= self.top + self.box:
                        self.bot = self.top
                        self.top += self.box
                        self.dir, self.run = 1, 1
                        p = True
                    elif dn <= self.bot - self.box:
                        self.top = self.bot
                        self.bot -= self.box
                        self.dir, self.run = -1, 1
                        p = True
                if not p:
                    break
                printed.append(self.dir)
        self.bricks += len(printed)
        return printed


# ---------------------------------------------------------------------------
def make_1m(n=200000, seed=7):
    rnd = random.Random(seed)
    t, px, vol = datetime(2024, 1, 1), 1.0850, 0.00009
    out = []
    for _ in range(n):
        vol *= math.exp(rnd.gauss(0, 0.002))
        vol = min(max(vol, 0.00004), 0.0003)
        px *= math.exp(rnd.gauss(0, vol))
        out.append((t, px * (1 + abs(rnd.gauss(0, vol * .6))),
                    px * (1 - abs(rnd.gauss(0, vol * .6))), px))
        t += timedelta(minutes=1)
    return out


def agg(series, n):
    out = []
    for i in range(0, len(series) - n + 1, n):
        c = series[i:i + n]
        out.append((c[0][0], max(b[1] for b in c),
                    min(b[2] for b in c), c[-1][3]))
    return out


def sizing_series(series, size_min, reset="M"):
    """Mirror of f_rk_size: mean, median and reference close, frozen per period."""
    bars = agg(series, size_min)
    key = (lambda d: (d.year, d.month)) if reset == "M" else \
          (lambda d: d.isocalendar()[:2]) if reset == "W" else \
          (lambda d: (d.year, d.month, d.day))
    out, buf, held, prev, prev_c = {}, [], (None, None, None), None, None
    for tm, h, l, c in bars:
        k = key(tm.date())
        if prev is not None and k != prev and buf:
            held = (sum(buf) / len(buf), statistics.median(buf), prev_c)
            buf = []
        buf.append(h - l)
        prev, prev_c = k, c
        out[tm] = held
    return out


def chart_bars(feed, per):
    # Include the trailing partial group. Dropping it silently gave a slow chart
    # fewer feed bars than a fast one and looked like an engine fault.
    return [feed[i:i + per] for i in range(0, len(feed), per)]


# ---------------------------------------------------------------------------
def main():
    S = make_1m()
    feed = agg(S, 5)
    SZ = sizing_series(S, 30, "M")
    keys = sorted(SZ)

    def sizing_for(ts):
        lo, hi, best = 0, len(keys) - 1, None
        while lo <= hi:
            mid = (lo + hi) // 2
            if keys[mid] <= ts:
                best = keys[mid]
                lo = mid + 1
            else:
                hi = mid - 1
        return SZ[best] if best else (None, None, None)

    print(f"1m base: {len(S)} bars, {S[0][0].date()} -> {S[-1][0].date()}")
    print(f"feed: 5m, {len(feed)} bars\n")

    def walk(fb, per, **kw):
        r = Renko(**kw)
        seq, st = [], []
        for grp in chart_bars(fb, per):
            seq.extend(r.bar([(h, l, c) for _, h, l, c in grp],
                             sizing_for(grp[-1][0])))
            st.append((r.dir, r.run, r.box, r.top))
        return seq, st, r

    # --- A -----------------------------------------------------------------
    print("A. TIMEFRAME-PROOF BRICKS")
    base, _, _ = walk(feed, 1)
    ok_a = True
    for name, per in [("5m", 1), ("15m", 3), ("1h", 12), ("4h", 48), ("1D", 288)]:
        sq, _, _ = walk(feed, per)
        m = min(len(sq), len(base))
        same = sum(1 for i in range(m) if sq[i] == base[i])
        match = len(sq) == len(base) and same == m
        ok_a &= match
        print(f"   {name:>4} chart  {len(sq):>5} bricks  "
              f"{same}/{m} identical  {'ok' if match else 'DIFFERS'}")
    print(f"   -> {'PASS' if ok_a else 'FAIL'}\n")

    # --- B -----------------------------------------------------------------
    _, full, _ = walk(feed, 3)
    ok_b = True
    for cut in (4000, 9000, 15000):
        _, part, _ = walk(feed[:cut * 3], 3)
        for i in range(min(len(part), cut)):
            if part[i] != full[i]:
                print(f"   B FAIL at cut={cut} bar={i}")
                ok_b = False
                break
    print(f"B. FROZEN HISTORY          {'PASS' if ok_b else 'FAIL'}\n")

    # --- C -----------------------------------------------------------------
    worse = 0
    for start in (3000, 8000, 14000):
        _, late, _ = walk(feed[start * 3:], 3)
        for i in range(len(late)):
            f, l = full[start + i], late[i]
            if (l[0] == 1 and f[0] != 1) or (l[0] == -1 and f[0] != -1):
                worse += 1
    print(f"C. GATE NEVER LOOSENS      {'PASS' if worse == 0 else 'FAIL'} "
          f"({worse} cases where less history permitted what full history blocked)\n")

    # --- D -----------------------------------------------------------------
    print("D. BOX MODES")
    for label, kw in [("Derived/Median", {}),
                      ("Derived/Mean", {"avg_type": "Mean"}),
                      ("Fixed 20 pip", {"box_mode": "Fixed"}),
                      ("Percent 0.25%", {"box_mode": "Percent Of Price"}),
                      ("Wick trigger", {"trigger": "Wick"}),
                      ("Ceiling 0.0015", {"max_box": 0.0015})]:
        _, st, r = walk(feed, 3, **kw)
        b = sorted({round(s[2], 5) for s in st if s[2]})
        print(f"   {label:<16} {r.bricks:>6} bricks   {len(b)} distinct   "
              f"{min(b):.4f} - {max(b):.4f}" if b else f"   {label:<16} no box")


if __name__ == "__main__":
    main()
