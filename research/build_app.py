"""build_app.py — run the plan on every stored instrument and generate the app page."""
import os, json, datetime, warnings
warnings.filterwarnings('ignore')
import test_plan as TP
from runner import run_instrument, REPO, DATA

STRATEGIES = [
    ("Full Alignment", "3SHA-FA", "validated", "All three timeframes agree for the first time."),
    ("Partial Alignment", "", "not built", "Two of the three timeframes agree."),
    ("Full Cluster Cross", "", "not built", "All three SHA bodies cross together."),
    ("Pullback Resume", "", "not built", "Re-entry after a pullback inside an existing trend."),
    ("Early Trend", "", "not built", "Earliest turn signal, before full agreement."),
    ("Trend Continuation", "", "not built", "Adds while a trend is already running."),
    ("HTF2 Price Cross", "", "not built", "Price crosses the high-timeframe body."),
    ("HTF1 Price Cross", "", "not built", "Price crosses the mid-timeframe body."),
]

CSS = """
:root{--bg:#0e141b;--pan:#141c26;--pan2:#111823;--line:#243040;--ink:#e9e7df;--mut:#8a97a8;--dim:#5f6b7a;
--amber:#d9a441;--teal:#57bf9f;--rose:#d76d81;--head:#0b1017}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.6 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:32px 20px 70px}
h1{font:600 15px/1 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.15em;text-transform:uppercase;color:var(--amber);margin:0 0 6px}
.lead{color:var(--mut);max-width:74ch;margin:0}
.gen{color:var(--dim);font:11.5px ui-monospace,monospace;margin-top:6px}
.sec{margin-top:30px}
.sech{font:600 12px ui-monospace,monospace;letter-spacing:.14em;color:var(--dim);text-transform:uppercase;margin:0 0 10px}
.card{background:var(--pan);border:1px solid var(--line);border-radius:12px;padding:16px 18px}
.pgrid{display:grid;grid-template-columns:minmax(150px,auto) 1fr;gap:9px 18px;font-size:13px;align-items:baseline}
.pname{color:var(--ink)}
.pvals{font:12.5px ui-monospace,monospace;color:var(--amber)}
.pplain{grid-column:1/-1;color:var(--dim);font-size:12px;margin:-4px 0 6px;padding-left:2px}
.tot{margin-top:14px;padding-top:12px;border-top:1px solid var(--line);font:12px ui-monospace,monospace;color:var(--mut)}
.tot b{color:var(--ink);font-weight:600}
.fx{display:grid;grid-template-columns:minmax(140px,auto) 1fr;gap:5px 16px;font-size:12px;color:var(--mut);margin-top:10px}
.fx span:nth-child(odd){color:var(--dim)}
.sgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px}
.scard{background:var(--pan);border:1px solid var(--line);border-radius:12px;padding:13px 15px}
.scard.on{border-color:#2f5d4d}
.sn{font-size:13.5px;font-weight:600;margin:0}
.sd{font-size:12px;color:var(--dim);margin:3px 0 0}
.pill{display:inline-block;font:10.5px ui-monospace,monospace;padding:2px 8px;border-radius:20px;border:1px solid var(--line);color:var(--mut);margin-top:8px}
.pill.ok{color:var(--teal);border-color:#2f5d4d}
.inst{background:var(--pan);border:1px solid var(--line);border-radius:12px;margin-bottom:14px;overflow:hidden}
.ihead{padding:14px 18px;background:var(--head);display:flex;flex-wrap:wrap;gap:6px 14px;align-items:baseline}
.iname{font:600 15px ui-monospace,monospace}
.imeta{color:var(--mut);font:12px ui-monospace,monospace}
.ibody{padding:14px 18px}
.tt{width:100%;border-collapse:collapse;font:12px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace}
.tt th{color:var(--dim);text-align:right;padding:6px 7px;border-bottom:1px solid var(--line);font-weight:500;white-space:nowrap}
.tt th.l,.tt td.l{text-align:left}
.tt td{padding:7px 7px;border-bottom:1px solid #1b2530;text-align:right;white-space:nowrap}
.rank{color:var(--amber);font-weight:600}
.pos{color:var(--teal)}.neg{color:var(--rose)}
.v-holds{background:#123328;color:var(--teal);padding:2px 8px;border-radius:20px;font-size:11px}
.v-fragile{background:#332a12;color:var(--amber);padding:2px 8px;border-radius:20px;font-size:11px}
.v-fails{background:#331a1f;color:var(--rose);padding:2px 8px;border-radius:20px;font-size:11px}
.v-thin{background:#1c242e;color:var(--dim);padding:2px 8px;border-radius:20px;font-size:11px}
details.all{margin-top:12px;border-top:1px solid var(--line);padding-top:10px}
details.all>summary{cursor:pointer;color:var(--mut);font:12px ui-monospace,monospace;list-style:none}
details.all>summary::-webkit-details-marker{display:none}
details.all>summary::before{content:"\\25B8 ";color:var(--amber)}
details.all[open]>summary::before{content:"\\25BE "}
.scroll{overflow:auto;max-height:460px;margin-top:10px}
.note{border-left:2px solid var(--amber);background:#121a23;padding:9px 13px;margin:12px 0;font-size:12.5px;color:#c9cfd8}
.steps{counter-reset:s;list-style:none;padding:0;margin:0}
.steps li{counter-increment:s;position:relative;padding-left:30px;margin-bottom:11px;font-size:13px;color:var(--mut)}
.steps li::before{content:counter(s);position:absolute;left:0;top:0;width:20px;height:20px;border-radius:50%;background:var(--head);border:1px solid var(--line);color:var(--amber);font:11px/19px ui-monospace,monospace;text-align:center}
.steps b{color:var(--ink);font-weight:600}
.dt{width:100%;border-collapse:collapse;font:12px ui-monospace,monospace;margin-top:10px}
.dt td{padding:5px 8px;border-bottom:1px solid #1b2530;color:var(--mut)}
.dt td:first-child{color:var(--ink)}
.dt td:last-child{text-align:right;color:var(--dim)}
.foot{color:var(--dim);font:11px ui-monospace,monospace;margin-top:26px;border-top:1px solid var(--line);padding-top:12px}
"""


def fmt_num(v, plus=False):
    cls = 'pos' if v > 0 else 'neg' if v < 0 else ''
    s = f"{'+' if plus and v > 0 else ''}{v}"
    return f'<td class="{cls}">{s}</td>'


def row_html(r, rank=None):
    setting = f"{r['sha']} · {r['exit']} · {r['anchor']} · {r['basis']} · {r['stop']} · {r['risk']}%"
    rk = f'<td class="rank">{rank}</td>' if rank else '<td></td>'
    return (f"<tr>{rk}<td class='l'>{setting}</td><td>{r['trades']}</td><td>{r['win']}</td>"
            f"{fmt_num(r['ret'], True)}{fmt_num(r['maxdd'])}{fmt_num(r['retdd'])}"
            f"<td>{r['blocks']}/{r['nblocks']}</td>"
            f"<td><span class='v-{r['verdict']}'>{r['verdict']}</span></td></tr>")


HEAD = ("<tr><th></th><th class='l'>Setting</th><th>Trades</th><th>Win%</th>"
        "<th>Return%</th><th>MaxDrop%</th><th>Profit&divide;Pain</th><th>Blocks+</th><th>Verdict</th></tr>")


def build(results, manifest):
    now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')

    # 1. test plan
    plan = '<div class="card"><div class="pgrid">'
    for k, v in TP.PLAN.items():
        vals = " · ".join(str(v['fmt'](x)) for x in v['values'])
        plan += f'<span class="pname">{v["label"]}</span><span class="pvals">{vals}</span>'
        plan += f'<span class="pplain">{v["plain"]}</span>'
    plan += '</div>'
    plan += f'<div class="tot"><b>{TP.count()}</b> combinations per strategy, per instrument &nbsp;·&nbsp; every instrument gets the identical grid</div>'
    plan += '<div class="fx">' + ''.join(f'<span>{a}</span><span>{b}</span>' for a, b in TP.FIXED) + '</div></div>'

    # 2. strategies
    sg = '<div class="sgrid">'
    for name, code, status, desc in STRATEGIES:
        on = ' on' if status == 'validated' else ''
        pill = f'<span class="pill ok">{status}</span>' if status == 'validated' else f'<span class="pill">{status}</span>'
        sg += f'<div class="scard{on}"><p class="sn">{name}</p><p class="sd">{desc}</p>{pill}</div>'
    sg += '</div>'

    # 3. instruments
    ins = ''
    for res in results:
        blk_len = res['bars'] // TP.BLOCKS
        top = ''.join(row_html(r, i + 1) for i, r in enumerate(res['top']))
        if not top:
            top = '<tr><td colspan="9" style="text-align:left;color:var(--dim)">No setting produced enough trades to judge.</td></tr>'
        allrows = ''.join(row_html(r) for r in res['all_runs'])
        ins += f'''<div class="inst">
<div class="ihead"><span class="iname">{res['instrument']}</span>
<span class="imeta">{res['base_tf']} base · {res['htf1_tf']} + {res['htf2_tf']} filters · {res['span']} · {res['bars']:,} bars</span>
<span class="imeta">{res['n_holds']} of {TP.count()} settings hold</span></div>
<div class="ibody">
<table class="tt">{HEAD}{top}</table>
<div class="note">Ranked by how many independent time blocks stayed profitable, then by profit-to-pain — not by raw return. Each block here is about {blk_len:,} bars.</div>
<details class="all"><summary>All {len(res['all_runs'])} runs</summary><div class="scroll"><table class="tt">{HEAD}{allrows}</table></div></details>
</div></div>'''

    # 4. run page
    dt = ''
    for inst, v in manifest['instruments'].items():
        tfs = ', '.join(f"{k} ({v['timeframes'][k]['bars']:,})" for k in v['timeframes'])
        dt += f"<tr><td>{inst}</td><td>{v['venue']}</td><td>{tfs}</td></tr>"
    run = f'''<div class="card">
<ol class="steps">
<li><b>Upload the data</b> in chat and name the instrument. Any number of timeframe files — 4h, daily and weekly are the minimum this plan needs.</li>
<li><b>Files are stored in the repo</b> under <code>data/&lt;INSTRUMENT&gt;/</code> so they never need re-uploading.</li>
<li><b>The full plan runs</b> — {TP.count()} combinations per strategy — and every setting is checked across {TP.BLOCKS} independent time blocks.</li>
<li><b>This page regenerates</b> with a new instrument section: top 3 settings, plus the full grid underneath.</li>
</ol>
<div class="note">This page is the record, not the machine — it can't run the engine itself. Saying "run &lt;instrument&gt;" in chat is what starts a test.</div>
<p style="color:var(--dim);font:11.5px ui-monospace,monospace;margin:14px 0 0">Data currently stored</p>
<table class="dt">{dt}</table></div>'''

    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>3SHA Test Bench</title>
<style>{CSS}</style></head><body><div class="wrap">
<h1>3SHA Test Bench</h1>
<p class="lead">One fixed test plan, applied identically to every instrument. Settings are ranked by whether they survive across independent time periods — a high return that only works once ranks below a modest one that keeps working.</p>
<p class="gen">generated {now}</p>
<div class="sec"><p class="sech">1 · Test plan</p>{plan}</div>
<div class="sec"><p class="sech">2 · Strategies</p>{sg}</div>
<div class="sec"><p class="sech">3 · Instruments — top settings</p>{ins}</div>
<div class="sec"><p class="sech">4 · Run</p>{run}</div>
<p class="foot">Engine reconciled to TradingView to the penny (entries, position state, stop levels). Backtests only — no live trading result is implied.</p>
</div></body></html>'''


if __name__ == "__main__":
    manifest = json.load(open(os.path.join(DATA, "manifest.json")))
    results = []
    for inst in manifest['instruments']:
        print(f"  running {inst} ...")
        results.append(run_instrument(inst, verbose=False))
    out = os.path.join(REPO, "research")
    json.dump(results, open(os.path.join(out, "instrument_results.json"), "w"), indent=1)
    html = build(results, manifest)
    open(os.path.join(out, "index.html"), "w").write(html)
    print(f"wrote index.html ({len(html)//1024} KB) · {sum(len(r['all_runs']) for r in results)} total runs")
    for r in results:
        t = r['top'][0] if r['top'] else None
        print(f"  {r['instrument']:8s} holds={r['n_holds']:3d}  best={t['sha']+' '+t['exit'] if t else '-'} "
              f"r/DD={t['retdd'] if t else '-'} blocks={str(t['blocks'])+'/5' if t else '-'}")
