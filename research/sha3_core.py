"""3SHA core: SHA computation, HTF resampling, alignment & Full-Alignment signals.
Built to reproduce the Pine v6 logic exactly for parity validation."""
import numpy as np
import pandas as pd

def ema(a, length):
    return pd.Series(a).ewm(span=length, adjust=False).mean().to_numpy()

def f_sha(o, h, l, c, len1=4, len2=8):
    o1, h1, l1, c1 = ema(o,len1), ema(h,len1), ema(l,len1), ema(c,len1)
    haC = (o1 + h1 + l1 + c1) / 4.0
    n = len(haC); haO = np.empty(n)
    haO[0] = (o1[0] + c1[0]) / 2.0
    for i in range(1, n):
        haO[i] = (haO[i-1] + haC[i-1]) / 2.0
    haH = np.maximum(h1, np.maximum(haO, haC))
    haL = np.minimum(l1, np.minimum(haO, haC))
    return ema(haO,len2), ema(haH,len2), ema(haL,len2), ema(haC,len2)

def resample_htf(df, rule):
    r = df.resample(rule, closed='left', label='left')
    out = pd.DataFrame({'open':r['open'].first(),'high':r['high'].max(),
                        'low':r['low'].min(),'close':r['close'].last()}).dropna()
    return out

def align_nolookahead(base_index, htf, rule):
    """Map each base bar to the most recently CLOSED htf bar (no lookahead).
    Keeps timezone-aware timestamps throughout so the reindex actually matches."""
    dur = pd.tseries.frequencies.to_offset(rule)
    h = htf.copy()
    h['close_time'] = h.index + dur
    h = h.sort_values('close_time').reset_index(drop=True)
    left = pd.DataFrame({'t': pd.DatetimeIndex(base_index)}).sort_values('t').reset_index(drop=True)
    m = pd.merge_asof(left, h, left_on='t', right_on='close_time', direction='backward')
    m = m.set_index('t')
    return m.reindex(base_index)

def build_layers(df, htf1_rule='1h', htf2_rule='4h'):
    o,h,l,c = df['open'].to_numpy(),df['high'].to_numpy(),df['low'].to_numpy(),df['close'].to_numpy()
    bO,bH,bL,bC = f_sha(o,h,l,c)
    out = pd.DataFrame(index=df.index)
    out['bO'],out['bH'],out['bL'],out['bC'] = bO,bH,bL,bC
    for rule,pfx in [(htf1_rule,'h1'),(htf2_rule,'h2')]:
        htf = resample_htf(df, rule)
        sO,sH,sL,sC = f_sha(htf['open'].to_numpy(),htf['high'].to_numpy(),htf['low'].to_numpy(),htf['close'].to_numpy())
        sha = pd.DataFrame({'o':sO,'h':sH,'l':sL,'c':sC}, index=htf.index)
        al = align_nolookahead(df.index, sha, rule)
        out[pfx+'O'],out[pfx+'H'],out[pfx+'L'],out[pfx+'C'] = al['o'].values,al['h'].values,al['l'].values,al['c'].values
    out['base_dir'] = np.where(out['bC']>=out['bO'],1,-1)
    out['htf1_dir'] = np.where(out['h1C']>=out['h1O'],1,-1)
    out['htf2_dir'] = np.where(out['h2C']>=out['h2O'],1,-1)
    allb = (out['base_dir']==1)&(out['htf1_dir']==1)&(out['htf2_dir']==1)
    alls = (out['base_dir']==-1)&(out['htf1_dir']==-1)&(out['htf2_dir']==-1)
    out['alignment'] = np.where(allb,1,np.where(alls,-1,0))
    out['all_bull'], out['all_bear'] = allb, alls
    return out

def full_alignment_signals(layers, confirm=True):
    ab, as_ = layers['all_bull'].to_numpy(), layers['all_bear'].to_numpy()
    if confirm:  # v6: all_bull[1] and not all_bull[2]
        fb = np.r_[False,False, ab[1:-1] & ~ab[:-2]]
        fs = np.r_[False,False, as_[1:-1] & ~as_[:-2]]
    else:
        fb = np.r_[False, ab[1:] & ~ab[:-1]]
        fs = np.r_[False, as_[1:] & ~as_[:-1]]
    return fb, fs
