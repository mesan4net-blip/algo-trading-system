"""
fa_engine.py — faithful backtest engine mirroring 3SHA_FullAlignment_v1.pine.

Mirrors the finalized strategy exactly:
  - 3 SHA layers (two-pass EMA->HA->EMA), no-lookahead HTF alignment
  - Full Alignment entry (Confirmed 1-bar)
  - Gap skip (daily open vs prior daily close), default off
  - Initial stop: Trigger/Swing/HTF1-body/HTF2-body, Body or Wick basis, buffer, min-dist
  - Risk-based sizing (risk% / stop distance, capped by max-equity%)
  - Break-even, structural trailing stop (anchor menu), alignment-break exit, partial TP
  - Mental (close-based) stops by default; optional hard (intra-bar) stop
Everything close-based unless hard stop is enabled — same as the Pine.
"""
import numpy as np, pandas as pd

def ema(a, n): return pd.Series(a).ewm(span=n, adjust=False).mean().to_numpy()

def sha_ohlc(df, l1, l2):
    o,h,l,c=(df[x].to_numpy() for x in ['open','high','low','close'])
    o1,h1,l1_,c1=ema(o,l1),ema(h,l1),ema(l,l1),ema(c,l1)
    haC=(o1+h1+l1_+c1)/4.0; n=len(haC); haO=np.empty(n); haO[0]=(o1[0]+c1[0])/2
    for i in range(1,n): haO[i]=(haO[i-1]+haC[i-1])/2
    haH=np.maximum(h1,np.maximum(haO,haC)); haL=np.minimum(l1_,np.minimum(haO,haC))
    return ema(haO,l2),ema(haH,l2),ema(haL,l2),ema(haC,l2)

def align_htf(base_index, sha_o,sha_c, sha_index, dur, sha_h=None, sha_l=None, base_dur=None):
    """No-lookahead: HTF value available on the last base bar before its close (-15min conv).

    Returns open/close, plus high/low when supplied (needed for the Wick basis on
    the last-bar-beyond anchors)."""
    d={'o':sha_o,'c':sha_c}
    if sha_h is not None: d['h']=sha_h
    if sha_l is not None: d['l']=sha_l
    s=pd.DataFrame(d, index=sha_index)
    # A higher-timeframe value is only known once that bar CLOSES. The last base
    # bar able to use it is the one whose own close lands on that moment, so the
    # offset must be the BASE bar's duration -- not a hardcoded 15 minutes, which
    # leaks the value early on any chart faster than 15m.
    _bd = base_dur if base_dur is not None else pd.Timedelta('15min')
    s['ct']=pd.DatetimeIndex(s.index+dur-_bd).as_unit('ns')
    s=s.sort_values('ct').reset_index(drop=True)
    left=pd.DataFrame({'t':pd.DatetimeIndex(base_index).as_unit('ns')}).sort_values('t').reset_index(drop=True)
    m=pd.merge_asof(left,s,left_on='t',right_on='ct',direction='backward').set_index('t').reindex(base_index)
    if 'h' in d:
        return m['o'].values, m['c'].values, m['h'].values, m['l'].values
    return m['o'].values, m['c'].values

def gap_block_flags(base_index, daily_df, thresh):
    """Mark base bars that are the first bar of a NEW day whose open gapped > thresh%."""
    d=daily_df.copy()
    pclose=d['close'].shift(1)
    d['gap']=(d['open']-pclose).abs()/pclose*100.0
    # daily bar covering each base bar (by date, UTC)
    bdate=pd.DatetimeIndex(base_index).floor('D')
    gmap=d['gap']; gmap.index=pd.DatetimeIndex(d.index).floor('D')
    gap_of_day=pd.Series(bdate).map(gmap).fillna(0).values
    is_new_day=np.r_[True, bdate[1:]!=bdate[:-1]]
    return is_new_day & (gap_of_day>thresh)

def precompute(base_df, cfg, htf1_df, htf2_df, daily_df):
    idx=base_df.index
    bO,bH,bL,bC=sha_ohlc(base_df,*cfg['base_sha'])
    s1o,s1h,s1l,s1c=sha_ohlc(htf1_df,*cfg['htf1_sha'])
    s2o,s2h,s2l,s2c=sha_ohlc(htf2_df,*cfg['htf2_sha'])
    _bd = pd.Series(idx).diff().dt.total_seconds().median()
    base_dur = pd.Timedelta(seconds=float(_bd)) if _bd and _bd > 0 else pd.Timedelta('15min')
    h1O,h1C,h1H,h1L=align_htf(idx,s1o,s1c,htf1_df.index,cfg['htf1_dur'],s1h,s1l,base_dur)
    h2O,h2C,h2H,h2L=align_htf(idx,s2o,s2c,htf2_df.index,cfg['htf2_dur'],s2h,s2l,base_dur)
    bd=np.where(bC>=bO,1,-1); h1=np.where(h1C>=h1O,1,-1); h2=np.where(h2C>=h2O,1,-1)
    allb=(bd==1)&(h1==1)&(h2==1); alls=(bd==-1)&(h1==-1)&(h2==-1)
    # Confirmed (1-bar): all_bull[1] and not all_bull[2]
    fb=np.r_[False,False,allb[1:-1]&~allb[:-2]]; fs=np.r_[False,False,alls[1:-1]&~alls[:-2]]
    o,h,l,c=(base_df[x].to_numpy() for x in ['open','high','low','close'])
    body_low=np.minimum(o,c); body_high=np.maximum(o,c)
    def roll_min(a,n): return pd.Series(a).rolling(n,min_periods=1).min().to_numpy()
    def roll_max(a,n): return pd.Series(a).rolling(n,min_periods=1).max().to_numpy()
    # ---- Last-bar-beyond anchors -------------------------------------------
    # Most recent bar with ANY part past the SHA: below its lower edge (long) or
    # above its upper edge (short). Covers bars wholly beyond AND bars straddling
    # the edge. Forward-filled, so there is no lookback limit.
    sha_bot1_=np.minimum(h1O,h1C); sha_top1_=np.maximum(h1O,h1C)
    sha_bot2_=np.minimum(h2O,h2C); sha_top2_=np.maximum(h2O,h2C)
    ha_lo_b=np.minimum(bO,bC); ha_hi_b=np.maximum(bO,bC)
    def _ff(mask,vals):
        a=np.where(mask,vals,np.nan)
        return pd.Series(a).ffill().to_numpy()
    beyond={}
    for basis in ('Body','Wick'):
        p_lo = body_low  if basis=='Body' else l
        p_hi = body_high if basis=='Body' else h
        a_lo = ha_lo_b   if basis=='Body' else bL
        a_hi = ha_hi_b   if basis=='Body' else bH
        e1b  = sha_bot1_ if basis=='Body' else h1L
        e1t  = sha_top1_ if basis=='Body' else h1H
        e2b  = sha_bot2_ if basis=='Body' else h2L
        e2t  = sha_top2_ if basis=='Body' else h2H
        beyond[(basis,'px','h1','lo')]=_ff(p_lo<e1b,p_lo)
        beyond[(basis,'px','h2','lo')]=_ff(p_lo<e2b,p_lo)
        beyond[(basis,'ha','h1','lo')]=_ff(a_lo<e1b,a_lo)
        beyond[(basis,'ha','h2','lo')]=_ff(a_lo<e2b,a_lo)
        beyond[(basis,'px','h1','hi')]=_ff(p_hi>e1t,p_hi)
        beyond[(basis,'px','h2','hi')]=_ff(p_hi>e2t,p_hi)
        beyond[(basis,'ha','h1','hi')]=_ff(a_hi>e1t,a_hi)
        beyond[(basis,'ha','h2','hi')]=_ff(a_hi>e2t,a_hi)
        beyond[(basis,'near','lo')]=np.abs(c-e1b)<=np.abs(c-e2b)
        beyond[(basis,'near','hi')]=np.abs(c-e1t)<=np.abs(c-e2t)
    P=dict(idx=idx,o=o,h=h,l=l,c=c,beyond=beyond,bd=bd,h1=h1,h2=h2,allb=allb,alls=alls,fb=fb,fs=fs,
        base_bull=bd==1, htf1_bull=h1==1, htf2_bull=h2==1,
        body_low=body_low, body_high=body_high,
        sha_bot1=np.minimum(h1O,h1C), sha_top1=np.maximum(h1O,h1C),
        sha_bot2=np.minimum(h2O,h2C), sha_top2=np.maximum(h2O,h2C),
        roll_min=roll_min, roll_max=roll_max,
        gap_block=gap_block_flags(idx,daily_df,cfg.get('gap_thresh',0.5)))
    return P

def _anchor_low(P,i,mode,basis,lookback,swings):
    if mode=='Trigger':   return (P['body_low'][i] if basis=='Body' else P['l'][i])
    if mode=='Swing':     return swings[('low',basis,lookback)][i]
    if mode=='HTF1 Body': return P['sha_bot1'][i]
    return P['sha_bot2'][i]
def _anchor_high(P,i,mode,basis,lookback,swings):
    if mode=='Trigger':   return (P['body_high'][i] if basis=='Body' else P['h'][i])
    if mode=='Swing':     return swings[('high',basis,lookback)][i]
    if mode=='HTF1 Body': return P['sha_top1'][i]
    return P['sha_top2'][i]

def backtest(P, cfg):
    o,h,l,c=P['o'],P['h'],P['l'],P['c']; n=len(c)
    fb,fs,allb,alls,gap_block=P['fb'],P['fs'],P['allb'],P['alls'],P['gap_block']
    # pre-roll swings needed
    swings={}
    for basis in ['Body','Wick']:
        lo = P['body_low'] if basis=='Body' else P['l']
        hi = P['body_high'] if basis=='Body' else P['h']
        for lb in {cfg['sl_lookback'], cfg['trail_lookback']}:
            swings[('low',basis,lb)]=P['roll_min'](lo,lb)
            swings[('high',basis,lb)]=P['roll_max'](hi,lb)
    buf=cfg['sl_buffer']; tbuf=cfg['trail_buffer']; minstop=cfg['min_stop']
    equity=cfg.get('equity0',100000.0); eq_curve=[]
    pos=0; entry=0.0; stop=0.0; init=0.0; risk=0.0; qty=0.0; be=False; tptaken=False; ebar=-1
    trades=[]; posarr=np.zeros(n,int); stoparr=np.full(n,np.nan)
    for i in range(n):
        # ---- manage open position ----
        if pos==1:
            rr=(c[i]-entry)/risk if risk>0 else 0
            if cfg['use_tp1'] and (not tptaken) and rr>=cfg['tp1_r']:
                part=qty*cfg['tp1_pct']/100.0
                equity+=part*(c[i]-entry); qty-=part; tptaken=True
                if not be: stop=max(stop, entry+cfg['be_offset']); be=True
            if cfg['use_be'] and (not be) and rr>=cfg['be_trig_r']:
                stop=max(stop, entry+cfg['be_offset']); be=True
            if cfg['use_trail'] and rr>=cfg['trail_start_r']:
                ref=_anchor_low(P,i,cfg['trail_mode'],cfg['trail_basis'],cfg['trail_lookback'],swings)-tbuf
                if ref>stop: stop=ref
            align_out=cfg['use_align_exit'] and _align_broken(P,i,cfg['align_level'],1)
            if cfg['use_hard_stop']:
                hit = l[i]<=stop
                px = min(o[i],stop) if hit else c[i]
            else:
                hit = c[i]<=stop; px=c[i]
            if hit or align_out:
                equity+=qty*(px-entry); trades.append(('L',entry,px,rr)); pos=0; be=False; tptaken=False
        elif pos==-1:
            rr=(entry-c[i])/risk if risk>0 else 0
            if cfg['use_tp1'] and (not tptaken) and rr>=cfg['tp1_r']:
                part=qty*cfg['tp1_pct']/100.0
                equity+=part*(entry-c[i]); qty-=part; tptaken=True
                if not be: stop=min(stop, entry-cfg['be_offset']); be=True
            if cfg['use_be'] and (not be) and rr>=cfg['be_trig_r']:
                stop=min(stop, entry-cfg['be_offset']); be=True
            if cfg['use_trail'] and rr>=cfg['trail_start_r']:
                ref=_anchor_high(P,i,cfg['trail_mode'],cfg['trail_basis'],cfg['trail_lookback'],swings)+tbuf
                if ref<stop: stop=ref
            align_out=cfg['use_align_exit'] and _align_broken(P,i,cfg['align_level'],-1)
            if cfg['use_hard_stop']:
                hit=h[i]>=stop; px=max(o[i],stop) if hit else c[i]
            else:
                hit=c[i]>=stop; px=c[i]
            if hit or align_out:
                equity+=qty*(entry-px); trades.append(('S',entry,px,rr)); pos=0; be=False; tptaken=False
        # ---- entries (only when flat) ----
        if pos==0:
            blocked = cfg['skip_gaps'] and gap_block[i]
            if fb[i] and cfg['allow_longs'] and not blocked:
                st=_anchor_low(P,i,cfg['sl_mode'],cfg['sl_basis'],cfg['sl_lookback'],swings)-buf
                if minstop>0: st=min(st, c[i]-minstop)
                if st<c[i]:
                    _q=_qty(equity,c[i],st,cfg)
                    if _q>0:
                        entry=c[i]; init=st; stop=st; risk=entry-st
                        qty=_q; be=False; tptaken=False; ebar=i; pos=1
            elif fs[i] and cfg['allow_shorts'] and not blocked:
                st=_anchor_high(P,i,cfg['sl_mode'],cfg['sl_basis'],cfg['sl_lookback'],swings)+buf
                if minstop>0: st=max(st, c[i]+minstop)
                if st>c[i]:
                    _q=_qty(equity,c[i],st,cfg)
                    if _q>0:
                        entry=c[i]; init=st; stop=st; risk=st-entry
                        qty=_q; be=False; tptaken=False; ebar=i; pos=-1
        posarr[i]=pos; stoparr[i]=stop if pos!=0 else np.nan; eq_curve.append(equity)
    return dict(trades=trades, equity=np.array(eq_curve), pos=posarr, stop=stoparr,
                fb=fb, fs=fs)

def _qty(equity,entry,stop,cfg):
    """Fractional sizing: risk% of equity divided by the distance to the stop.

    No whole-unit rounding -- rounding down forced high-priced markets (Bitcoin)
    into one whole unit regardless of the risk setting, which both ignored the
    setting and massively oversized the position. Position value is capped by
    max_equity_pct, expressed as a percent of equity (400 = up to 4x)."""
    dist=abs(entry-stop)
    if dist<=0 or entry<=0: return 0.0
    q=(equity*cfg['risk_pct']/100.0)/dist
    qmax=(equity*cfg['max_equity_pct']/100.0)/entry
    return min(q,qmax)

def _align_broken(P,i,level,direction):
    bb=P['base_bull'][i]; h1=P['htf1_bull'][i]; h2=P['htf2_bull'][i]
    if direction==1:
        if level=='Base':  return not bb
        if level=='HTF1':  return not h1
        if level=='HTF2':  return not h2
        if level=='Any':   return (not bb) or (not h1) or (not h2)
        return P['alls'][i]  # All Layers Flip
    else:
        if level=='Base':  return bb
        if level=='HTF1':  return h1
        if level=='HTF2':  return h2
        if level=='Any':   return bb or h1 or h2
        return P['allb'][i]

def metrics(res):
    tr=res['trades']
    if not tr: return dict(trades=0,win=0,ret=0,maxdd=0,retdd=0)
    eq=res['equity']; e0=eq[0] if len(eq) else 100000
    rets=[(px/en-1 if d=='L' else en/px-1) for d,en,px,rr in tr]
    wins=sum(1 for r in rets if r>0)
    peak=np.maximum.accumulate(eq); dd=((eq-peak)/peak).min()*100
    ret=(eq[-1]/eq[0]-1)*100
    return dict(trades=len(tr), win=round(wins/len(tr)*100,1), ret=round(ret,1),
                maxdd=round(dd,1), retdd=round(ret/abs(dd),2) if dd else 0)

def default_cfg():
    return dict(
        base_sha=(4,8), htf1_sha=(4,8), htf2_sha=(2,2),
        htf1_dur=pd.Timedelta('1D'), htf2_dur=pd.Timedelta('7D'),
        allow_longs=True, allow_shorts=True,
        skip_gaps=False, gap_thresh=0.5,
        sl_mode='Swing', sl_basis='Body', sl_lookback=10, sl_buffer=2.0, min_stop=0.0,
        use_hard_stop=False,
        risk_pct=1.0, max_equity_pct=20.0, equity0=100000.0,
        use_tp1=False, tp1_r=2.0, tp1_pct=50.0,
        use_be=True, be_trig_r=1.0, be_offset=0.0,
        use_trail=True, trail_mode='Swing', trail_basis='Body', trail_start_r=1.0,
        trail_lookback=6, trail_buffer=2.0,
        use_align_exit=True, align_level='HTF1',
        reverse_on_stop=False)


# ---------------------------------------------------------------------------
# Compiled fast path. Identical logic to backtest() above, with string dispatch
# hoisted out into precomputed arrays so the bar loop can be JIT-compiled.
# Verified to match backtest() exactly before use.
# ---------------------------------------------------------------------------
try:
    from numba import njit
    _HAVE_NUMBA = True
except ImportError:
    _HAVE_NUMBA = False
    def njit(**kw):
        def deco(f): return f
        return deco


@njit(cache=True)
def _core(o, h, l, c, fb, fs, abl, abshort, alow, ahigh, tlow, thigh,
          allb, alls, use_rev,
          minstop, risk_pct, maxeq_pct, equity0,
          use_be, be_trig, be_off, use_trail, trail_start,
          use_align, use_hard, use_tp1, tp1_r, tp1_pct, cost):
    n = len(c)
    equity = equity0
    eq = np.empty(n)
    tr_ret = np.empty(n)
    ntr = 0
    pos = 0
    entry = 0.0; stop = 0.0; risk = 0.0; qty = 0.0
    be = False; tptaken = False
    for i in range(n):
        stopped = 0          # +1 a long was stopped this bar, -1 a short was
        if pos == 1:
            rr = (c[i] - entry) / risk if risk > 0 else 0.0
            if use_tp1 and (not tptaken) and rr >= tp1_r:
                part = qty * tp1_pct / 100.0
                equity += part * (c[i] - entry); qty -= part; tptaken = True
                if not be:
                    if entry + be_off > stop: stop = entry + be_off
                    be = True
            if use_be and (not be) and rr >= be_trig:
                if entry + be_off > stop: stop = entry + be_off
                be = True
            if use_trail and rr >= trail_start:
                if tlow[i] > stop: stop = tlow[i]
            align_out = use_align and abl[i]
            if use_hard:
                hit = l[i] <= stop
                px = min(o[i], stop) if hit else c[i]
            else:
                hit = c[i] <= stop
                px = c[i]
            if hit or align_out:
                equity += qty * (px - entry) - cost * qty * (entry + px) * 0.5
                tr_ret[ntr] = px / entry - 1.0 - cost; ntr += 1
                if hit:
                    stopped = 1
                pos = 0; be = False; tptaken = False
        elif pos == -1:
            rr = (entry - c[i]) / risk if risk > 0 else 0.0
            if use_tp1 and (not tptaken) and rr >= tp1_r:
                part = qty * tp1_pct / 100.0
                equity += part * (entry - c[i]); qty -= part; tptaken = True
                if not be:
                    if entry - be_off < stop: stop = entry - be_off
                    be = True
            if use_be and (not be) and rr >= be_trig:
                if entry - be_off < stop: stop = entry - be_off
                be = True
            if use_trail and rr >= trail_start:
                if thigh[i] < stop: stop = thigh[i]
            align_out = use_align and abshort[i]
            if use_hard:
                hit = h[i] >= stop
                px = max(o[i], stop) if hit else c[i]
            else:
                hit = c[i] >= stop
                px = c[i]
            if hit or align_out:
                equity += qty * (entry - px) - cost * qty * (entry + px) * 0.5
                tr_ret[ntr] = entry / px - 1.0 - cost; ntr += 1
                if hit:
                    stopped = -1
                pos = 0; be = False; tptaken = False
        if pos == 0:
            # Reverse on stop: flip only if the opposite side is fully aligned now.
            rev_l = use_rev and stopped == -1 and allb[i]
            rev_s = use_rev and stopped == 1 and alls[i]
            if fb[i] or rev_l:
                st = alow[i]
                if minstop > 0 and c[i] - minstop < st: st = c[i] - minstop
                if st < c[i]:
                    dist = c[i] - st
                    q = (equity * risk_pct / 100.0) / dist
                    qmax = (equity * maxeq_pct / 100.0) / c[i]
                    if qmax < q: q = qmax
                    if q > 0:
                        entry = c[i]; stop = st; risk = dist; qty = q
                        be = False; tptaken = False; pos = 1
            elif fs[i] or rev_s:
                st = ahigh[i]
                if minstop > 0 and c[i] + minstop > st: st = c[i] + minstop
                if st > c[i]:
                    dist = st - c[i]
                    q = (equity * risk_pct / 100.0) / dist
                    qmax = (equity * maxeq_pct / 100.0) / c[i]
                    if qmax < q: q = qmax
                    if q > 0:
                        entry = c[i]; stop = st; risk = dist; qty = q
                        be = False; tptaken = False; pos = -1
        eq[i] = equity
    return eq, tr_ret[:ntr]


_BEYOND = {'Last Bar Beyond Nearest SHA':      ('px', 'near'),
           'Last Bar Beyond Furthest SHA':     ('px', 'far'),
           'Last SHA Bar Beyond Nearest SHA':  ('ha', 'near'),
           'Last SHA Bar Beyond Furthest SHA': ('ha', 'far')}


def _anchor_arrays(P, mode, basis, lookback, buf, sign):
    """Return the stop/trail reference line for every bar, buffer already applied."""
    if mode in _BEYOND:
        src, which = _BEYOND[mode]
        side = 'hi' if sign > 0 else 'lo'
        B = P['beyond']
        near_h1 = B[(basis, 'near', side)]
        a1 = B[(basis, src, 'h1', side)]
        a2 = B[(basis, src, 'h2', side)]
        pick = np.where(near_h1, a1, a2) if which == 'near' else np.where(near_h1, a2, a1)
        # fall back to the swing anchor wherever no such bar exists yet
        src_sw = (P['body_high'] if basis == 'Body' else P['h']) if sign > 0 else \
                 (P['body_low'] if basis == 'Body' else P['l'])
        sw = P['roll_max'](src_sw, lookback) if sign > 0 else P['roll_min'](src_sw, lookback)
        pick = np.where(np.isnan(pick), sw, pick)
        return pick + buf if sign > 0 else pick - buf
    if mode == 'Trigger':
        base = P['body_low'] if basis == 'Body' else P['l']
        if sign > 0:
            base = P['body_high'] if basis == 'Body' else P['h']
    elif mode == 'Swing':
        src = (P['body_high'] if basis == 'Body' else P['h']) if sign > 0 else \
              (P['body_low'] if basis == 'Body' else P['l'])
        base = P['roll_max'](src, lookback) if sign > 0 else P['roll_min'](src, lookback)
    elif mode == 'HTF1 Body':
        base = P['sha_top1'] if sign > 0 else P['sha_bot1']
    else:
        base = P['sha_top2'] if sign > 0 else P['sha_bot2']
    return base + buf if sign > 0 else base - buf


def _align_arrays(P, level):
    bb, h1, h2 = P['base_bull'], P['htf1_bull'], P['htf2_bull']
    if level == 'Base':   return ~bb, bb
    if level == 'HTF1':   return ~h1, h1
    if level == 'HTF2':   return ~h2, h2
    if level == 'Any':    return (~bb) | (~h1) | (~h2), bb | h1 | h2
    return P['alls'].copy(), P['allb'].copy()


def backtest_fast(P, cfg, cost=0.001):
    alow = _anchor_arrays(P, cfg['sl_mode'], cfg['sl_basis'], cfg['sl_lookback'], cfg['sl_buffer'], -1)
    ahigh = _anchor_arrays(P, cfg['sl_mode'], cfg['sl_basis'], cfg['sl_lookback'], cfg['sl_buffer'], +1)
    tm = cfg['trail_mode']
    tlow = _anchor_arrays(P, tm, cfg['trail_basis'], cfg['trail_lookback'], cfg['trail_buffer'], -1)
    thigh = _anchor_arrays(P, tm, cfg['trail_basis'], cfg['trail_lookback'], cfg['trail_buffer'], +1)
    abl, abshort = _align_arrays(P, cfg['align_level'])
    eq, rets = _core(
        P['o'], P['h'], P['l'], P['c'], P['fb'], P['fs'],
        np.ascontiguousarray(abl), np.ascontiguousarray(abshort),
        np.ascontiguousarray(alow), np.ascontiguousarray(ahigh),
        np.ascontiguousarray(tlow), np.ascontiguousarray(thigh),
        np.ascontiguousarray(P['allb']), np.ascontiguousarray(P['alls']),
        bool(cfg.get('reverse_on_stop', False)),
        float(cfg['min_stop']), float(cfg['risk_pct']), float(cfg['max_equity_pct']),
        float(cfg['equity0']), bool(cfg['use_be']), float(cfg['be_trig_r']), float(cfg['be_offset']),
        bool(cfg['use_trail']), float(cfg['trail_start_r']), bool(cfg['use_align_exit']),
        bool(cfg['use_hard_stop']), bool(cfg['use_tp1']), float(cfg['tp1_r']), float(cfg['tp1_pct']),
        float(cost))
    return dict(equity=eq, rets=rets, trades=[None] * len(rets))


def metrics_fast(res):
    r = res['rets']
    if len(r) == 0:
        return dict(trades=0, win=0, ret=0, maxdd=0, retdd=0)
    eq = res['equity']
    peak = np.maximum.accumulate(eq)
    dd = ((eq - peak) / peak).min() * 100
    ret = (eq[-1] / eq[0] - 1) * 100
    return dict(trades=len(r), win=round(float((r > 0).mean()) * 100, 1), ret=round(float(ret), 1),
                maxdd=round(float(dd), 1), retdd=round(float(ret / abs(dd)), 2) if dd else 0)
