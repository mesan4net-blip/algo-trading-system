# Two changes to the candle exits in the v3 strategy.
#
#   1. A candle only counts as a stall if the wick AGAINST the trade is the
#      dominant one. Stops a hammer closing a buy.
#   2. Engulfing against the trade, as its own toggle.
#
# Run AFTER derive_doji.py, BEFORE derive_dbg_compact.py.
import sys, io

P = 'V3_S.pine'
t = io.open(P, encoding='utf-8').read()

def sub(a, b, n=1):
    global t
    c = t.count(a)
    if c != n:
        sys.exit('ANCHOR FAIL (%d, want %d): %s' % (c, n, a[:90]))
    t = t.replace(a, b)

# ── 1. New input, appended after the last doji input ────────────────────────
anchor = 'dj_avg_bars = input.int(14, "  Average Range (bars)"'
line_end = t.index('\n', t.index(anchor))
t = t[:line_end + 1] + '''use_engulf_exit = input.bool(false, "Exit: Engulfing Candle Against The Trade", tooltip="Close when a candle both reverses and swallows the one before it - a down candle whose body covers the previous up candle\\x27s body, in a buy, and the mirror in a sell.\\n\\nThis is the OPPOSITE shape to the two tests above, which both need a small body. A decisive reversal is a big body with little wick, and it slips past both of them. That is the gap this fills.\\n\\nExits on its own, immediately - it does not go through Candles Required, since two engulfing candles in a row is close to a contradiction. It does use the Minimum Candle Size gate above.\\n\\nWorth running on its own first: a candle big enough to engulf will often break the Base SHA layer on the same bar, in which case it is not earning anything the SHA exit was not already doing.", group=grp_mgmt)
''' + t[line_end + 1:]

# ── 2. Wick direction, and the engulfing test ───────────────────────────────
sub('''_dj_body_small = dj_body_pct > 0 and _dj_rng > 0 and _dj_body <= _dj_rng * dj_body_pct / 100.0
_dj_wick_up    = dj_wick_pct > 0 and _dj_rng > 0 and (rawH - math.max(rawO, rawC)) >= _dj_rng * dj_wick_pct / 100.0
_dj_wick_dn    = dj_wick_pct > 0 and _dj_rng > 0 and (math.min(rawO, rawC) - rawL) >= _dj_rng * dj_wick_pct / 100.0
dj_qual_long  = use_doji_exit and dj_big_enough and (_dj_body_small or _dj_wick_up)
dj_qual_short = use_doji_exit and dj_big_enough and (_dj_body_small or _dj_wick_dn)''',
'''_dj_up_wick    = rawH - math.max(rawO, rawC)
_dj_dn_wick    = math.min(rawO, rawC) - rawL
_dj_body_small = dj_body_pct > 0 and _dj_rng > 0 and _dj_body <= _dj_rng * dj_body_pct / 100.0
_dj_wick_up    = dj_wick_pct > 0 and _dj_rng > 0 and _dj_up_wick >= _dj_rng * dj_wick_pct / 100.0
_dj_wick_dn    = dj_wick_pct > 0 and _dj_rng > 0 and _dj_dn_wick >= _dj_rng * dj_wick_pct / 100.0
// The wick pointing AGAINST the trade has to be the dominant one. A hammer in a
// buy - small body, long tail underneath - is buyers stepping in at the low,
// which is support, not a stall, and it should not close the trade. Without
// this the small-body test flags it anyway, because that test does not look at
// which side the tail is on. A true doji has wicks of roughly equal length and
// still qualifies both ways, which is right: a genuine stall is two-sided.
_dj_against_long  = _dj_up_wick >= _dj_dn_wick
_dj_against_short = _dj_dn_wick >= _dj_up_wick
// The SHAPE, on its own. Kept separate from the exit toggle so the same test can
// be asked at entry without switching the exit on.
dj_shape_long  = dj_big_enough and _dj_against_long  and (_dj_body_small or _dj_wick_up)
dj_shape_short = dj_big_enough and _dj_against_short and (_dj_body_small or _dj_wick_dn)
dj_qual_long  = use_doji_exit and dj_shape_long
dj_qual_short = use_doji_exit and dj_shape_short

// ── ENGULFING AGAINST THE TRADE ─────────────────────────────────────────────
// Body swallows the previous body, and turns the other way. The two tests above
// both need a SMALL body, so the most convincing reversal candle on the chart -
// a big body, little wick - passes them untouched. This catches that one.
// Bodies only. Wicks are ignored, which is the common definition and the one
// that does not fall apart on gaps.
_en_up      = rawC > rawO
_en_dn      = rawC < rawO
_en_up_prev = rawC[1] > rawO[1]
_en_dn_prev = rawC[1] < rawO[1]
eng_qual_long  = use_engulf_exit and dj_big_enough and _en_dn and _en_up_prev and rawO >= rawC[1] and rawC <= rawO[1]
eng_qual_short = use_engulf_exit and dj_big_enough and _en_up and _en_dn_prev and rawO <= rawC[1] and rawC >= rawO[1]''')

# ── 3. Wire it into both sides ──────────────────────────────────────────────
for side, qual in (('long', 'eng_qual_long'), ('short', 'eng_qual_short')):
    old = '''    _dj_out    = use_doji_exit and dj_bars >= dj_need
    _other_out = _align_out or _sha_out or _time_out or _cross_out or _eod_out or _dj_out'''
    new = '''    _dj_out    = use_doji_exit and dj_bars >= dj_need
    _eng_out   = %s
    _other_out = _align_out or _sha_out or _time_out or _cross_out or _eod_out or _dj_out or _eng_out''' % qual
    if t.count(old) != (2 if side == 'long' else 1):
        sys.exit('ANCHOR FAIL on the %s side' % side)
    i = t.index(old)          # long first, then what is left is the short side
    t = t[:i] + new + t[i + len(old):]

sub('_dj_out ? "Doji/Rejection" : "SHA Cross"',
    '_dj_out ? "Doji/Rejection" : _eng_out ? "Engulfing" : "SHA Cross"', 2)

io.open(P, 'w', encoding='utf-8').write(t)
print('written: %d lines' % (t.count('\n') + 1))
