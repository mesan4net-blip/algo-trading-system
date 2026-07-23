"""
test_plan.py — the single source of truth for what gets tested.

Every instrument is put through this identical grid, so results are comparable
across instruments instead of each one being hand-tuned.

Only genuine-SHA smoothing pairs are included: len1 >= 2 and len2 >= len1, so both
EMA passes actually smooth. (len1 = 1 disables the first pass entirely, which turns
the Smoothed Heikin-Ashi into a plain Heikin-Ashi -- a different indicator.)
"""

PLAN = {
    "sha": {
        "label": "Smoothing — chart + mid layer",
        "plain": "How much the chart and mid-timeframe trend layers are smoothed. Smaller reacts sooner but whipsaws more; larger is calmer but later.",
        "values": [(2, 4), (3, 6), (4, 8), (6, 11), (8, 16), (10, 20)],
        "fmt": lambda v: f"{v[0]},{v[1]}",
    },
    "htf2": {
        "label": "Smoothing — slow layer",
        "plain": "The slow filter that gates every trade. Swung separately because the chart and the slow layer often want different speeds.",
        "values": [(2, 2), (3, 6), (4, 8), (6, 11), (8, 16), (10, 20)],
        "fmt": lambda v: f"{v[0]},{v[1]}",
    },
    "exit": {
        "label": "Exit trigger (alignment break)",
        "plain": "Which timeframe turning against the trade closes it. Base is tightest, HTF2 loosest.",
        "values": ["Base", "HTF1", "HTF2"],
        "fmt": {"Base": "base flip", "HTF1": "HTF1 flip", "HTF2": "HTF2 flip"}.get,
    },
    "anchor": {
        "label": "Initial stop anchor",
        "plain": "What the stop is placed behind -- recent structure, or the mid/high timeframe trend body.",
        "values": ["Swing", "HTF1 Body", "HTF2 Body"],
        "fmt": str,
    },
    "basis": {
        "label": "Anchor basis",
        "plain": "Body uses the candle body edge (tighter). Wick uses the full high/low including the shadow (wider).",
        "values": ["Body", "Wick"],
        "fmt": str,
    },
    "stop_style": {
        "label": "Stop style",
        "plain": "Mental only triggers when a candle CLOSES beyond the stop. Hard is a real order that fires intra-bar and survives gaps.",
        "values": ["mental", "hard"],
        "fmt": str,
    },
    "risk": {
        "label": "Risk per trade",
        "plain": "Percent of the account risked from entry to stop. Scales return and drawdown together.",
        "values": [0.5, 1.0, 2.0],
        "fmt": lambda v: f"{v}%",
    },
}

FIXED = [
    ("Entry", "Full Alignment, Confirmed (1 bar) -- longs and shorts"),
    ("Break-even", "on -- stop moves to entry at +1R"),
    ("Trailing stop", "on -- swing/6 bars, same basis, starts at +1R, close-based"),
    ("Partial take-profit", "off"),
    ("Gap skip", "off"),
    ("Position sizing", "fractional, risk% of equity divided by the stop distance"),
    ("Leverage limit", "4x equity -- a position is never larger than that"),
    ("Stop buffer", "0.05% of median price (scale-relative, so it means the same on any instrument)"),
    ("Cost", "0.1% per round trip"),
    ("Validation", "full history + 5 equal time blocks; ranked on block consistency, not raw return"),
]

MIN_TRADES = 20   # a setting with fewer trades than this is not judged
BLOCKS = 5


def expand():
    """Yield every combination in the plan as a dict."""
    for sha in PLAN["sha"]["values"]:
        for h2 in PLAN["htf2"]["values"]:
            for ex in PLAN["exit"]["values"]:
                for an in PLAN["anchor"]["values"]:
                    for ba in PLAN["basis"]["values"]:
                        for st in PLAN["stop_style"]["values"]:
                            for rk in PLAN["risk"]["values"]:
                                yield dict(sha=sha, htf2=h2, exit=ex, anchor=an,
                                           basis=ba, stop_style=st, risk=rk)


def count():
    n = 1
    for k in PLAN:
        n *= len(PLAN[k]["values"])
    return n


def describe(c):
    return (f"{c['sha'][0]},{c['sha'][1]} · {c['htf2'][0]},{c['htf2'][1]} · {PLAN['exit']['fmt'](c['exit'])} · "
            f"{c['anchor']} · {c['basis']} · {c['stop_style']} · {c['risk']}%")


if __name__ == "__main__":
    print(f"{count()} combinations per strategy per instrument")
    for k, v in PLAN.items():
        vals = ", ".join(str(v["fmt"](x)) for x in v["values"])
        print(f"  {v['label']:32s} {vals}")
