"""
runner.py — run the full test plan on one instrument.

Ranking is by ROBUSTNESS, not raw return: a setting must stay positive across
independent time blocks to be called a keeper. A high return that only works in
one block ranks below a modest return that works in four.
"""
import os, json, warnings
import numpy as np, pandas as pd
warnings.filterwarnings('ignore')

from fa_engine import precompute, backtest_fast as backtest, metrics_fast as metrics, default_cfg

# Realistic round-trip cost by market type (spread + commission + slippage).
# Crypto spot is an order of magnitude dearer than a major currency pair or a
# large ETF, so a single blanket figure would flatter one and punish another.
COST = {'BTCUSDT': 0.0020,   # 0.10% per side, Binance spot taker
        'EURUSD':  0.0002,   # ~0.5-1 pip on a major
        'QQQ':     0.0002,   # penny spread on a ~$500 ETF, plus commission
        'SPY':     0.0002}
DEFAULT_COST = 0.0005
import test_plan as TP

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, "data")

TF_DUR = {'1D': pd.Timedelta('1D'), '1W': pd.Timedelta('7D'),
          '4h': pd.Timedelta('4h'), '1h': pd.Timedelta('1h')}


def load(path):
    d = pd.read_csv(path)
    d.columns = ['time', 'open', 'high', 'low', 'close'] + list(d.columns[5:])
    d['t'] = pd.to_datetime(d['time'], utc=True).dt.as_unit('ns')
    return d.set_index('t')[['open', 'high', 'low', 'close']]


EXIT_MAP = {
 'Base':          dict(align_level='Base'),
 'HTF1':          dict(align_level='HTF1'),
 'HTF2':          dict(align_level='HTF2'),
 'All':           dict(align_level='All'),
 'Base x2':       dict(align_level='Base', align_confirm_bars=2),
 'SHA break':     dict(use_align_exit=False, use_sha_break=True, sha_break_layer='HTF1'),
 'Target 2R':     dict(use_align_exit=False, use_target=True, target_r=2.0),
 'Target 3R':     dict(use_align_exit=False, use_target=True, target_r=3.0),
 'Give-back 40%': dict(use_align_exit=False, use_giveback=True, giveback_pct=40.0),
 'Time 30':       dict(use_align_exit=False, use_time_stop=True, time_stop_bars=30),
}


def cfg_from(combo, buf):
    c = default_cfg()
    c.update(base_sha=combo['sha'], htf1_sha=combo['sha'], htf2_sha=combo['htf2'],
             sl_mode=combo['anchor'],
             sl_basis=combo['basis'], trail_basis=combo['basis'],
             use_hard_stop=(combo['stop_style'] == 'hard'),
             risk_pct=1.0, max_equity_pct=400.0,
             sl_buffer=buf, trail_buffer=buf)
    c.update(EXIT_MAP[combo['exit']])
    t = combo['trail']
    if t == 'off':
        c['use_trail'] = False
    elif t.startswith('Swing'):
        c.update(use_trail=True, trail_mode='Swing', trail_lookback=int(t.split()[1]))
    else:
        c.update(use_trail=True, trail_mode=t)
    return c


def verdict(blocks_pos, retdd, trades):
    if trades < TP.MIN_TRADES:
        return "thin"
    if blocks_pos >= 4 and retdd > 1.0:
        return "holds"
    if blocks_pos >= 3 and retdd > 0.5:
        return "fragile"
    return "fails"


def run_instrument(inst, base_tf='4h', htf1_tf='1D', htf2_tf='1W', verbose=True, chunk=None, nchunks=None):
    cost = COST.get(inst, DEFAULT_COST)
    folder = os.path.join(DATA, inst)
    base = load(os.path.join(folder, f"{base_tf}.csv"))
    h1 = load(os.path.join(folder, f"{htf1_tf}.csv"))
    h2 = load(os.path.join(folder, f"{htf2_tf}.csv"))
    daily = h1 if htf1_tf == '1D' else load(os.path.join(folder, "1D.csv"))
    buf = 0.0005 * float(np.median(base['close']))

    n = len(base)
    blk = n // TP.BLOCKS
    segs = [base.iloc[k * blk:(k + 1) * blk] if k < TP.BLOCKS - 1
            else base.iloc[k * blk:] for k in range(TP.BLOCKS)]

    # precompute cache keyed by SHA pair (the only thing precompute depends on)
    pc_full, pc_seg = {}, {}

    def get_full(key, c):
        if key not in pc_full:
            pc_full[key] = precompute(base, c, h1, h2, daily)
        return pc_full[key]

    def get_seg(key, i, c):
        k = (key, i)
        if k not in pc_seg:
            pc_seg[k] = precompute(segs[i], c, h1, h2, daily)
        return pc_seg[k]

    rows = []
    combos = list(TP.expand())
    if chunk is not None:
        combos = combos[chunk::nchunks]        # stride, so each chunk spans the whole grid
    for j, combo in enumerate(combos):
        c = cfg_from(combo, buf)
        c['htf1_dur'] = TF_DUR[htf1_tf]
        c['htf2_dur'] = TF_DUR[htf2_tf]
        key = (combo['sha'], combo['htf2'])
        m = metrics(backtest(get_full(key, c), c, cost=cost))
        bl = []
        if m['trades'] >= TP.MIN_TRADES:
            for i in range(TP.BLOCKS):
                bl.append(metrics(backtest(get_seg(key, i, c), c, cost=cost))['retdd'])
        bp = sum(1 for x in bl if x > 0)
        rows.append(dict(
            idx=j,
            sha=f"{combo['sha'][0]},{combo['sha'][1]}",
            htf2=f"{combo['htf2'][0]},{combo['htf2'][1]}", exit=combo['exit'],
            anchor=combo['anchor'], basis=combo['basis'],
            stop=combo['stop_style'], trail=combo['trail'],
            trades=m['trades'], win=m['win'], ret=m['ret'], maxdd=m['maxdd'],
            retdd=m['retdd'], blocks=bp, nblocks=TP.BLOCKS,
            block_detail=[round(x, 2) for x in bl],
            verdict=verdict(bp, m['retdd'], m['trades'])))
        if verbose and (j + 1) % 200 == 0:
            print(f"    {j+1}/{len(combos)}")

    # rank: block consistency first, then profit-to-pain
    if chunk is not None:
        return dict(instrument=inst, partial=True, rows=rows)
    rows.sort(key=lambda r: (r['blocks'], r['retdd']), reverse=True)
    ranked = [r for r in rows if r['trades'] >= TP.MIN_TRADES]
    span = f"{base.index[0].date()} → {base.index[-1].date()}"
    return dict(instrument=inst, cost_pct=round(cost*100, 3), base_tf=base_tf, htf1_tf=htf1_tf, htf2_tf=htf2_tf,
                span=span, bars=n, buffer=round(buf, 6),
                top=ranked[:3], all_runs=rows,
                n_holds=sum(1 for r in rows if r['verdict'] == 'holds'))


if __name__ == "__main__":
    import sys
    inst = sys.argv[1] if len(sys.argv) > 1 else 'EURUSD'
    res = run_instrument(inst)
    print(json.dumps({k: v for k, v in res.items() if k != 'all_runs'}, indent=1)[:1200])
