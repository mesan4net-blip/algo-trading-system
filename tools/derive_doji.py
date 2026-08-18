# Adds the Doji / Rejection Candle exit to 3SHA_PriceAboveAll_v3.pine and
# switches order processing to the bar close. Targeted edits only - every
# anchor is asserted, nothing else in the file is touched.
import sys, io

P = 'V3_S.pine'
t = io.open(P, encoding='utf-8').read()

def sub(a, b, n=1):
    global t
    c = t.count(a)
    if c != n:
        sys.exit('ANCHOR FAIL (%d, want %d): %s' % (c, n, a[:80]))
    t = t.replace(a, b)

# ── 1. Fills land on the close of the bar that calls for them ───────────────
sub('calc_on_every_tick=false, process_orders_on_close=false, pyramiding=0,',
    'calc_on_every_tick=false, process_orders_on_close=true, pyramiding=0,')

# ── 2. Inputs, appended at the END of the Trade Management group ────────────
anchor_in = 'The STOP is deliberately exempt - blocking it would leave the entry candle unprotected, and a gap through the stop is exactly when protection matters most.", group=grp_mgmt)\n'
new_inputs = anchor_in + '''
use_doji_exit = input.bool(false, "Exit: Doji / Rejection Candle", tooltip="Close when the candle itself says the move has stopped - a small body (doji, spinning top) or a long rejection wick against the trade (inverted hammer, shooting star). Read on standard candles, so the chart type does not change the answer.\\n\\nDifferent from Give-Back, which rests as an order and cannot act until the bar AFTER the peak. A rejection candle makes its high and hands it back inside ONE bar, so give-back arrives too late for it. Exits at the close of the qualifying candle.", group=grp_mgmt)
dj_body_pct = input.float(25, "  Body Up To (% of candle range)", minval=0, maxval=100, step=5, tooltip="The candle qualifies when its body is this share of its high-to-low range or less. 25 means the body is a quarter of the candle or smaller. 0 = do not use this test.", group=grp_mgmt)
dj_wick_pct = input.float(60, "  Wick At Least (% of candle range)", minval=0, maxval=100, step=5, tooltip="The candle qualifies when the wick pointing AGAINST the trade is this share of its range or more - the upper wick in a buy, the lower wick in a sell. 0 = do not use this test.", group=grp_mgmt)
dj_need = input.int(1, "  Candles Required", minval=1, maxval=10, tooltip="How many qualifying candles IN A ROW before the trade closes. 1 exits on the first one. The count resets to zero on any candle that does not qualify, so candles scattered across a trade never add up.\\n\\nHigher numbers mean fewer false alarms and a later exit - by 3 you are two candles past the one that worried you.", group=grp_mgmt)
dj_min_size_pct = input.float(50, "  Minimum Candle Size (% of average range)", minval=0, step=5, tooltip="A candle worth nothing at all satisfies the body and wick tests purely from noise, because both are measured against the candle\\x27s own size. This requires the candle to be a real one first: its high-to-low range must be at least this share of the recent average. 0 = off, and this exit will then fire through every quiet patch.", group=grp_mgmt)
dj_avg_bars = input.int(14, "  Average Range (bars)", minval=1, maxval=200, tooltip="How many bars the average candle range is measured over. The current candle is excluded, so it is never measured partly against itself. High-to-low range rather than ATR: ATR includes the gap from the previous close, which would suppress a genuine rejection candle on the first bar after an overnight gap.", group=grp_mgmt)
'''
sub(anchor_in, new_inputs)

# ── 3. Counter, alongside the other per-trade state ─────────────────────────
sub('var float  peak_r      = 0.0   // best R reached, for the give-back exit',
    'var float  peak_r      = 0.0   // best R reached, for the give-back exit\n'
    'var int    dj_bars     = 0     // consecutive qualifying doji/rejection candles')

# ── 4. The candle test itself, global so ta.* runs every bar ────────────────
anchor_calc = 'trail_sw_high = _tsell_body ? (_tsell_hi ? trail_sw_high_body : trail_sw_low_body)  : (_tsell_hi ? trail_sw_high_wick : trail_sw_low_wick)\n'
calc = anchor_calc + '''
// ── DOJI / REJECTION CANDLE ─────────────────────────────────────────────────
// Two measurements rather than a list of pattern names, because no two
// platforms define a doji the same way and the thresholds are the part worth
// testing. Small body covers doji and spinning top; the wick test covers
// inverted hammer, shooting star and gravestone. Either one qualifies.
// The size gate applies to BOTH - a tiny candle with a proportionally long
// wick is noise wearing a costume.
_dj_rng  = rawH - rawL
_dj_body = math.abs(rawC - rawO)
// Previous N bars, excluding the current one, so a candle is never measured
// partly against itself.
_dj_avg  = ta.sma(_dj_rng, math.max(1, dj_avg_bars))[1]
dj_big_enough  = dj_min_size_pct <= 0 or (not na(_dj_avg) and _dj_avg > 0 and _dj_rng >= _dj_avg * dj_min_size_pct / 100.0)
_dj_body_small = dj_body_pct > 0 and _dj_rng > 0 and _dj_body <= _dj_rng * dj_body_pct / 100.0
_dj_wick_up    = dj_wick_pct > 0 and _dj_rng > 0 and (rawH - math.max(rawO, rawC)) >= _dj_rng * dj_wick_pct / 100.0
_dj_wick_dn    = dj_wick_pct > 0 and _dj_rng > 0 and (math.min(rawO, rawC) - rawL) >= _dj_rng * dj_wick_pct / 100.0
dj_qual_long  = use_doji_exit and dj_big_enough and (_dj_body_small or _dj_wick_up)
dj_qual_short = use_doji_exit and dj_big_enough and (_dj_body_small or _dj_wick_dn)
'''
sub(anchor_calc, calc)

# ── 5. Long side: count, and join the other close-based exits ───────────────
sub('    bad_bars := align_broken_long ? bad_bars + 1 : 0\n',
    '    bad_bars := align_broken_long ? bad_bars + 1 : 0\n'
    '    dj_bars := dj_qual_long ? dj_bars + 1 : 0\n')
sub('''    _cross_out = use_cross_exit and cross_dn
    _eod_out   = past_cutoff
    _other_out = _align_out or _sha_out or _time_out or _cross_out or _eod_out''',
    '''    _cross_out = use_cross_exit and cross_dn
    _eod_out   = past_cutoff
    _dj_out    = use_doji_exit and dj_bars >= dj_need
    _other_out = _align_out or _sha_out or _time_out or _cross_out or _eod_out or _dj_out''')

# ── 6. Short side, same two edits ───────────────────────────────────────────
sub('    bad_bars := align_broken_short ? bad_bars + 1 : 0\n',
    '    bad_bars := align_broken_short ? bad_bars + 1 : 0\n'
    '    dj_bars := dj_qual_short ? dj_bars + 1 : 0\n')
sub('''    _cross_out = use_cross_exit and cross_up
    _eod_out   = past_cutoff
    _other_out = _align_out or _sha_out or _time_out or _cross_out or _eod_out''',
    '''    _cross_out = use_cross_exit and cross_up
    _eod_out   = past_cutoff
    _dj_out    = use_doji_exit and dj_bars >= dj_need
    _other_out = _align_out or _sha_out or _time_out or _cross_out or _eod_out or _dj_out''')

# ── 7. Its own exit reason, both sides ──────────────────────────────────────
sub('_eod_out ? "Daily Cutoff" : "SHA Cross"',
    '_eod_out ? "Daily Cutoff" : _dj_out ? "Doji/Rejection" : "SHA Cross"', 2)

# ── 8. Reset the counter everywhere the other per-trade state resets ────────
sub('    bad_bars     := 0\n', '    bad_bars     := 0\n    dj_bars      := 0\n', 2)
sub('        bad_bars := 0\n', '        bad_bars := 0\n        dj_bars := 0\n', 2)

# ── 9. Diagnostics, same chain as the rest ──────────────────────────────────
anchor_dbg = 'plot(dbg ? dbg_stop_lvl : na, "dbg stop level", display=display.data_window)'
sub(anchor_dbg, anchor_dbg + '''
plot(dbg ? (_dj_rng > 0 ? _dj_body / _dj_rng * 100.0 : na) : na, "dbg body % of range", display=display.data_window)
plot(dbg ? (_dj_rng > 0 ? (rawH - math.max(rawO, rawC)) / _dj_rng * 100.0 : na) : na, "dbg upper wick % of range", display=display.data_window)
plot(dbg ? (_dj_rng > 0 ? (math.min(rawO, rawC) - rawL) / _dj_rng * 100.0 : na) : na, "dbg lower wick % of range", display=display.data_window)
plot(dbg ? (_dj_avg > 0 ? _dj_rng / _dj_avg * 100.0 : na) : na, "dbg candle size % of average", display=display.data_window)
plot(dbg ? (dj_big_enough ? 1 : 0) : na, "dbg size gate ok", display=display.data_window)
plot(dbg ? (dj_qual_long ? 1 : 0) : na, "dbg doji qualifies L", display=display.data_window)
plot(dbg ? (dj_qual_short ? 1 : 0) : na, "dbg doji qualifies S", display=display.data_window)
plot(dbg ? dj_bars : na, "dbg doji candles in a row", display=display.data_window)''')

io.open(P, 'w', encoding='utf-8').write(t)
print('written: %d lines' % (t.count('\n') + 1))
