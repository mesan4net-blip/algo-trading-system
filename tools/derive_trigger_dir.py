# A trigger candle may not close against the trade it is starting.
# Run AFTER derive_trail_fix.py, BEFORE derive_dbg_compact.py.
import sys, io
P='V3_S.pine'; t=io.open(P,encoding='utf-8').read()
def sub(a,b,n=1):
    global t
    c=t.count(a)
    if c!=n: sys.exit('ANCHOR FAIL (%d, want %d): %s'%(c,n,a[:90]))
    t=t.replace(a,b)

sub('''var int   trg_dir = 0        // 1 long, -1 short, 0 none''',
'''// A trigger candle may not close AGAINST the trade it is starting. A red candle
// closing above all three layers is price falling while it happens to still be
// above them - that is not evidence of a push, and with Buy Reference = High the
// order would then rest above a falling candle's high. A flat candle, close
// equal to open, still counts: it is not against the trade.
// Real candles, not SHA - this is the candle on the chart.
trg_dir_ok_long  = rawC >= rawO
trg_dir_ok_short = rawC <= rawO

var int   trg_dir = 0        // 1 long, -1 short, 0 none''')

sub('if _flat_now and trg_dir == 0 and all_bull and brk_ok_long and allow_longs',
    'if _flat_now and trg_dir == 0 and all_bull and brk_ok_long and trg_dir_ok_long and allow_longs')
sub('else if _flat_now and trg_dir == 0 and all_bear and brk_ok_short and allow_shorts',
    'else if _flat_now and trg_dir == 0 and all_bear and brk_ok_short and trg_dir_ok_short and allow_shorts')

io.open(P,'w',encoding='utf-8').write(t)
print('written: %d lines'%(t.count('\n')+1))
