# A doji or rejection candle cannot start a trade. Same two measurements as the
# exit - small body, or a wick against the trade - asked at the front instead of
# the back. Run AFTER derive_confirm_entry.py, BEFORE derive_dbg_compact.py.
import sys, io
P='V3_S.pine'; t=io.open(P,encoding='utf-8').read()
def sub(a,b,n=1):
    global t
    c=t.count(a)
    if c!=n: sys.exit('ANCHOR FAIL (%d, want %d): %s'%(c,n,a[:90]))
    t=t.replace(a,b)

# Input, appended at the END of the entry group
anchor='entry_confirm = input.bool(false, "Confirm Entry At Candle Close"'
le=t.index('\n', t.index(anchor))
t=t[:le+1]+'''block_doji_entry = input.bool(false, "Block Doji / Rejection Candles", tooltip="A candle that says nobody is in control should not be the candle a trade starts on. An inverted hammer in a BUY - small body, long wick above - is a failed push, and buying it means buying the failure.\\n\\nSame two measurements as the exit: a small body, or a wick pointing AGAINST the trade, with the wick against having to be the dominant one. It uses the SAME thresholds, set in \\u2465 Trade Management under Exit: Doji / Rejection Candle - Body Up To, Wick At Least and Minimum Candle Size. Those apply here whether or not that exit is switched on.\\n\\nIt blocks BOTH the trigger candle and, with Confirm Entry At Candle Close on, the candle the trade opens on.", group=grp_entry)
'''+t[le+1:]

# The trigger candle
sub('and brk_ok_long and trg_dir_ok_long and allow_longs',
    'and brk_ok_long and trg_dir_ok_long and not (block_doji_entry and dj_shape_long) and allow_longs')
sub('and brk_ok_short and trg_dir_ok_short and allow_shorts',
    'and brk_ok_short and trg_dir_ok_short and not (block_doji_entry and dj_shape_short) and allow_shorts')

# The candle the trade opens on, when confirming at the close
sub('_cf_long  = _cf_reach and rawC >= rawO',
    '_cf_long  = _cf_reach and rawC >= rawO and not (block_doji_entry and dj_shape_long)')
sub('_cf_short = _cf_reach and rawC <= rawO',
    '_cf_short = _cf_reach and rawC <= rawO and not (block_doji_entry and dj_shape_short)')

io.open(P,'w',encoding='utf-8').write(t)
print('written: %d lines'%(t.count('\n')+1))
