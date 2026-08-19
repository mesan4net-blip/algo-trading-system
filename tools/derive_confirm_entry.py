# Adds "Confirm Entry At Candle Close" - the trade opens at the close of the
# first candle that both reaches the level AND closes with the trade, instead of
# filling the instant price touches the level.
# Run AFTER derive_trigger_dir.py, BEFORE derive_dbg_compact.py.
import sys, io

P = 'V3_S.pine'
t = io.open(P, encoding='utf-8').read()

def sub(a, b, n=1):
    global t
    c = t.count(a)
    if c != n:
        sys.exit('ANCHOR FAIL (%d, want %d): %s' % (c, n, a[:90]))
    t = t.replace(a, b)

# ── 1. Input, appended at the END of the entry group ────────────────────────
anchor = 'min_layer_gap_pct = input.float(0.0, "Minimum Layer Gap (%)"'
line_end = t.index('\n', t.index(anchor))
t = t[:line_end + 1] + '''entry_confirm = input.bool(false, "Confirm Entry At Candle Close", tooltip="OFF: the order rests at the level and fills the moment price touches it, part-way through a candle. Nobody can know what colour that candle will be, so a sell can open on a candle that goes on to close green.\\n\\nON: no order rests. The trade opens at the CLOSE of the first candle that both reaches the level AND closes with the trade - a buy needs a candle closing up, a sell one closing down. A sell can then never open on an up candle, because the candle has finished by the time the trade exists.\\n\\nThe cost is the fill price, and it cuts both ways. On a candle that dips to the level and recovers, the close is a BETTER price than the level. On a candle that reaches the level and keeps running, it is a much worse one. And some trades are missed entirely: price reaches the level, closes against the trade, and never comes back.\\n\\nThe trigger candle itself can never fill - the level is taken FROM that candle, so it would enter at once and the level would mean nothing.", group=grp_entry)
''' + t[line_end + 1:]

# ── 2. The test, and both routes into a trade ───────────────────────────────
sub('''if long_signal and (pos_dir == "flat" or (use_flip and pos_dir == "short"))
    strategy.cancel("PAA3-S")
    if _lvl_above_L
        strategy.entry("PAA3-L", strategy.long, stop=entry_level)
    else
        strategy.entry("PAA3-L", strategy.long, limit=entry_level)
else if short_signal and (pos_dir == "flat" or (use_flip and pos_dir == "long"))
    strategy.cancel("PAA3-L")
    if _lvl_above_S
        strategy.entry("PAA3-S", strategy.short, limit=entry_level)
    else
        strategy.entry("PAA3-S", strategy.short, stop=entry_level)
else
    strategy.cancel("PAA3-L")
    strategy.cancel("PAA3-S")''',
'''// ── CONFIRM-AT-CLOSE TEST ───────────────────────────────────────────────────
// Never on the trigger candle: the level is taken FROM that candle, so its own
// high or low reaches it by definition and the trade would open immediately at
// the trigger close, making the reference level meaningless.
// Above or below is judged against the PREVIOUS close - where price sat when
// the candle began - which is the same question a resting order asks.
_cf_live  = entry_confirm and trg_dir != 0 and not na(entry_level) and not na(trg_bar) and bar_index > trg_bar
_cf_above = _cf_live and entry_level > rawC[1]
_cf_reach = _cf_live and (_cf_above ? rawH >= entry_level : rawL <= entry_level)
_cf_long  = _cf_reach and rawC >= rawO
_cf_short = _cf_reach and rawC <= rawO

if long_signal and (pos_dir == "flat" or (use_flip and pos_dir == "short"))
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
    strategy.cancel("PAA3-S")''')

io.open(P, 'w', encoding='utf-8').write(t)
print('written: %d lines' % (t.count('\n') + 1))
