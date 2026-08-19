# Rewrites the diagnostics chain in the v3 strategy so the script fits inside
# TradingView's 64-output limit. Nothing is thrown away - every buy/sell pair
# becomes one reading instead of two, and the four entry blockers become one.
# Run AFTER derive_doji.py, BEFORE derive_paa3_indicator.py.
import sys, io

P = 'V3_S.pine'
t = io.open(P, encoding='utf-8').read()

marker = 'plot(dbg ? (all_bull ? 1 : 0) : na, "dbg setup L", display=display.data_window)'
i = t.find(marker)
if i < 0:
    sys.exit('ANCHOR FAIL: diagnostics chain not found')

new = '''// SIDE CODES, used by every reading below that has a buy and a sell version:
//   0 = neither   1 = buy side   2 = sell side   3 = both
plot(dbg ? (all_bull ? 1 : 0) + (all_bear ? 2 : 0) : na, "dbg setup", display=display.data_window)
plot(dbg ? (pa_bull_raw ? 1 : 0) + (pa_bear_raw ? 2 : 0) : na, "dbg transition", display=display.data_window)
plot(dbg ? (brk_ok_long ? 1 : 0) + (brk_ok_short ? 2 : 0) : na, "dbg breakout", display=display.data_window)
plot(dbg ? _nb_hi_h : na, "dbg N-bar high", display=display.data_window)
plot(dbg ? _nb_lo_l : na, "dbg N-bar low", display=display.data_window)
plot(dbg ? (trg_dir == 1 ? 1 : trg_dir == -1 ? 2 : 0) : na, "dbg trigger", display=display.data_window)
plot(dbg ? (trg_dir == 0 or na(trg_bar) ? na : bar_index - trg_bar) : na, "dbg bars since trigger", display=display.data_window)
plot(dbg ? (trg_dir == 1 ? trg_h : trg_dir == -1 ? trg_l : na) : na, "dbg trigger level", display=display.data_window)
plot(dbg ? entry_level : na, "dbg entry level", display=display.data_window)
plot(dbg ? (trg_dir != 0 ? 1 : 0) : na, "dbg order resting", display=display.data_window)
// One reading instead of four. 0 = nothing blocking, and the number names the
// FIRST thing that is:  1 = date range   2 = gap   3 = daily cutoff
//                       4 = layer gap too small
plot(dbg ? (not in_date ? 1 : gap_block ? 2 : eod_entry_block ? 3 : gap_block_entry ? 4 : 0) : na, "dbg blocked by", display=display.data_window)
plot(dbg ? (long_signal ? 1 : 0) + (short_signal ? 2 : 0) : na, "dbg signal", display=display.data_window)
plot(dbg ? (pos_dir == "flat" ? 1 : 0) : na, "dbg flat", display=display.data_window)
plot(dbg ? dbg_stop_ok : na, "dbg stop ok", display=display.data_window)
plot(dbg ? dbg_stop_lvl : na, "dbg stop level", display=display.data_window)
plot(dbg ? (_dj_rng > 0 ? _dj_body / _dj_rng * 100.0 : na) : na, "dbg body % of range", display=display.data_window)
// The wick that matters is the one pointing against the trade - upper in a buy,
// lower in a sell. Flat, it shows whichever is longer.
plot(dbg ? (_dj_rng > 0 ? (pos_dir == "short" ? (math.min(rawO, rawC) - rawL) : pos_dir == "long" ? (rawH - math.max(rawO, rawC)) : math.max(rawH - math.max(rawO, rawC), math.min(rawO, rawC) - rawL)) / _dj_rng * 100.0 : na) : na, "dbg wick against trade %", display=display.data_window)
plot(dbg ? (not na(_dj_avg) and _dj_avg > 0 ? _dj_rng / _dj_avg * 100.0 : na) : na, "dbg candle size % of average", display=display.data_window)
plot(dbg ? (dj_qual_long ? 1 : 0) + (dj_qual_short ? 2 : 0) : na, "dbg doji qualifies", display=display.data_window)
plot(dbg ? (eng_qual_long ? 1 : 0) + (eng_qual_short ? 2 : 0) : na, "dbg engulfing qualifies", display=display.data_window)
plot(dbg ? dj_bars : na, "dbg doji candles in a row", display=display.data_window)
'''

t = t[:i] + new
io.open(P, 'w', encoding='utf-8').write(t)

n_plot = sum(1 for l in t.split('\n') if l.lstrip().startswith('plot('))
n_cand = sum(1 for l in t.split('\n') if l.lstrip().startswith('plotcandle('))
print('plot(): %d   plotcandle(): %d   outputs used: %d of 64' % (n_plot, n_cand, n_plot + n_cand * 9))
