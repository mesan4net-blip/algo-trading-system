# Fixes two ways the trail and break-even could stop working with no sign, and
# adds the readings that would have shown it. Run AFTER derive_candle_exits.py,
# BEFORE derive_dbg_compact.py.
import sys, io

P = 'V3_S.pine'
t = io.open(P, encoding='utf-8').read()

def sub(a, b, n=1):
    global t
    c = t.count(a)
    if c != n:
        sys.exit('ANCHOR FAIL (%d, want %d): %s' % (c, n, a[:90]))
    t = t.replace(a, b)

# ── 1. An unavailable trail anchor falls back to the swing ──────────────────
sub('''trail_low_ref  = trail_low_anchor  - trail_buffer_raw
trail_high_ref = trail_high_anchor + trail_buffer_raw''',
'''// An anchor can come back with nothing - the eligible-SHA choices have nothing
// to point at when no layer qualifies. The comparison that ratchets the stop
// then quietly fails and the trail never moves again for the life of the trade,
// with no error and nothing on the chart to show it. Falling back to the swing
// keeps the trail working; going silent is the one thing it must not do.
trail_low_anchor_ok  = not na(trail_low_anchor)
trail_high_anchor_ok = not na(trail_high_anchor)
_tla = trail_low_anchor_ok  ? trail_low_anchor  : trail_sw_low
_tha = trail_high_anchor_ok ? trail_high_anchor : trail_sw_high
trail_low_ref  = _tla - trail_buffer_raw
trail_high_ref = _tha + trail_buffer_raw''')

# ── 2. R is measurable, and says so when it cannot be worked out ────────────
# _rr silently became 0 whenever risk_unit or entry_price was unusable, which
# switches off break-even, the trail, partial take-profit, give-back, the target
# and the time stop all at once. Now it is na, and na is visible.
for side, cmp in (('long', 'rawC - entry_price'), ('short', 'entry_price - rawC')):
    sub('    _rr = risk_unit > 0 ? (%s) / risk_unit : 0.0' % cmp,
        '    _rr = risk_unit > 0 and not na(entry_price) ? (%s) / risk_unit : na\n'
        '    dbg_rr := _rr' % cmp)

# na fails every >= test on its own, but say so rather than relying on it.
for a, b in (('if use_tp1 and not tp1_taken and _rr >= tp1_r',
              'if use_tp1 and not tp1_taken and not na(_rr) and _rr >= tp1_r'),
             ('if use_be and not be_moved and _rr >= be_trig_r',
              'if use_be and not be_moved and not na(_rr) and _rr >= be_trig_r'),
             ('if use_trail and _rr >= trail_start_r',
              'if use_trail and not na(_rr) and _rr >= trail_start_r')):
    sub(a, b, 2)

sub('_time_stop_rr_guard_placeholder', '_time_stop_rr_guard_placeholder', 0) if False else None
for a in ('and _rr < time_stop_min_r',):
    sub(a, 'and (na(_rr) or _rr < time_stop_min_r)', 2)

# ── 3. State worth seeing, declared next to the other diagnostics ───────────
sub('''var float dbg_stop_lvl = na
var float dbg_stop_ok  = na''',
'''var float dbg_stop_lvl = na
var float dbg_stop_ok  = na
var float dbg_rr       = na   // R right now. na means it cannot be worked out,
                              // which switches off every R-based mechanism -
                              // that used to happen silently.''')

io.open(P, 'w', encoding='utf-8').write(t)
print('written: %d lines' % (t.count('\n') + 1))
