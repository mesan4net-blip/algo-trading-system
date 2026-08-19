# Builds 3SHA_PriceAboveAll_Alerts_v3.pine FROM 3SHA_PriceAboveAll_v3.pine.
# Targeted replacements only, every anchor asserted. Everything not listed here
# is carried across unchanged, so the two files cannot drift apart on the
# signal, the levels, the stop, the trail or the exits - only on the small
# amount of order-filling code the indicator has to supply for itself.
import sys, io

src = io.open('V3_S.pine', encoding='utf-8').read()
t = src

def sub(a, b, n=1):
    global t
    c = t.count(a)
    if c != n:
        sys.exit('ANCHOR FAIL (%d, want %d): %s' % (c, n, a[:90]))
    t = t.replace(a, b)

# ── 1. Declaration ──────────────────────────────────────────────────────────
sub('''// TRADING COSTS: Pine requires these to be constants in the strategy() call, so
//   they cannot be script inputs. Set them below or override in the Properties
//   tab. They ship at zero — a zero-cost backtest is fine for reconciliation
//   against TradingView, but is not a tradeable result.''',
    '''// THIS IS THE INDICATOR HALF OF THE PAIR. It is built from the strategy by a
//   script, not typed out, so the two cannot drift apart. Same inputs, same
//   defaults, same levels, same exits — it just draws and alerts instead of
//   trading. Costs do not appear here because nothing is being counted.''')

sub('''strategy("3SHA Price Above All v3", shorttitle="3SHA-PAA3", overlay=true,
     initial_capital=100000, currency=currency.USD,
     default_qty_type=strategy.percent_of_equity, default_qty_value=10,
     calc_on_every_tick=false, process_orders_on_close=true, pyramiding=0,
     max_bars_back=5000, max_labels_count=500, max_lines_count=500,
     commission_type=strategy.commission.percent, commission_value=0.0,
     slippage=0)''',
    '''indicator("3SHA Price Above All v3 — Alerts", shorttitle="3SHA-PAA3-A", overlay=true,
     max_bars_back=5000, max_labels_count=500, max_lines_count=500)''')

# f_qty is never called in the strategy - size comes from the declaration - but
# it is carried across so the two files stay line-for-line comparable.
sub('    _eq   = strategy.equity',
    '    _eq   = 100000.0   // matches the strategy\'s starting capital; f_qty is unused in both')

# ── 2. The order-filling state ──────────────────────────────────────────────
sub("var int    dj_bars     = 0     // consecutive qualifying doji/rejection candles",
    '''var int    dj_bars     = 0     // consecutive qualifying doji/rejection candles

// ============================================================================
// ORDER FILLING  (this is the ONLY part the indicator does differently)
// ============================================================================
// The strategy hands its orders to TradingView and TradingView fills them. An
// indicator gets no such help, so the filling is written out below by hand. It
// has to match what TradingView does or the two halves will disagree:
//
//   - An order placed on a bar is tested against THAT bar's close first, then
//     left resting and tested against the whole of each later bar.
//   - A price reached inside a bar fills AT that price. A bar that OPENS
//     already past it fills at the open instead - that is the gap case, and
//     getting it wrong misprices every gap day.
//   - When one bar reaches both the stop and the target, the stop is taken.
//     That is the assumption TradingView makes, so it is the one made here.
//   - When an exit and an opposite entry are both waiting, the exit goes
//     first. Which one really came first is unknowable from bar data.
//
var float pend_lvl  = na     // the entry order waiting: its price
var bool  pend_long = false  // the entry order waiting: which way
var bool  pend_stop = false  // the entry order waiting: stop, or limit
var float rest_stop = na     // the stop waiting on an open trade
var float rest_tgt  = na     // the target waiting on an open trade
var int   em_pos    = 0      // 1 = in a buy, -1 = in a sell, 0 = flat
var int   em_e_bar  = na     // bar the open trade started on
var float em_e_px   = na     // price it actually filled at
var int   em_x_bar  = na     // bar the last trade ended on
var float em_x_px   = na     // price it ended at''')

# ── 3. Fill whatever was left waiting, before anything reads the position ───
sub('_setup_gone = (trg_dir == 1 and not all_bull) or (trg_dir == -1 and not all_bear)',
    '''// ── FILL THE ORDERS LEFT WAITING BY THE PREVIOUS BAR ───────────────────────
// This sits here, ahead of everything that reads the position, because that is
// where TradingView does it: orders are filled before the strategy's own code
// runs on the bar.
if em_pos != 0
    _x_stop = not na(rest_stop) and (em_pos > 0 ? rawL <= rest_stop : rawH >= rest_stop)
    _x_tgt  = not na(rest_tgt)  and (em_pos > 0 ? rawH >= rest_tgt  : rawL <= rest_tgt)
    if _x_stop or _x_tgt
        // At the level, unless the bar opened past it - then at the open.
        _sp = em_pos > 0 ? math.min(rest_stop, rawO) : math.max(rest_stop, rawO)
        _tp = em_pos > 0 ? math.max(rest_tgt,  rawO) : math.min(rest_tgt,  rawO)
        // Stop first when a single bar reaches both.
        em_x_px  := _x_stop ? _sp : _tp
        em_x_bar := bar_index
        em_pos   := 0
        rest_stop := na
        rest_tgt  := na

if not na(pend_lvl)
    _reached = pend_long ? (pend_stop ? rawH >= pend_lvl : rawL <= pend_lvl)
                         : (pend_stop ? rawL <= pend_lvl : rawH >= pend_lvl)
    if _reached
        // At the price, unless the bar opened past it - then at the open.
        _fill_px = pend_long ? (pend_stop ? math.max(pend_lvl, rawO) : math.min(pend_lvl, rawO))
                             : (pend_stop ? math.min(pend_lvl, rawO) : math.max(pend_lvl, rawO))
        if em_pos != 0
            // A flip: the old trade ends at the same price the new one starts.
            em_x_px  := _fill_px
            em_x_bar := bar_index
        em_e_px   := _fill_px
        em_e_bar  := bar_index
        em_pos    := pend_long ? 1 : -1
        pend_lvl  := na
        rest_stop := na
        rest_tgt  := na

_setup_gone = (trg_dir == 1 and not all_bull) or (trg_dir == -1 and not all_bear)''')

sub('_flat_now = strategy.position_size == 0', '_flat_now = em_pos == 0')

# ── 4. Read the position from the filling above instead of from the engine ──
sub('''// Pine's order engine is the single source of truth. v2 rests orders at the
// reference level and lets the engine fill them, so a parallel hand-kept copy
// of the position drifts a bar behind and produces phantom entries and double
// exits. Everything below is READ from the engine, never assumed.
_ps  = strategy.position_size
_ot  = strategy.opentrades''',
    '''// In the strategy these are read from Pine's order engine, which is the single
// source of truth there. Here they are read from the filling block above, which
// has already run for this bar - so everything below still READS the position
// rather than assuming it, and the rest of the file is unchanged.
_ps  = em_pos
_ot  = em_pos != 0 ? 1 : 0''')

sub('''_e_bar = _ot > 0 ? strategy.opentrades.entry_bar_index(_ot - 1) : na
_e_px  = _ot > 0 ? strategy.opentrades.entry_price(_ot - 1)     : na''',
    '''_e_bar = _ot > 0 ? em_e_bar : na
_e_px  = _ot > 0 ? em_e_px  : na''')

sub('''    _ct = strategy.closedtrades
    exit_no      := trade_no
    exit_from_px := lbl_entry_px
    exit_px      := _ct > 0 ? strategy.closedtrades.exit_price(_ct - 1)     : rawC
    exit_bar     := _ct > 0 ? strategy.closedtrades.exit_bar_index(_ct - 1) : bar_index''',
    '''    exit_no      := trade_no
    exit_from_px := lbl_entry_px
    exit_px      := not na(em_x_px)  ? em_x_px  : rawC
    exit_bar     := not na(em_x_bar) ? em_x_bar : bar_index''')

# ── 5. Partial take-profit: an alert, since there is no position to reduce ──
for side, word in (('L', 'BUY'), ('S', 'SELL')):
    sub('        strategy.close("PAA3-%s", qty_percent=tp1_pct, comment="TP1")' % side,
        '        alert("3SHA PAA v3 — %s: partial take-profit at " + str.tostring(rawC, format.mintick), alert.freq_once_per_bar_close)' % word)

# ── 6. Resting exit orders ──────────────────────────────────────────────────
for side in ('L', 'S'):
    sub('''    if (not na(_rest_lvl) or not na(_tgt_lvl)) and not _other_out
        strategy.exit("PAA3-stop", from_entry="PAA3-%s", stop=_rest_lvl, limit=_tgt_lvl)   // real intra-bar, gap-safe''' % side,
        '''    if (not na(_rest_lvl) or not na(_tgt_lvl)) and not _other_out
        rest_stop := _rest_lvl
        rest_tgt  := _tgt_lvl
    // No else. In the strategy, a bar that does not call strategy.exit leaves
    // the previous order sitting there - it is refreshed, never cancelled. The
    // levels are cleared in one place only: when a trade ends.''')

# ── 7. Closing at the bar close ─────────────────────────────────────────────
for side, word in (('L', 'BUY'), ('S', 'SELL')):
    pass
sub('''        strategy.close_all(comment = _why)''',
    '''        alert("3SHA PAA v3 — closed: " + _why + " at " + str.tostring(rawC, format.mintick), alert.freq_once_per_bar_close)
        em_x_px   := rawC
        em_x_bar  := bar_index
        em_pos    := 0
        rest_stop := na
        rest_tgt  := na''', 2)

# ── 8. Placing the entry order ──────────────────────────────────────────────
sub('''if long_signal and (pos_dir == "flat" or (use_flip and pos_dir == "short"))
    strategy.cancel("PAA3-S")
    if entry_confirm
        strategy.cancel("PAA3-L")
        if _cf_long
            strategy.entry("PAA3-L", strategy.long)
    else if _lvl_above_L
        strategy.entry("PAA3-L", strategy.long, stop=entry_level)
    else
        strategy.entry("PAA3-L", strategy.long, limit=entry_level)
else if short_signal and (pos_dir == "flat" or (use_flip and pos_dir == "long"))
    strategy.cancel("PAA3-L")
    if entry_confirm
        strategy.cancel("PAA3-S")
        if _cf_short
            strategy.entry("PAA3-S", strategy.short)
    else if _lvl_above_S
        strategy.entry("PAA3-S", strategy.short, limit=entry_level)
    else
        strategy.entry("PAA3-S", strategy.short, stop=entry_level)
else
    strategy.cancel("PAA3-L")
    strategy.cancel("PAA3-S")''',
    '''if long_signal and (pos_dir == "flat" or (use_flip and pos_dir == "short"))
    if entry_confirm
        // Nothing rests. The trade opens at THIS close, if the candle qualified.
        pend_lvl := na
        if _cf_long
            if em_pos != 0
                em_x_px  := rawC
                em_x_bar := bar_index
            em_e_px   := rawC
            em_e_bar  := bar_index
            em_pos    := 1
            rest_stop := na
            rest_tgt  := na
    else
        pend_lvl  := entry_level
        pend_long := true
        pend_stop := _lvl_above_L
else if short_signal and (pos_dir == "flat" or (use_flip and pos_dir == "long"))
    if entry_confirm
        pend_lvl := na
        if _cf_short
            if em_pos != 0
                em_x_px  := rawC
                em_x_bar := bar_index
            em_e_px   := rawC
            em_e_bar  := bar_index
            em_pos    := -1
            rest_stop := na
            rest_tgt  := na
    else
        pend_lvl  := entry_level
        pend_long := false
        pend_stop := not _lvl_above_S
else
    pend_lvl  := na

// ── ORDERS ARE TESTED AGAINST THIS BAR'S CLOSE TOO ─────────────────────────
// The strategy runs with process_orders_on_close on, so an order it places is
// checked once against the close of the bar that placed it before it is left
// to wait. Same here, and in the same place - after the rest of the bar's work,
// which is when TradingView does it.
if em_pos != 0
    _c_stop = not na(rest_stop) and (em_pos > 0 ? rawC <= rest_stop : rawC >= rest_stop)
    _c_tgt  = not na(rest_tgt)  and (em_pos > 0 ? rawC >= rest_tgt  : rawC <= rest_tgt)
    if _c_stop or _c_tgt
        em_x_px   := rawC
        em_x_bar  := bar_index
        em_pos    := 0
        rest_stop := na
        rest_tgt  := na

if not na(pend_lvl)
    _c_entry = pend_long ? (pend_stop ? rawC >= pend_lvl : rawC <= pend_lvl)
                         : (pend_stop ? rawC <= pend_lvl : rawC >= pend_lvl)
    if _c_entry
        if em_pos != 0
            em_x_px  := rawC
            em_x_bar := bar_index
        em_e_px   := rawC
        em_e_bar  := bar_index
        em_pos    := pend_long ? 1 : -1
        pend_lvl  := na
        rest_stop := na
        rest_tgt  := na''')

# ── 9. Alerts ───────────────────────────────────────────────────────────────
sub('''alertcondition(did_enter and pos_dir == "long",  "PAA Long Entry",  "3SHA Price Above All — LONG entry")
alertcondition(did_enter and pos_dir == "short", "PAA Short Entry", "3SHA Price Above All — SHORT entry")
alertcondition(did_exit, "PAA Exit", "3SHA Price Above All — position closed")''',
    '''// Two kinds, and the difference matters.
//
// The ORDER RESTING alerts fire the moment a setup produces a level, which is
// while there is still something to do about it - place the order and the
// broker does the waiting, exactly as the strategy does. The message carries
// the price and whether it is a stop or a limit.
//
// The ENTRY and EXIT alerts fire on the close of the bar the fill happened on.
// They confirm, they do not warn: a resting order fills part-way through a bar
// and no indicator can know that until the bar has closed. Trade the resting
// alerts; read the others.
alertcondition(did_enter and pos_dir == "long",  "PAA Long Entry",  "3SHA Price Above All — LONG entry filled")
alertcondition(did_enter and pos_dir == "short", "PAA Short Entry", "3SHA Price Above All — SHORT entry filled")
alertcondition(did_exit, "PAA Exit", "3SHA Price Above All — position closed")
alertcondition(not na(pend_lvl) and na(pend_lvl[1]) and pend_long,       "PAA Buy Order Resting",  "3SHA Price Above All — BUY order now resting")
alertcondition(not na(pend_lvl) and na(pend_lvl[1]) and not pend_long,   "PAA Sell Order Resting", "3SHA Price Above All — SELL order now resting")

_new_order = not na(pend_lvl) and (na(pend_lvl[1]) or pend_lvl != pend_lvl[1] or pend_long != pend_long[1])
if _new_order
    alert("3SHA PAA v3 — " + (pend_long ? "BUY" : "SELL") + " " + (pend_stop ? "stop" : "limit")
          + " resting at " + str.tostring(pend_lvl, format.mintick), alert.freq_once_per_bar_close)
if did_enter
    alert("3SHA PAA v3 — " + (pos_dir == "long" ? "BUY" : "SELL") + " filled at "
          + str.tostring(entry_price, format.mintick) + ", stop " + str.tostring(stop_level, format.mintick),
          alert.freq_once_per_bar_close)''')

# ── 10. Diagnostics for the order filling ──────────────────────────────────
sub('plot(dbg ? dj_bars : na, "dbg doji candles in a row", display=display.data_window)',
    '''plot(dbg ? dj_bars : na, "dbg doji candles in a row", display=display.data_window)

// ── ORDER FILLING ───────────────────────────────────────────────────────────
// Load this and the strategy on one chart with the same settings, open the Data
// Window and walk the bars. 'position' should match the strategy's Position
// Size on every bar and 'entry fill price' should match its entry price to the
// tick. Anywhere they differ is the filling code, and nothing else in the two
// files can cause it.
plot(dbg ? em_pos : na, "dbg position", display=display.data_window)
plot(dbg ? em_e_px : na, "dbg entry fill price", display=display.data_window)
plot(dbg ? em_x_px : na, "dbg last exit price", display=display.data_window)
plot(dbg ? pend_lvl : na, "dbg order waiting at", display=display.data_window)
// 0 = nothing waiting  1 = buy stop  2 = buy limit  3 = sell stop  4 = sell limit
plot(dbg ? (na(pend_lvl) ? 0 : pend_long ? (pend_stop ? 1 : 2) : (pend_stop ? 3 : 4)) : na, "dbg order type", display=display.data_window)
plot(dbg ? rest_stop : na, "dbg stop waiting at", display=display.data_window)
plot(dbg ? rest_tgt : na, "dbg target waiting at", display=display.data_window)''')

io.open('V3_I.pine', 'w', encoding='utf-8').write(t)

# Report how much of the file is untouched.
import difflib
a, b = src.splitlines(), t.splitlines()
same = sum(bl.size for bl in difflib.SequenceMatcher(None, a, b).get_matching_blocks())
print('strategy %d lines -> indicator %d lines' % (len(a), len(b)))
print('lines carried across unchanged: %d of %d (%.1f%%)' % (same, len(a), 100.0 * same / len(a)))
print('no strategy.* left:', 'strategy.' not in t.replace('the strategy.', ''))
