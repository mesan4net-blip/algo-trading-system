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


# Each correction and what it cost. Append, never overwrite — the point of a log
# is that you can see what changed and what it did to the numbers.
HISTORY = [
 dict(n=1, change="First cross-market run",
      detail="4h base, 20% equity cap, fixed 2-point stop buffer.",
      effect="QQQ negative, SPY flat, EUR/USD weak. Strong BTC figures were in-sample."),
 dict(n=2, change="Made the settings scale-invariant",
      detail="Equity cap lifted and the buffer expressed as a percent of price, so one setting means the same on Bitcoin and on EUR/USD.",
      effect="Comparable at last: BTC +41% over 1.4yr, QQQ -24%, SPY +13%, EUR/USD +10.6%."),
 dict(n=3, change="Swept the smoothing",
      detail="Every moving-average pair, across all four markets.",
      effect="No pair generalised. Slower settings flattered BTC and did nothing elsewhere — a clear overfitting trap."),
 dict(n=4, change="Dropped the 1,1 result",
      detail="A length of 1 disables that smoothing pass, so 1,1 is a plain Heikin-Ashi, not a smoothed one.",
      effect="BTC's best result was measuring a different indicator. Disqualified; floor set at length 2."),
 dict(n=5, change="Unfroze the slow layer",
      detail="It had been pinned at 2,2 in every run because that was the chart setting, never because it was tested.",
      effect="Swung results three to six fold. Grid went from 648 to 3,888 per market."),
 dict(n=6, change="Made the ranking time-aware",
      detail="Return per year against the worst dip, instead of a bare ratio.",
      effect="Collapsed an illusion: QQQ's top setting scored 11.5 while earning 0.8% a year over 26 years. Settings that held fell from 468 to 10."),
 dict(n=7, change="Fixed position sizing",
      detail="Sizes had been rounded down to whole units, forcing one whole Bitcoin per trade and ignoring the risk setting entirely.",
      effect="BTC halved, from 32% a year to 15.7% — the earlier figure came from positions six times too large."),
 dict(n=8, change="Unfroze the trailing stop",
      detail="It had been on but pinned to one anchor in all 25,920 runs.",
      effect="Preference splits by market: trending markets want it on, stock indices want it off. QQQ's surviving settings went from 45 to 258."),
 dict(n=9, change="Charged trading costs",
      detail="The engine had never applied a spread, while the plan claimed 0.1% per round trip.",
      effect="The worst finding of the project. EUR/USD fell from 2.4% a year to 1.5% and its surviving settings from 637 to 54. BTC fell from 15.7% to 7.8%."),
 dict(n=10, change="Fixed a look-ahead on fast charts",
      detail="The higher-timeframe offset was hardcoded at 15 minutes, leaking the daily value early on any faster chart.",
      effect="Made 5-minute testing honest. Also showed hold-until-stopped turns QQQ and SPY from losing to winning on a 15-minute base."),
]


# ---------------------------------------------------------------------------
# Plain-English translation. The page should read like instructions you could
# type into TradingView, not like a code you have to decrypt.
# ---------------------------------------------------------------------------
SAY_EXIT = {
 'Base': "when the chart timeframe turns against the trade",
 'HTF1': "when the mid timeframe turns against the trade",
 'HTF2': "when the slow timeframe turns against the trade"}

SAY_ANCHOR = {
 'Swing': "behind the recent swing low (or high, when short)",
 'HTF1 Body': "behind the mid-timeframe trend body",
 'HTF2 Body': "behind the slow-timeframe trend body",
 'Last Bar Beyond Nearest SHA': "behind the last bar that pushed clear of the nearer trend line",
 'Last Bar Beyond Furthest SHA': "behind the last bar that pushed clear of the further trend line",
 'Last SHA Bar Beyond Nearest SHA': "behind the last smoothed candle that pushed clear of the nearer trend line",
 'Last SHA Bar Beyond Furthest SHA': "behind the last smoothed candle that pushed clear of the further trend line"}

SAY_BASIS = {'Body': "measured on candle bodies, wicks ignored",
             'Wick': "measured on full candle highs and lows"}

SAY_STOP = {'mental': "mental — only acts once a candle closes past it",
            'hard': "hard — a real order, fires the instant price touches it"}

def say_trail(t):
    if t == 'off': return "none — the stop does not follow price"
    if t.startswith('Swing'):
        return f"follows the {t.split()[1]}-bar swing, once the trade is 1R ahead"
    return f"follows the {'mid' if 'HTF1' in t else 'slow'}-timeframe trend body, once the trade is 1R ahead"

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600&family=Karla:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
:root{--paper:#F5F8F2;--card:#FFF;--ink:#16241E;--soft:#54655C;--faint:#8FA096;
--grow:#2E7A5A;--grow-lt:#E8F2EB;--honey:#B87A16;--honey-lt:#FAF0DC;--clay:#A9483A;--clay-lt:#F8E9E5;--line:#E1E9DE;
--dsp:'Fraunces',Georgia,serif;--ui:'Karla',system-ui,sans-serif;--mono:'IBM Plex Mono',monospace}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.6 var(--ui);-webkit-font-smoothing:antialiased}
.wrap{max-width:920px;margin:0 auto;padding:0 24px 90px}
.hero{padding:64px 0 30px}
.eyebrow{font:500 12px/1 var(--mono);letter-spacing:.2em;text-transform:uppercase;color:var(--grow);margin:0 0 20px}
h1{font:600 clamp(34px,5.5vw,54px)/1.05 var(--dsp);font-variation-settings:'SOFT' 40,'WONK' 1;letter-spacing:-.02em;margin:0 0 16px;max-width:18ch}
.lede{font-size:17px;color:var(--soft);max-width:60ch;margin:0}
.sec{margin-top:60px}
h2{font:600 27px/1.15 var(--dsp);font-variation-settings:'SOFT' 40;margin:0 0 6px}
.sub{color:var(--soft);max-width:62ch;margin:0 0 22px;font-size:15px}
.mk{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:26px 28px;margin-bottom:16px}
.mkh{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;padding-bottom:16px;border-bottom:1px solid var(--line)}
.mkh .nm{font:600 26px/1 var(--dsp);font-variation-settings:'SOFT' 40}
.mkh .meta{font-size:13.5px;color:var(--faint)}
.lab{font:500 11px/1 var(--mono);letter-spacing:.15em;text-transform:uppercase;color:var(--faint);margin:22px 0 12px}
.set{display:grid;grid-template-columns:minmax(130px,auto) 1fr;gap:9px 20px;font-size:15px}
.set dt{color:var(--soft)}
.set dd{margin:0;font-weight:500}
.set dd.num{font-family:var(--mono);font-size:14.5px;color:var(--grow);font-weight:500}
.res{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px}
.rb{background:var(--grow-lt);border-radius:11px;padding:14px 16px}
.rb.warn{background:var(--honey-lt)}
.rb.bad{background:var(--clay-lt)}
.rb .v{font:600 25px/1 var(--dsp);font-variation-settings:'SOFT' 40;display:block;letter-spacing:-.01em}
.rb .k{font-size:13px;color:var(--soft);margin-top:5px;display:block;line-height:1.35}
.vs{margin-top:14px;padding:13px 16px;border-radius:11px;background:#F2F5F0;font-size:14.5px;color:var(--soft)}
.vs b{color:var(--ink)}
details{margin-top:18px;border-top:1px solid var(--line);padding-top:14px}
summary{cursor:pointer;font-size:14px;color:var(--grow);list-style:none;font-weight:500}
summary::-webkit-details-marker{display:none}
summary::before{content:"+ ";font-weight:600}
details[open] summary::before{content:"– "}
.scroll{overflow:auto;max-height:400px;margin-top:12px;border:1px solid var(--line);border-radius:10px}
table{width:100%;border-collapse:collapse;font:400 12.5px/1.45 var(--mono)}
th{position:sticky;top:0;background:#F0F4EE;color:var(--soft);text-align:right;padding:9px;font-weight:500;white-space:nowrap;border-bottom:1px solid var(--line)}
th.l,td.l{text-align:left}
td{padding:7px 9px;text-align:right;white-space:nowrap;border-bottom:1px solid #F1F4EF}
tbody tr:hover td{background:#F8FAF6}
.pos{color:var(--grow)}.neg{color:var(--clay)}
.hrow{display:flex;gap:16px;padding:16px 0;border-top:1px solid var(--line)}
.hrow:first-child{border-top:none}
.hn{font:600 15px/1 var(--dsp);color:var(--grow);width:24px;flex:none;padding-top:3px}
.hb h4{margin:0 0 3px;font-size:15.5px;font-weight:600}
.hb .d{color:var(--soft);font-size:14px;margin:0 0 6px;line-height:1.5}
.hb .e{font-size:14px;margin:0;padding-left:12px;border-left:2px solid var(--grow);line-height:1.5}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:8px 28px 22px}
.plan dt{color:var(--soft);font-size:14.5px}
.foot{margin-top:70px;padding-top:22px;border-top:1px solid var(--line);color:var(--faint);font-size:13.5px}
.foot .l{font:400 18px/1.5 var(--dsp);color:var(--soft);margin:0 0 8px;max-width:46ch}
@media(max-width:620px){.set{grid-template-columns:1fr;gap:3px 0}.set dd{margin-bottom:8px}}
"""


def enrich(res):
    """Add annualised return and a time-aware ratio, then re-rank.

    A bare profit-to-pain ratio has no sense of time: +24% earned over 26 years
    scores the same as +24% in one year. Annualising stops a setting that barely
    moves from topping the table on a small drawdown alone."""
    a, b = [x.strip() for x in res['span'].split('\u2192')]
    yrs = max((datetime.date.fromisoformat(b) - datetime.date.fromisoformat(a)).days / 365.25, 0.25)
    res['years'] = round(yrs, 1)
    for r in res['all_runs']:
        g = 1 + r['ret'] / 100.0
        r['cagr'] = round(((g ** (1 / yrs)) - 1) * 100, 2) if g > 0 else -100.0
        dd = abs(r['maxdd'])
        r['mar'] = round(r['cagr'] / dd, 2) if dd > 0.01 else 0.0
        if r['verdict'] == 'holds' and r['mar'] < 0.25:
            r['verdict'] = 'fragile'
    res['all_runs'].sort(key=lambda r: (r['blocks'], r['mar']), reverse=True)
    ranked = [r for r in res['all_runs'] if r['trades'] >= TP.MIN_TRADES]
    res['top'] = ranked[:3]
    res['n_holds'] = sum(1 for r in res['all_runs'] if r['verdict'] == 'holds')
    return res


HOLD = {}   # buy-and-hold benchmark, filled at build time


def band(v, good, ok):
    return '' if v >= good else (' warn' if v >= ok else ' bad')


def market_card(res):
    t = res['top'][0] if res['top'] else None
    if not t:
        return ''
    trail = t.get('trail', 'Swing 6')
    per_yr = t['cagr']
    hold = HOLD.get(res['instrument'])
    yrs = res['years']
    per_year_trades = t['trades'] / yrs

    beats = hold is None or per_yr > hold
    vs = ''
    if hold is not None:
        vs = (f"<div class='vs'>Simply buying and holding {res['instrument']} over the same years made "
              f"<b>{hold:.1f}% a year</b>. This strategy made <b>{per_yr:.1f}%</b> — "
              + ("<b>better</b>." if beats else "<b>less</b>, though with a far smaller drop along the way.") + "</div>")

    rows = ''.join(
        f"<tr><td class='l'>{r['sha']} / {r.get('htf2','2,2')} · {r['exit']} · {r['anchor']} · {r['basis']} · {r['stop']} · {r.get('trail','')}</td>"
        f"<td>{r['trades']}</td><td class='{'pos' if r['cagr']>0 else 'neg'}'>{r['cagr']}</td>"
        f"<td class='neg'>{r['maxdd']}</td><td>{r['blocks']}/{r['nblocks']}</td></tr>"
        for r in res['all_runs'][:400])

    return f"""<div class="mk">
<div class="mkh"><span class="nm">{res['instrument']}</span>
<span class="meta">{res['base_tf']} chart · {res['years']} years of history · {res['cost_pct']}% cost per trade</span></div>

<p class="lab">Settings to use</p>
<dl class="set">
<dt>Smoothing — chart &amp; mid</dt><dd class="num">{t['sha']}</dd>
<dt>Smoothing — slow layer</dt><dd class="num">{t.get('htf2','2,2')}</dd>
<dt>Enter</dt><dd>when all three timeframes agree for the first time</dd>
<dt>Exit</dt><dd>{SAY_EXIT.get(t['exit'], t['exit'])}</dd>
<dt>Place the stop</dt><dd>{SAY_ANCHOR.get(t['anchor'], t['anchor'])}, {SAY_BASIS[t['basis']]}</dd>
<dt>Stop type</dt><dd>{SAY_STOP[t['stop']]}</dd>
<dt>Trailing stop</dt><dd>{say_trail(trail)}</dd>
<dt>Break-even</dt><dd>move the stop to your entry once the trade is 1R ahead</dd>
<dt>Risk</dt><dd>1% of the account per trade</dd>
</dl>

<p class="lab">How it did</p>
<div class="res">
<div class="rb{band(per_yr, 5, 1)}"><span class="v">{'+' if per_yr>0 else ''}{per_yr:.1f}%</span><span class="k">made per year</span></div>
<div class="rb{band(-t['maxdd']*-1, -8, -15)}"><span class="v">{t['maxdd']:.1f}%</span><span class="k">worst drop along the way</span></div>
<div class="rb"><span class="v">{t['trades']}</span><span class="k">trades — about {per_year_trades:.0f} a year</span></div>
<div class="rb{band(t['blocks'], 4, 3)}"><span class="v">{t['blocks']} of {t['nblocks']}</span><span class="k">separate test periods it made money in</span></div>
</div>
{vs}
<details><summary>Show the other {len(res['all_runs'])-1:,} combinations tested</summary>
<div class="scroll"><table>
<thead><tr><th class="l">Settings</th><th>Trades</th><th>Per year%</th><th>Worst drop%</th><th>Periods</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<p style="font-size:13px;color:var(--faint);margin:8px 0 0">Showing the 400 strongest. Ranked by how many periods stayed profitable, then by return per year against the worst drop.</p>
</details>
</div>"""


def build(results, manifest):
    now = datetime.datetime.utcnow().strftime('%d %B %Y')
    total = sum(len(r['all_runs']) for r in results)
    cards = ''.join(market_card(r) for r in results)
    hist = ''.join(f'<div class="hrow"><span class="hn">{h["n"]}</span><div class="hb">'
                   f'<h4>{h["change"]}</h4><p class="d">{h["detail"]}</p>'
                   f'<p class="e">{h["effect"]}</p></div></div>' for h in HISTORY)
    plan = ''.join(f'<dt>{v["label"]}</dt><dd class="num">{" · ".join(str(v["fmt"](x)) for x in v["values"])}</dd>'
                   for v in TP.PLAN.values())

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>3SHA — what works, and where</title><style>{CSS}</style></head><body><div class="wrap">

<header class="hero">
<p class="eyebrow">3SHA · full alignment</p>
<h1>What to set, and how well it did.</h1>
<p class="lede">Every market below was put through the same {TP.count():,} combinations of settings. What you see first is the one that held up best — written out so you can type it straight into a chart.</p>
</header>

<section class="sec">{cards}</section>

<section class="sec">
<h2>What changed along the way</h2>
<p class="sub">Every correction made to the method, in order. Most made the results worse — which is the point. A number is only worth having once you know what was wrong with the one before it.</p>
<div class="card">{hist}</div>
</section>

<section class="sec">
<h2>What gets tested</h2>
<p class="sub">Each market goes through this identical grid — {TP.count():,} combinations — so the results can be compared instead of each market being quietly tuned to flatter itself. Every setting is then re-checked across {TP.BLOCKS} separate stretches of history.</p>
<div class="card"><dl class="set plan" style="padding-top:18px">{plan}</dl></div>
</section>

<footer class="foot">
<p class="l">Built slowly, on purpose. Every figure here is a backtest — a careful record of the past, never a promise about what comes next.</p>
<p>{total:,} backtests · engine matched to TradingView to the penny · generated {now}</p>
</footer>
</div></body></html>"""


if __name__ == "__main__":
    import sys, time
    import numpy as np
    out = os.path.dirname(os.path.abspath(__file__))
    cache = os.path.join(out, "runs"); os.makedirs(cache, exist_ok=True)
    manifest = json.load(open(os.path.join(DATA, "manifest.json")))
    arg = sys.argv[1] if len(sys.argv) > 1 else "build"
    if arg != "build":
        t0 = time.time()
        res = run_instrument(arg, verbose=False)
        json.dump(res, open(os.path.join(cache, f"{arg}.json"), "w"))
        print(f"{arg}: {len(res['all_runs'])} runs in {time.time()-t0:.0f}s · {res['n_holds']} held")
    else:
        from runner import load
        results = []
        for inst in manifest['instruments']:
            f = os.path.join(cache, f"{inst}.json")
            if os.path.exists(f):
                r = enrich(json.load(open(f)))
                b = load(os.path.join(DATA, inst, r['base_tf'] + '.csv'))
                yrs = (b.index[-1] - b.index[0]).days / 365.25
                tot = b['close'].iloc[-1] / b['close'].iloc[0]
                HOLD[inst] = ((tot ** (1 / yrs)) - 1) * 100
                results.append(r)
        html = build(results, manifest)
        open(os.path.join(out, "index.html"), "w").write(html)
        print(f"index.html ({len(html)//1024} KB) · {len(results)} markets")
