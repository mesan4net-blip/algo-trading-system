import numpy as np, pandas as pd, sys, json, warnings, datetime
warnings.filterwarnings('ignore'); sys.path.insert(0,'research')
from fa_engine import precompute, backtest, metrics, default_cfg
def load(p):
    d=pd.read_csv(p); d.columns=['time','open','high','low','close']+list(d.columns[5:])
    d['t']=pd.to_datetime(d['time'],utc=True).dt.as_unit('ns'); return d.set_index('t')[['open','high','low','close']]
U="/mnt/user-data/uploads/"
BTC=dict(b4=U+"BINANCE_BTCUSDT__240.csv",b1h=U+"BINANCE_BTCUSDT__60.csv",b15=U+"BINANCE_BTCUSDT__15.csv",d=U+"BINANCE_BTCUSDT__1D.csv",w=U+"BINANCE_BTCUSDT__1W.csv")
QQQ=dict(b4=U+"BATS_QQQ__240.csv",d=U+"BATS_QQQ__1D.csv",w=U+"BATS_QQQ__1W.csv")
SPY=dict(b4=U+"BATS_SPY__240.csv",d=U+"BATS_SPY__1D__1_.csv",w=U+"BATS_SPY__1W.csv")
EUR=dict(b4=U+"FOREXCOM_EURUSD__240.csv",b1h=U+"FOREXCOM_EURUSD__60.csv",b15=U+"FOREXCOM_EURUSD__15.csv",d=U+"FOREXCOM_EURUSD__1D.csv",w=U+"FOREXCOM_EURUSD__1W.csv")
ALIGN={'Base':'base flip','HTF1':'daily flip','HTF2':'weekly flip'}
cache={}
def L(p):
    if p not in cache: cache[p]=load(p)
    return cache[p]
rows=[]; rid=0; S="Full Alignment · 3SHA-FA"
def log(test,market,base_df,tf,dy,wk,cfg,window,buflabel):
    global rid
    m=metrics(backtest(precompute(base_df,cfg,dy,wk,dy),cfg)); rid+=1
    ma=f"{cfg['base_sha'][0]},{cfg['base_sha'][1]}·{cfg['htf1_sha'][0]},{cfg['htf1_sha'][1]}·{cfg['htf2_sha'][0]},{cfg['htf2_sha'][1]}"
    rows.append(dict(id=rid,strategy=S,test=test,market=market,base=tf,ma=ma,
        exit_on=ALIGN[cfg['align_level']],anchor=cfg['sl_mode'],basis=cfg['sl_basis'],
        stop='hard' if cfg['use_hard_stop'] else 'mental',risk=cfg['risk_pct'],cap=int(cfg['max_equity_pct']),
        buffer=buflabel,window=window,trades=m['trades'],win=m['win'],ret=m['ret'],maxdd=m['maxdd'],retdd=m['retdd']))

# Batch 1: Cross-market OOS (4h, cap100, %buffer)
for mk,F in [('BTC',BTC),('QQQ',QQQ),('SPY',SPY),('EURUSD',EUR)]:
    b=L(F['b4']); dy=L(F['d']); wk=L(F['w']); buf=0.0005*float(np.median(b['close'])); yrs=f"{b.index[0].year}-{b.index[-1].year}"
    for al in ['Base','HTF1']:
        for slm in ['Swing','HTF1 Body']:
            c=default_cfg(); c.update(align_level=al,sl_mode=slm,sl_basis='Body',trail_basis='Body',max_equity_pct=100,sl_buffer=buf,trail_buffer=buf)
            log("Cross-market OOS · 4h",mk,b,'4h',dy,wk,c,yrs,"0.05%")
# Batch 2: BTC dev 4h knobs
b=L(BTC['b4']); dy=L(BTC['d']); wk=L(BTC['w'])
for al in ['Base','HTF1','HTF2']:
    for slm in ['Swing','HTF1 Body','HTF2 Body']:
        c=default_cfg(); c.update(align_level=al,sl_mode=slm,sl_basis='Body',trail_basis='Body')
        log("BTC dev · 4h knobs",'BTC',b,'4h',dy,wk,c,'2025-2026',"2pt")
# Batch 3: BTC base sweep
for tf,key in [('15m','b15'),('1h','b1h'),('4h','b4')]:
    bb=L(BTC[key])
    for al in ['Base','HTF1']:
        c=default_cfg(); c.update(align_level=al,sl_mode='HTF1 Body',sl_basis='Body',trail_basis='Body')
        log("BTC dev · base sweep",'BTC',bb,tf,dy,wk,c,f'full {tf}',"2pt")
# Batch 4: MA sweep (4h, base flip, Swing, cap100, %buffer)
for mk,F in [('BTC',BTC),('QQQ',QQQ),('SPY',SPY),('EURUSD',EUR)]:
    b=L(F['b4']); dyy=L(F['d']); wkk=L(F['w']); buf=0.0005*float(np.median(b['close']))
    for l1,l2 in [(2,4),(4,8),(4,12),(6,12),(8,16),(8,24),(10,20),(12,30)]:
        c=default_cfg(); c.update(base_sha=(l1,l2),htf1_sha=(l1,l2),htf2_sha=(2,2),align_level='Base',sl_mode='Swing',sl_basis='Body',trail_basis='Body',max_equity_pct=100,sl_buffer=buf,trail_buffer=buf)
        log("MA sweep · 4h",mk,b,'4h',dyy,wkk,c,'full',"0.05%")

# Batch 5: genuine SHA validation (len1>=2; fixed configs; per-time-block consistency)
def blocks_pos(bdf,dy,wk,cf,B=5):
    n=len(bdf); blk=n//B; r=[]
    for k in range(B):
        seg=bdf.iloc[k*blk:(k+1)*blk] if k<B-1 else bdf.iloc[k*blk:]
        r.append(metrics(backtest(precompute(seg,cf,dy,wk,dy),cf))['retdd'])
    return sum(1 for x in r if x>0),B
for mk,F in [('BTC',BTC),('EURUSD',EUR),('QQQ',QQQ),('SPY',SPY)]:
    b=L(F['b4']); dy=L(F['d']); wk=L(F['w']); buf=0.0005*float(np.median(b['close']))
    configs=[(2,4),(3,6)]+([(5,12),(6,11)] if mk=='EURUSD' else [])
    for l1,l2 in configs:
        c=default_cfg(); c.update(base_sha=(l1,l2),htf1_sha=(l1,l2),htf2_sha=(2,2),align_level='Base',sl_mode='Swing',sl_basis='Body',trail_basis='Body',max_equity_pct=100,sl_buffer=buf,trail_buffer=buf)
        p,B=blocks_pos(b,dy,wk,c)
        log("Genuine SHA · 4h",mk,b,'4h',dy,wk,c,f"full · {p}/{B} blk+","0.05%")

strats={}
for r in rows: strats.setdefault(r['strategy'],[]).append(r)
summ={s:dict(n=len(rs),best=max(x['retdd'] for x in rs)) for s,rs in strats.items()}
meta=dict(generated=datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'),n=len(rows),
          note='Engine reconciled to TradingView to the penny. Cross-market OOS & MA sweep use cap 100% + scale-relative buffer.')
json.dump(dict(rows=rows,meta=meta,summary=summ),open('/mnt/user-data/outputs/results.json','w'),indent=1)

COLS=[('test','Test',1),('market','Market',1),('base','Base',1),('ma','MA b·h1·h2',1),('exit_on','Exit on',1),('anchor','Stop anchor',1),
 ('basis','Basis',1),('stop','Stop',1),('risk','Risk%',0),('cap','Cap%',0),('buffer','Buf',1),('window','Window',1),
 ('trades','Trades',0),('win','Win%',0),('ret','Return%',0),('maxdd','MaxDrop%',0),('retdd','Profit÷Pain',0)]
maxrd=max([abs(r['retdd']) for r in rows]+[1.0])
def cell(k,l,r):
    v=r[k]
    if k in('ret','maxdd'):
        cls='pos' if v>0 else 'neg' if v<0 else ''; return '<td class="%s">%s%s</td>'%(cls,'+' if v>0 else '',v)
    if k=='retdd':
        w=min(abs(v)/maxrd*46,46); col='var(--teal)' if v>=1.5 else 'var(--amber)' if v>=0.8 else 'var(--rose)'
        side='left:50%' if v>=0 else 'right:50%'; cls='pos' if v>=1.5 else 'neg' if v<0 else ''
        return '<td class="rd"><span class="bar" style="%s;width:%.1f%%;background:%s"></span><span class="v %s"><b>%s</b></span></td>'%(side,w,col,cls,v)
    return '<td class="l">%s</td>'%v if l else '<td>%s</td>'%v
def table(rs):
    rs=sorted(rs,key=lambda r:(r['market'],-r['retdd']))
    head=''.join('<th class="l">%s</th>'%t if l else '<th>%s</th>'%t for k,t,l in COLS)
    body=''.join('<tr>'+''.join(cell(k,l,r) for k,t,l in COLS)+'</tr>' for r in rs)
    return '<div class="scroll"><table><thead><tr>'+head+'</tr></thead><tbody>'+body+'</tbody></table></div>'
acc=''
for s,rs in strats.items():
    sm=summ[s]
    acc+='<details class="strat" open><summary><span class="sname">%s</span><span class="ssum">%d runs · <b>BTC</b> holds with genuine SHA (2,4 &amp; 3,6, 4/5 blocks) · <b>EUR/USD</b> real but only at slower SHA (~6,11) · QQQ/SPY dead · 1,1 (plain HA, no smoothing) disqualified</span></summary>'%(s,sm['n'])
    acc+='<div class="bar2"><span class="fixed">Fixed: HTF1=Daily · HTF2=Weekly · entry=Full Alignment (Confirmed) · break-even on · trailing on · gap-skip off. Click headers to build a multi-level sort (①②③…); click again to flip direction.</span><button class="clearsort">clear sort</button></div>'
    acc+=table(rs)+'</details>'

TPL=r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>3SHA Research Log</title><style>
:root{--bg:#0e141b;--panel:#151d27;--line:#243040;--ink:#e9e7df;--mut:#8a97a8;--amber:#d9a441;--teal:#57bf9f;--rose:#d76d81;--head:#0b1017}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1260px;margin:0 auto;padding:34px 22px 70px}
h1{font:600 15px/1 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--amber);margin:0 0 6px}
.sub{color:var(--mut);margin:0 0 2px;max-width:78ch}.meta{color:var(--mut);font:12px/1.5 ui-monospace,monospace;margin-top:8px}
.strat{border:1px solid var(--line);border-radius:11px;margin:16px 0;overflow:hidden;background:#111823}
.strat>summary{list-style:none;cursor:pointer;padding:15px 18px;background:var(--head);display:flex;flex-wrap:wrap;gap:6px 16px;align-items:baseline}
.strat>summary::-webkit-details-marker{display:none}
.strat>summary::before{content:"\25B8";color:var(--amber);margin-right:8px;font-size:12px}
.strat[open]>summary::before{content:"\25BE"}
.sname{font:600 13px ui-monospace,monospace;letter-spacing:.06em;color:var(--ink)}.ssum{color:var(--mut);font:12px ui-monospace,monospace}
.bar2{display:flex;align-items:center;gap:14px;padding:9px 18px 4px;flex-wrap:wrap}
.fixed{color:#7f8a99;font:11.5px/1.5 ui-monospace,monospace;margin:0;flex:1;min-width:280px}
.clearsort{background:var(--panel);color:var(--amber);border:1px solid var(--line);border-radius:6px;padding:5px 11px;font:11px ui-monospace,monospace;cursor:pointer}
.clearsort:hover{border-color:var(--amber)}
.scroll{overflow:auto;padding:0 12px 14px}
table{width:100%;border-collapse:collapse;font:12px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace}
th{position:sticky;top:0;background:#0d141c;color:var(--mut);text-align:right;padding:8px 8px;border-bottom:1px solid var(--line);white-space:nowrap;font-weight:500;cursor:pointer;user-select:none}
th:hover{color:var(--ink)}th.l,td.l{text-align:left}
td{padding:6px 8px;border-bottom:1px solid #1b2530;text-align:right;white-space:nowrap}
tbody tr:hover td{background:#131b24}
.pos{color:var(--teal)}.neg{color:var(--rose)}
.rd{position:relative}.rd .bar{position:absolute;top:3px;bottom:3px;border-radius:2px;opacity:.22}.rd .v{position:relative}
.sb{color:var(--amber);font-size:10px}
.tip{border-left:2px solid var(--amber);padding:8px 12px;margin:16px 0;color:#c9cfd8;background:#121a23;font-size:13px}
.foot{color:#5f6b7a;font:11px ui-monospace,monospace;margin-top:16px}
</style></head><body><div class="wrap">
<h1>3SHA Research Log</h1>
<p class="sub">Backtest results per strategy — each a collapsible section; more entry types will be added as their own sections. Read the terrain, not the peak: a real edge is a broad band of green that survives out-of-sample.</p>
<p class="meta">__META__</p>
<div class="tip">Engine reconciled to TradingView to the penny (entries, position, stops). Sort: click any header to make it the primary sort, click another to sort within it, and so on; click a sorted header again to flip its direction; <b>clear sort</b> resets to Market.</div>
__ACC__
<p class="foot">__NOTE__</p>
</div>
<script>
document.querySelectorAll('.strat table').forEach(function(tbl){
  var ths=[].slice.call(tbl.querySelectorAll('th'));
  var tb=tbl.querySelector('tbody');
  var marketCol=ths.findIndex(function(th){return th.textContent.replace(/[0-9\u2191\u2193]/g,'').trim()==='Market';});
  if(marketCol<0)marketCol=1;
  var spec=[{c:marketCol,d:1}];
  function parse(td){var t=td.textContent.replace('+','').replace('%','').trim();var n=parseFloat(t);return isNaN(n)?t.toLowerCase():n;}
  function apply(){
    var rows=[].slice.call(tb.querySelectorAll('tr'));
    rows.sort(function(a,b){
      for(var i=0;i<spec.length;i++){var c=spec[i].c,d=spec[i].d;var x=parse(a.children[c]),y=parse(b.children[c]);if(x<y)return -d;if(x>y)return d;}
      return 0;
    });
    rows.forEach(function(r){tb.appendChild(r);});
    ths.forEach(function(th,i){
      var idx=-1;for(var k=0;k<spec.length;k++)if(spec[k].c===i)idx=k;
      var b=th.querySelector('.sb');if(!b){b=document.createElement('span');b.className='sb';th.appendChild(b);}
      b.textContent= idx>=0 ? (' '+(idx+1)+(spec[idx].d>0?'\u2191':'\u2193')) : '';
    });
  }
  ths.forEach(function(th,i){th.addEventListener('click',function(){
    var found=null;for(var k=0;k<spec.length;k++)if(spec[k].c===i)found=spec[k];
    if(found)found.d=-found.d;else spec.push({c:i,d:1});
    apply();
  });});
  var det=tbl.closest('details');var btn=det?det.querySelector('.clearsort'):null;
  if(btn)btn.addEventListener('click',function(){spec=[{c:marketCol,d:1}];apply();});
  apply();
});
</script></body></html>"""
html=TPL.replace('__ACC__',acc).replace('__META__','%d runs · generated %s'%(meta['n'],meta['generated'])).replace('__NOTE__',meta['note'])
open('/mnt/user-data/outputs/3SHA_research_log.html','w').write(html)
print("runs=%d  sections=%d  html_kb=%.1f"%(len(rows),len(strats),len(html)/1024))
