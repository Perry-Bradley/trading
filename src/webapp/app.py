"""Web dashboard for the MSNR assistant (deployable to Railway).

Routes:
  GET  /            dashboard: NAV, open positions, recent closes, latest signals, model status
  POST /tick        run one engine tick (optionally ?refresh=1 to re-pull data), then redirect
  GET  /api/status  the last tick status as JSON

Run locally:   python -m src.webapp.app           (then open http://localhost:8000)
On Railway:    gunicorn -b 0.0.0.0:$PORT src.webapp.app:app   (see Procfile)

The dashboard reads cached state so page loads are fast; learning/trading happens
only when a tick runs (button, or a scheduled hit to /tick).
"""
from __future__ import annotations

import json
import os

from flask import Flask, jsonify, redirect, render_template_string, request

import config
from src import engine

app = Flask(__name__)
LAST_TICK = config.DATA_DIR / "last_tick.json"

TARGET_R = float(os.environ.get("TARGET_R", "2"))
TF = os.environ.get("TF", "H4")
BIAS_TF = os.environ.get("BIAS_TF", "D1")
BROKER = os.environ.get("BROKER", "paper")

PAGE = """
<!doctype html><html><head><meta charset="utf-8"><title>MSNR Assistant</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
 body{font-family:system-ui,Segoe UI,Arial;background:#0e1116;color:#e6edf3;margin:0;padding:24px}
 h1{font-size:20px;margin:0 0 4px} .sub{color:#8b949e;font-size:13px;margin-bottom:18px}
 .cards{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:20px}
 .card{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:14px 18px;min-width:150px}
 .card .v{font-size:22px;font-weight:700} .card .l{color:#8b949e;font-size:12px}
 table{width:100%;border-collapse:collapse;margin:10px 0 26px;font-size:13px}
 th,td{text-align:left;padding:7px 10px;border-bottom:1px solid #21262d}
 th{color:#8b949e;font-weight:600} .long{color:#3fb950}.short{color:#f85149}
 .btn{background:#238636;color:#fff;border:0;padding:10px 16px;border-radius:8px;font-size:14px;cursor:pointer;margin-right:8px}
 .btn.alt{background:#1f6feb} .pill{padding:2px 8px;border-radius:20px;font-size:11px;background:#30363d}
 .warn{color:#d29922;font-size:12px;margin-top:18px}
</style></head><body>
<h1>MSNR Trading Assistant</h1>
<div class="sub">{{tf}} entry / {{bias}} bias &middot; target {{tr}}R &middot; breakeven {{be}}% &middot; broker: {{broker}}</div>
<div class="cards">
  <div class="card"><div class="v">{{nav}}</div><div class="l">account NAV</div></div>
  <div class="card"><div class="v">{{nupd}}</div><div class="l">trades learned from</div></div>
  <div class="card"><div class="v">{{nopen}}</div><div class="l">open positions</div></div>
  <div class="card"><div class="v">{{nsig}}</div><div class="l">live signals</div></div>
</div>
<form method="post" action="/tick" style="margin-bottom:8px">
  <button class="btn">Run tick</button>
  <button class="btn alt" name="refresh" value="1">Run tick + refresh data</button>
</form>

<h3>Live signals</h3>
<table><tr><th>pair</th><th>dir</th><th>entry</th><th>SL</th><th>TP</th><th>R:R</th><th>conf</th><th>size</th></tr>
{% for s in signals %}<tr><td>{{s.pair}}</td><td class="{{s.direction}}">{{s.direction|upper}}</td>
<td>{{'%.5f'|format(s.entry)}}</td><td>{{'%.5f'|format(s.stop)}}</td><td>{{'%.5f'|format(s.target)}}</td>
<td>1:{{tr}}</td><td>{{'%.1f'|format(s.conf*100)}}%</td><td>{{'%.2f'|format(s.size)}}x</td></tr>
{% else %}<tr><td colspan="8">no fresh signals on last tick</td></tr>{% endfor %}</table>

<h3>Open positions</h3>
<table><tr><th>pair</th><th>dir</th><th>entry</th><th>SL</th><th>TP</th><th>size</th></tr>
{% for p in open_positions %}<tr><td>{{p.pair}}</td><td class="{{p.direction}}">{{p.direction|upper}}</td>
<td>{{'%.5f'|format(p.entry)}}</td><td>{{'%.5f'|format(p.stop)}}</td><td>{{'%.5f'|format(p.target)}}</td>
<td>{{'%.2f'|format(p.size)}}x</td></tr>{% else %}<tr><td colspan="6">none</td></tr>{% endfor %}</table>

<h3>Recently closed</h3>
<table><tr><th>pair</th><th>dir</th><th>outcome</th><th>R</th><th>P&amp;L</th></tr>
{% for c in closed %}<tr><td>{{c.pair}}</td><td class="{{c.direction}}">{{c.direction|upper}}</td>
<td>{{c.outcome}}</td><td>{{'%.2f'|format(c.r or 0)}}</td><td>{{'%+.2f'|format(c.pnl)}}</td></tr>
{% else %}<tr><td colspan="5">none yet</td></tr>{% endfor %}</table>

<div class="warn">Decision-support only — not financial advice. Paper-trade before risking real capital.
Last tick: {{when}}</div>
</body></html>
"""


def _load_last() -> dict:
    if LAST_TICK.exists():
        return json.loads(LAST_TICK.read_text())
    return {"nav": 0, "n_updates": 0, "breakeven": 1 / (1 + TARGET_R),
            "open_positions": [], "closed": [], "opened": [], "signals": [], "when": "never"}


@app.route("/")
def index():
    st = _load_last()
    return render_template_string(
        PAGE, tf=TF, bias=BIAS_TF, tr=int(TARGET_R), be=round(st["breakeven"] * 100, 1),
        broker=BROKER, nav=f"{st['nav']:.2f}", nupd=st["n_updates"],
        nopen=len(st["open_positions"]), nsig=len(st.get("signals", [])),
        signals=st.get("signals", []), open_positions=st["open_positions"],
        closed=st["closed"][-10:][::-1] if st["closed"] else [], when=st.get("when", "never"))


@app.route("/tick", methods=["POST", "GET"])
def do_tick():
    refresh = request.values.get("refresh") == "1"
    st = engine.tick(BROKER, TF, BIAS_TF, TARGET_R, refresh=refresh)
    # cache the live signals for display (highest confidence first)
    sigs = sorted(st.get("opened", []) + _scan_only(), key=lambda s: -s.get("conf", 0))
    import datetime as _dt
    st["signals"] = sigs[:12]
    st["when"] = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    LAST_TICK.write_text(json.dumps(st, indent=2, default=str))
    return redirect("/")


def _scan_only() -> list:
    """Current signals across pairs (read-only) for display, scored by the policy."""
    from src import backtest
    from src.ml.online import OnlinePolicy, vec
    pol = OnlinePolicy.load_or_bootstrap(TARGET_R)
    out = []
    for pr in config.PAIRS:
        try:
            for s in backtest.signals(pr, TF, BIAS_TF, TARGET_R, lookback=3):
                p = pol.proba(vec(s["features"]))
                s["conf"], s["size"] = p, pol.size(p)
                out.append({k: s[k] for k in ("pair", "direction", "entry", "stop",
                                              "target", "conf", "size")})
        except FileNotFoundError:
            continue
    return out


@app.route("/api/status")
def api_status():
    return jsonify(_load_last())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), debug=False)
