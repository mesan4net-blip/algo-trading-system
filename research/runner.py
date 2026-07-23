"""
runner.py — run the full test plan on one instrument.

Ranking is by ROBUSTNESS, not raw return: a setting must stay positive across
independent time blocks to be called a keeper. A high return that only works in
one block ranks below a modest return that works in four.
"""
import os, json, warnings
import numpy as np, pandas as pd
warnings.filterwarnings('ignore')

from fa_engine import precompute, backtest, metrics, default_cfg
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


def cfg_from(combo, buf):
    c = default_cfg()
    c.update(base_sha=combo['sha'], htf1_sha=combo['sha'], htf2_sha=(2, 2),
             align_level=combo['exit'], sl_mode=combo['anchor'],
             sl_basis=combo['basis'], trail_basis=combo['basis'],
             use_hard_stop=(combo['stop_style'] == 'hard'),
             risk_pct=combo['risk'], max_equity_pct=100.0,
             sl_buffer=buf, trail_buffer=buf)
    return c


def verdict(blocks_pos, retdd, trades):
    if trades < TP.MIN_TRADES:
        return "thin"
    if blocks_pos >= 4 and retdd > 1.0:
        return "holds"
    if blocks_pos >= 3 and retdd > 0.5:
        return "fragile"
    return "fails"


def run_instrument(inst, base_tf='4h', htf1_tf='1D', htf2_tf='1W', verbose=True):
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

    def get_full(sha, c):
        if sha not in pc_full:
            pc_full[sha] = precompute(base, c, h1, h2, daily)
        return pc_full[sha]

    def get_seg(sha, i, c):
        k = (sha, i)
        if k not in pc_seg:
            pc_seg[k] = precompute(segs[i], c, h1, h2, daily)
        return pc_seg[k]

    rows = []
    combos = list(TP.expand())
    for j, combo in enumerate(combos):
        c = cfg_from(combo, buf)
        c['htf1_dur'] = TF_DUR[htf1_tf]
        c['htf2_dur'] = TF_DUR[htf2_tf]
        m = metrics(backtest(get_full(combo['sha'], c), c))
        bl = []
        if m['trades'] >= TP.MIN_TRADES:
            for i in range(TP.BLOCKS):
                bl.append(metrics(backtest(get_seg(combo['sha'], i, c), c))['retdd'])
        bp = sum(1 for x in bl if x > 0)
        rows.append(dict(
            idx=j,
            sha=f"{combo['sha'][0]},{combo['sha'][1]}", exit=combo['exit'],
            anchor=combo['anchor'], basis=combo['basis'],
            stop=combo['stop_style'], risk=combo['risk'],
            trades=m['trades'], win=m['win'], ret=m['ret'], maxdd=m['maxdd'],
            retdd=m['retdd'], blocks=bp, nblocks=TP.BLOCKS,
            block_detail=[round(x, 2) for x in bl],
            verdict=verdict(bp, m['retdd'], m['trades'])))
        if verbose and (j + 1) % 200 == 0:
            print(f"    {j+1}/{len(combos)}")

    # rank: block consistency first, then profit-to-pain
    rows.sort(key=lambda r: (r['blocks'], r['retdd']), reverse=True)
    ranked = [r for r in rows if r['trades'] >= TP.MIN_TRADES]
    span = f"{base.index[0].date()} → {base.index[-1].date()}"
    return dict(instrument=inst, base_tf=base_tf, htf1_tf=htf1_tf, htf2_tf=htf2_tf,
                span=span, bars=n, buffer=round(buf, 6),
                top=ranked[:3], all_runs=rows,
                n_holds=sum(1 for r in rows if r['verdict'] == 'holds'))


if __name__ == "__main__":
    import sys
    inst = sys.argv[1] if len(sys.argv) > 1 else 'EURUSD'
    res = run_instrument(inst)
    print(json.dumps({k: v for k, v in res.items() if k != 'all_runs'}, indent=1)[:1200])
