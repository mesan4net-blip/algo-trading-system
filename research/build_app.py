"""build_app.py — run the plan on every stored instrument and generate the bench page."""
import os, json, datetime, warnings
warnings.filterwarnings('ignore')
import test_plan as TP
from runner import run_instrument, REPO, DATA

STRATEGIES = [
    ("Full alignment", "live", "All three timeframes agree for the first time."),
    ("Partial alignment", "planned", "Two of the three agree."),
    ("Full cluster cross", "planned", "All three bodies cross together."),
    ("Pullback resume", "planned", "Re-entry after a dip inside a live trend."),
    ("Early trend", "planned", "The first turn, before full agreement."),
    ("Trend continuation", "planned", "Adds while a trend is already running."),
    ("High-timeframe cross", "planned", "Price crosses the slow trend body."),
    ("Mid-timeframe cross", "planned", "Price crosses the mid trend body."),
]

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600&family=Karla:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
:root{
--paper:#F5F8F2; --card:#FFFFFF; --ink:#16241E; --soft:#54655C; --faint:#8FA096;
--grow:#2E7A5A; --grow-lt:#E4F0E7; --honey:#B87A16; --honey-lt:#FAF0DC; --clay:#A9483A; --clay-lt:#F8E9E5;
--line:#E1E9DE; --line2:#CBD8C8;
--dsp:'Fraunces',Georgia,serif; --ui:'Karla',system-ui,sans-serif; --mono:'IBM Plex Mono',monospace;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.65 var(--ui);-webkit-font-smoothing:antialiased}
.wrap{max-width:1080px;margin:0 auto;padding:0 24px 96px}
code{font:400 13px var(--mono);background:var(--grow-lt);padding:2px 6px;border-radius:4px}

.hero{padding:72px 0 40px}
.eyebrow{font:500 12px/1 var(--mono);letter-spacing:.22em;text-transform:uppercase;color:var(--grow);margin:0 0 22px}
.hero h1{font:600 clamp(40px,6.5vw,72px)/1.02 var(--dsp);font-variation-settings:'SOFT' 40,'WONK' 1;letter-spacing:-.02em;margin:0 0 20px;max-width:16ch}
.hero p{font-size:18px;line-height:1.6;color:var(--soft);max-width:56ch;margin:0}

.mstrip{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;background:var(--line);
border:1px solid var(--line);border-radius:14px;overflow:hidden;margin-top:44px}
.m{background:var(--card);padding:20px 22px}
.m .n{font:600 34px/1 var(--dsp);font-variation-settings:'SOFT' 40;letter-spacing:-.02em;display:block}
.m .l{font:500 12px/1.4 var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--faint);margin-top:9px;display:block}

.sec{margin-top:76px}
.sh{display:flex;align-items:baseline;gap:14px;margin:0 0 8px;flex-wrap:wrap}
.sh h2{font:600 30px/1.15 var(--dsp);font-variation-settings:'SOFT' 40;letter-spacing:-.015em;margin:0}
.sh .tag{font:500 11px/1 var(--mono);letter-spacing:.16em;text-transform:uppercase;color:var(--faint)}
.sub{color:var(--soft);max-width:62ch;margin:0 0 26px;font-size:15.5px}

.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:26px 28px}

.grove{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:24px 26px;margin-bottom:14px}
.gtop{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
.gtop .nm{font:600 21px/1 var(--dsp);font-variation-settings:'SOFT' 40}
.gtop .meta{font:400 12.5px/1 var(--mono);color:var(--faint)}
.gtop .score{margin-left:auto;font:500 12.5px/1 var(--mono);color:var(--grow)}
.matrix{margin-top:18px}
.mrow{display:flex;gap:4px;margin-bottom:4px;align-items:center}
.mrow .rl{font:500 11.5px/1 var(--mono);color:var(--faint);width:46px;text-align:right;flex:none}
.mc{flex:1;height:34px;border-radius:4px;background:#F0F3EE;display:flex;align-items:center;justify-content:center;
font:500 12.5px/1 var(--mono);color:var(--grow)}
.mc.dk{color:#fff}
.mc.lbl{background:none;height:20px;color:var(--faint);font-size:11.5px}
.mrow.head{margin-bottom:6px}
.legend .axis{color:var(--soft)}
.legend{display:flex;gap:18px;flex-wrap:wrap;margin-top:14px;padding-top:13px;border-top:1px solid var(--line);
font:400 12.5px/1 var(--mono);color:var(--soft);align-items:center}
.legend i{width:11px;height:11px;border-radius:2px;display:inline-block;margin-right:6px;vertical-align:-1px}

.plan{display:grid;grid-template-columns:minmax(160px,auto) 1fr;gap:0 26px}
.plan .k{padding:15px 0;border-top:1px solid var(--line);font-weight:600;font-size:15px}
.plan .v{padding:15px 0;border-top:1px solid var(--line)}
.plan .k.first,.plan .v.first{border-top:none}
.plan .vals{font:500 13.5px/1.7 var(--mono);color:var(--grow)}
.plan .why{color:var(--soft);font-size:14px;margin-top:3px}
.fixed{margin-top:24px;padding-top:20px;border-top:1px solid var(--line);
display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:11px 30px}
.fixed div{font-size:13.5px;color:var(--soft);display:flex;gap:9px}
.fixed b{color:var(--ink);font-weight:600;flex:none;min-width:118px}

.sgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(238px,1fr));gap:12px}
.scard{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px}
.scard.live{border-color:var(--grow);background:var(--grow-lt)}
.scard h3{font:600 17px/1.2 var(--dsp);font-variation-settings:'SOFT' 40;margin:0 0 5px}
.scard p{font-size:13.5px;color:var(--soft);margin:0 0 12px;line-height:1.5}
.st{font:500 10.5px/1 var(--mono);letter-spacing:.13em;text-transform:uppercase;color:var(--faint)}
.scard.live .st{color:var(--grow)}

.inst{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:24px 26px;margin-bottom:14px}
.ih{display:flex;align-items:baseline;gap:13px;flex-wrap:wrap;margin-bottom:18px}
.ih .nm{font:600 24px/1 var(--dsp);font-variation-settings:'SOFT' 40;letter-spacing:-.01em}
.ih .meta{font:400 12.5px/1.5 var(--mono);color:var(--faint)}
.pick{display:flex;gap:15px;align-items:flex-start;padding:15px 0;border-top:1px solid var(--line)}
.pick .rk{font:600 15px/1 var(--dsp);color:var(--faint);width:19px;flex:none;padding-top:3px}
.pick .body{flex:1;min-width:0}
.pick .set{font:500 13.5px/1.5 var(--mono);word-break:break-word}
.pick .nums{display:flex;gap:19px;flex-wrap:wrap;margin-top:7px;font-size:13px;color:var(--soft)}
.pick .nums b{color:var(--ink);font-weight:600;font-family:var(--mono)}
.vb{font:500 11px/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;padding:5px 11px;border-radius:20px;flex:none}
.vb.holds{background:var(--grow-lt);color:var(--grow)}
.vb.fragile{background:var(--honey-lt);color:var(--honey)}
.vb.fails{background:var(--clay-lt);color:var(--clay)}
.vb.thin{background:#EEF1EC;color:var(--faint)}
.blocks{display:inline-flex;gap:3px;vertical-align:-1px;margin-left:3px}
.blocks i{width:7px;height:7px;border-radius:50%;background:#DCE4D9;display:inline-block}
.blocks i.on{background:var(--grow)}
.readnote{margin-top:16px;padding:13px 16px;background:var(--grow-lt);border-radius:10px;font-size:13.5px;color:#28503F}

details.all{margin-top:16px;border-top:1px solid var(--line);padding-top:14px}
details.all>summary{cursor:pointer;font:500 13px/1 var(--mono);color:var(--grow);list-style:none}
details.all>summary::-webkit-details-marker{display:none}
details.all>summary::before{content:"+ ";font-weight:600}
details.all[open]>summary::before{content:"\\2013 "}
.scroll{overflow:auto;max-height:440px;margin-top:14px;border:1px solid var(--line);border-radius:10px}
table{width:100%;border-collapse:collapse;font:400 12.5px/1.5 var(--mono)}
th{position:sticky;top:0;background:#F0F4EE;color:var(--soft);text-align:right;padding:9px 10px;font-weight:500;
white-space:nowrap;border-bottom:1px solid var(--line)}
th.l,td.l{text-align:left}
td{padding:7px 10px;text-align:right;white-space:nowrap;border-bottom:1px solid #F0F3EE}
tbody tr:hover td{background:#F7FAF5}
.pos{color:var(--grow)}.neg{color:var(--clay)}

.steps{list-style:none;padding:0;margin:0;counter-reset:s}
.steps li{counter-increment:s;position:relative;padding-left:44px;margin-bottom:20px}
.steps li:last-child{margin-bottom:0}
.steps li::before{content:counter(s);position:absolute;left:0;top:-2px;width:29px;height:29px;border-radius:50%;
background:var(--grow-lt);color:var(--grow);font:600 14px/29px var(--dsp);text-align:center}
.steps h4{margin:0 0 3px;font-size:15.5px;font-weight:600}
.steps p{margin:0;color:var(--soft);font-size:14px;line-height:1.55}
.honest{margin-top:24px;padding:15px 18px;background:var(--honey-lt);border-radius:10px;font-size:14px;color:#6E4A0C}
.stored{margin-top:26px;padding-top:20px;border-top:1px solid var(--line)}
.stored h4{font:500 11.5px/1 var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--faint);margin:0 0 12px}
.srow{display:flex;gap:14px;align-items:baseline;padding:8px 0;border-bottom:1px solid #F0F3EE;font-size:13.5px;flex-wrap:wrap}
.srow .i{font-weight:600;min-width:78px;font-family:var(--mono);font-size:13px}
.srow .t{color:var(--faint);font-family:var(--mono);font-size:12.5px}

.foot{margin-top:80px;padding-top:26px;border-top:1px solid var(--line2);color:var(--faint);font-size:13.5px}
.foot .line{font:400 19px/1.5 var(--dsp);color:var(--soft);margin:0 0 10px;max-width:44ch}

@media(max-width:640px){
.plan{grid-template-columns:1fr;gap:0}
.plan .v{padding-top:0;border-top:none}
.pick{flex-wrap:wrap}
.mrow .rl{width:38px}
}
@media(prefers-reduced-motion:no-preference){
.reveal{opacity:0;transform:translateY(14px);animation:up .7s cubic-bezier(.2,.7,.3,1) forwards}
@keyframes up{to{opacity:1;transform:none}}
}
"""

VMAP = {'holds': 'h', 'fragile': 'f', 'fails': 'x', 'thin': 't'}


def enrich(res):
    """Add annualised return and a time-aware ratio, then re-rank.

    Profit-divided-by-pain has no sense of time: +24% earned over 26 years scores the
    same as +24% in one year. Annualising fixes that, so a setting that barely moves
    can no longer top the table on a small drawdown alone.
    """
    a, b = [s.strip() for s in res['span'].split('→')]
    yrs = max((datetime.date.fromisoformat(b) - datetime.date.fromisoformat(a)).days / 365.25, 0.25)
    res['years'] = round(yrs, 1)
    for r in res['all_runs']:
        g = 1 + r['ret'] / 100.0
        r['cagr'] = round(((g ** (1 / yrs)) - 1) * 100, 2) if g > 0 else -100.0
        dd = abs(r['maxdd'])
        r['mar'] = round(r['cagr'] / dd, 2) if dd > 0.01 else 0.0
        if r['verdict'] == 'holds' and r['mar'] < 0.25:
            r['verdict'] = 'fragile'          # positive but not paying for the wait
    res['all_runs'].sort(key=lambda r: (r['blocks'], r['mar']), reverse=True)
    ranked = [r for r in res['all_runs'] if r['trades'] >= TP.MIN_TRADES]
    res['top'] = ranked[:3]
    res['n_holds'] = sum(1 for r in res['all_runs'] if r['verdict'] == 'holds')
    return res


def num(v, plus=False):
    cls = 'pos' if v > 0 else 'neg' if v < 0 else ''
    return f'<td class="{cls}">{"+" if plus and v > 0 else ""}{v}</td>'


def blocks_dots(r):
    return ('<span class="blocks">' +
            ''.join(f'<i class="{"on" if i < r["blocks"] else ""}"></i>' for i in range(r['nblocks'])) +
            '</span>')


def setting_str(r):
    return (f"{r['sha']} / {r.get('htf2','2,2')} · {r['exit']} flip · {r['anchor']} · "
            f"{r['basis']} · {r['stop']} · trail {r.get('trail','Swing 6')}")


def pick_html(r, rank):
    return f'''<div class="pick"><span class="rk">{rank}</span><div class="body">
<div class="set">{setting_str(r)}</div>
<div class="nums"><span>{r['trades']} trades</span><span>{r['win']}% won</span>
<span>per year <b>{'+' if r['cagr']>0 else ''}{r['cagr']}%</b></span>
<span>total <b>{'+' if r['ret']>0 else ''}{r['ret']}%</b></span>
<span>worst dip <b>{r['maxdd']}%</b></span>
<span>year&divide;dip <b>{r['mar']}</b></span>
<span>{r['blocks']} of {r['nblocks']} periods{blocks_dots(r)}</span></div></div>
<span class="vb {r['verdict']}">{r['verdict']}</span></div>'''


HEAD = ("<tr><th class='l'>Setting</th><th>Trades</th><th>Win%</th><th>Per year%</th><th>Total%</th>"
        "<th>Worst dip%</th><th>Year&divide;dip</th><th>Periods</th><th class='l'>Verdict</th></tr>")


def row_html(r):
    return (f"<tr><td class='l'>{setting_str(r)}</td><td>{r['trades']}</td><td>{r['win']}</td>"
            f"{num(r['cagr'], True)}{num(r['ret'], True)}{num(r['maxdd'])}{num(r['mar'])}"
            f"<td>{r['blocks']}/{r['nblocks']}</td><td class='l'>{r['verdict']}</td></tr>")


def grove_html(res):
    rowv = [TP.PLAN['sha']['fmt'](v) for v in TP.PLAN['sha']['values']]
    colv = [TP.PLAN['htf2']['fmt'](v) for v in TP.PLAN['htf2']['values']]
    cellmap = {}
    for r in res['all_runs']:
        k = (r['sha'], r.get('htf2', '2,2'))
        c = cellmap.setdefault(k, {'n': 0, 'held': 0, 'best': None})
        c['n'] += 1
        if r['verdict'] == 'holds':
            c['held'] += 1
        if c['best'] is None or r['mar'] > c['best']['mar']:
            c['best'] = r
    per = max((c['n'] for c in cellmap.values()), default=1)

    head = '<div class="mrow head"><span class="rl"></span>' + ''.join(
        f'<span class="mc lbl">{c}</span>' for c in colv) + '</div>'
    body = ''
    for rv in rowv:
        cells = ''
        for cv in colv:
            c = cellmap.get((rv, cv))
            if not c:
                cells += '<span class="mc"></span>'
                continue
            frac = c['held'] / max(c['n'], 1)
            b = c['best']
            tip = (f"chart {rv} · slow {cv} — {c['held']} of {c['n']} held, "
                   f"best {b['cagr']}%/yr vs {b['maxdd']}% dip")
            style = f"background:rgba(46,122,90,{round(0.06 + frac * 0.94, 3)})" if frac > 0 else ""
            txt = c['held'] if c['held'] else ''
            dark = ' dk' if frac > 0.45 else ''
            cells += f'<span class="mc v{dark}" style="{style}" title="{tip}">{txt}</span>'
        body += f'<div class="mrow"><span class="rl">{rv}</span>{cells}</div>'

    held = res['n_holds']
    n = max(len(res['all_runs']), 1)
    pct = round(held / n * 100)
    return f'''<div class="grove">
<div class="gtop"><span class="nm">{res['instrument']}</span>
<span class="meta">{res['span']} · {res['bars']:,} bars</span>
<span class="score">{held} of {n:,} held ({pct}%)</span></div>
<div class="matrix">{head}{body}</div>
<div class="legend"><span class="axis">rows — chart &amp; mid smoothing &nbsp;·&nbsp; columns — slow-layer smoothing</span>
<span style="color:var(--faint)">number = how many of the {per} variations in that pairing survived every period</span></div></div>'''


def build(results, manifest):
    now = datetime.datetime.utcnow().strftime('%d %B %Y')
    total_runs = sum(len(r['all_runs']) for r in results)
    total_holds = sum(r['n_holds'] for r in results)
    live = sum(1 for s in STRATEGIES if s[1] == 'live')

    metrics = f'''<div class="mstrip">
<div class="m"><span class="n">{len(results)}</span><span class="l">markets tested</span></div>
<div class="m"><span class="n">{total_runs:,}</span><span class="l">backtests run</span></div>
<div class="m"><span class="n">{total_holds}</span><span class="l">settings that held</span></div>
<div class="m"><span class="n">{live}<span style="color:var(--faint);font-size:22px"> / {len(STRATEGIES)}</span></span><span class="l">signals built</span></div>
</div>'''

    plan = '<div class="card"><div class="plan">'
    for i, (k, v) in enumerate(TP.PLAN.items()):
        f = ' first' if i == 0 else ''
        vals = " · ".join(str(v['fmt'](x)) for x in v['values'])
        plan += f'<div class="k{f}">{v["label"]}</div><div class="v{f}"><div class="vals">{vals}</div><div class="why">{v["plain"]}</div></div>'
    plan += '</div><div class="fixed">'
    plan += ''.join(f'<div><b>{a}</b><span>{b}</span></div>' for a, b in TP.FIXED)
    plan += '</div></div>'

    sg = '<div class="sgrid">' + ''.join(
        f'<div class="scard{" live" if st=="live" else ""}"><h3>{n}</h3><p>{d}</p><span class="st">{st}</span></div>'
        for n, st, d in STRATEGIES) + '</div>'

    groves = ''.join(grove_html(r) for r in results)

    ins = ''
    for res in results:
        blk = res['bars'] // TP.BLOCKS
        picks = ''.join(pick_html(r, i + 1) for i, r in enumerate(res['top']))
        if not picks:
            picks = '<div class="pick"><div class="body"><div class="set">Nothing traded enough to judge.</div></div></div>'
        allr = ''.join(row_html(r) for r in res['all_runs'])
        ins += f'''<div class="inst"><div class="ih"><span class="nm">{res['instrument']}</span>
<span class="meta">{res['base_tf']} chart · {res['htf1_tf']} and {res['htf2_tf']} filters · {res['span']} · {res['years']} years</span></div>
{picks}
<div class="readnote">Ranked by how many separate periods stayed profitable, then by return <em>per year</em> against the worst dip. A small drawdown alone can't earn a top spot — the return has to be worth the wait. Tested over {res['years']} years; each period covers about {blk:,} bars.</div>
<details class="all"><summary>Show all {len(res['all_runs'])} variations</summary>
<div class="scroll"><table>{HEAD}{allr}</table></div></details></div>'''

    stored = ''
    for inst, v in manifest['instruments'].items():
        tfs = ' · '.join(f"{k} {v['timeframes'][k]['bars']:,}" for k in v['timeframes'])
        stored += f'<div class="srow"><span class="i">{inst}</span><span class="t">{v["venue"]}</span><span class="t">{tfs}</span></div>'

    run = f'''<div class="card">
<ol class="steps">
<li><h4>Bring the market</h4><p>Upload any number of timeframe files and name the instrument. The plan needs a 4-hour chart plus daily and weekly at minimum.</p></li>
<li><h4>It gets kept</h4><p>Files are stored in the repository under <code>data/</code>, so a market only ever has to be uploaded once.</p></li>
<li><h4>Every variation runs</h4><p>All {TP.count()} combinations, then each one re-checked across {TP.BLOCKS} separate stretches of history.</p></li>
<li><h4>The page grows</h4><p>A new section appears here with the settings that held, and the full grid underneath.</p></li>
</ol>
<div class="honest">This page is the record, not the engine — it can't run a test on its own. Saying <b>run &lt;market&gt;</b> in chat is what starts one.</div>
<div class="stored"><h4>Markets held in the repository</h4>{stored}</div></div>'''

    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>3SHA — research bench</title><style>{CSS}</style></head><body><div class="wrap">

<header class="hero reveal">
<p class="eyebrow">3SHA · research bench</p>
<h1>What holds up when you actually check.</h1>
<p>One idea, {TP.count()} ways to trade it, put through the same honest examination on every market. Most of them fail — and knowing exactly which ones, and where, is worth more than any single good result.</p>
{metrics}
</header>

<section class="sec">
<div class="sh"><h2>The terrain</h2><span class="tag">every variation, at a glance</span></div>
<p class="sub">Each mark is one complete backtest. Green survived across separate stretches of history; amber held only partly; pale ones didn't make it. A real edge shows up as a band of green, not a lone bright dot.</p>
{groves}
</section>

<section class="sec">
<div class="sh"><h2>What gets tested</h2><span class="tag">the fixed plan</span></div>
<p class="sub">Every market is put through this identical grid, so results can be compared instead of each one being quietly tuned to look good.</p>
{plan}
</section>

<section class="sec">
<div class="sh"><h2>The signals</h2><span class="tag">{live} of {len(STRATEGIES)} built</span></div>
<p class="sub">Each entry type is built and proven on its own before any of them are combined.</p>
{sg}
</section>

<section class="sec">
<div class="sh"><h2>What survived</h2><span class="tag">best settings per market</span></div>
<p class="sub">The three strongest settings for each market, with the full grid kept underneath so nothing is hidden.</p>
{ins}
</section>

<section class="sec">
<div class="sh"><h2>Add a market</h2></div>
{run}
</section>

<footer class="foot">
<p class="line">Built slowly, on purpose. Every number here is a backtest — a careful record of the past, never a promise about what comes next.</p>
<p>Engine reconciled to TradingView to the penny: entries, position state and stop levels all match. Generated {now}.</p>
</footer>
</div></body></html>'''


if __name__ == "__main__":
    import sys, time
    out = os.path.join(REPO, "research")
    cache = os.path.join(out, "runs")
    os.makedirs(cache, exist_ok=True)
    manifest = json.load(open(os.path.join(DATA, "manifest.json")))
    arg = sys.argv[1] if len(sys.argv) > 1 else "build"

    if arg != "build":
        t0 = time.time()
        res = run_instrument(arg, verbose=False)
        json.dump(res, open(os.path.join(cache, f"{arg}.json"), "w"))
        top = res['top'][0] if res['top'] else None
        print(f"{arg}: {len(res['all_runs'])} runs in {time.time()-t0:.0f}s · {res['n_holds']} held")
        if top:
            print(f"  best  {setting_str(top)}")
            print(f"        ret {top['ret']}%  dd {top['maxdd']}%  p/p {top['retdd']}  "
                  f"{top['blocks']}/{top['nblocks']} periods  {top['trades']} trades")
    else:
        results = []
        for inst in manifest['instruments']:
            f = os.path.join(cache, f"{inst}.json")
            if os.path.exists(f):
                results.append(enrich(json.load(open(f))))
        html = build(results, manifest)
        open(os.path.join(out, "index.html"), "w").write(html)
        print(f"index.html ({len(html)//1024} KB) · {len(results)} markets · "
              f"{sum(len(r['all_runs']) for r in results):,} runs")
