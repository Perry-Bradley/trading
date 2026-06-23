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
import threading
import time

from flask import Flask, jsonify, redirect, render_template_string, request, send_file

import config
from src import engine

app = Flask(__name__)
LAST_TICK = config.DATA_DIR / "last_tick.json"

TARGET_R = float(os.environ.get("TARGET_R", "2"))
TF = os.environ.get("TF", "H4")
BIAS_TF = os.environ.get("BIAS_TF", "D1")
BROKER = os.environ.get("BROKER", "paper")

# ---------------------------------------------------------------------------
# Self-seeding: Railway's disk is ephemeral, so a fresh container has no data or
# model. On startup we fetch data + bootstrap the model in a background thread so
# the dashboard heals itself (~1-2 min) without anyone clicking. Polled endpoints
# return [] (never 500) while SEED["state"] == "warming".
# ---------------------------------------------------------------------------
SEED = {"state": "idle"}
_seed_lock = threading.Lock()


def _model_path():
    return config.ROOT / "models" / f"online_policy_{int(TARGET_R)}r.joblib"


def _seeded() -> bool:
    return SEED["state"] == "ready" or _model_path().exists()


def _seed() -> None:
    with _seed_lock:
        if SEED["state"] == "warming":
            return
        SEED["state"] = "warming"
    try:
        from src.data import fetch
        from src.ml.online import OnlinePolicy
        for pr in config.PAIRS:
            for t in {TF, BIAS_TF}:
                if not (config.DATA_DIR / f"{pr}_{t}.parquet").exists():
                    try:
                        fetch.save(pr, t)
                    except Exception as e:  # noqa: BLE001
                        print(f"  (seed fetch {pr} {t} failed: {e})")
        if not _model_path().exists():
            OnlinePolicy.bootstrap(TARGET_R)
        SEED["state"] = "ready"
        print("[seed] ready")
    except Exception as e:  # noqa: BLE001
        SEED["state"] = f"error: {e}"
        print(f"[seed] {SEED['state']}")


def _ensure_seeding() -> None:
    if SEED["state"] in ("warming", "ready"):
        return
    if _model_path().exists():
        SEED["state"] = "ready"
        return
    threading.Thread(target=_seed, daemon=True).start()


_ensure_seeding()   # kick off on import (cold start)

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
    html = """<!doctype html><html><head><meta charset=utf-8><title>MSNR API</title>
<meta name=viewport content="width=device-width,initial-scale=1">
<style>body{font-family:system-ui,Segoe UI,Arial;background:#0a0d12;color:#e6edf3;max-width:680px;margin:48px auto;padding:0 20px;line-height:1.65}
h1{font-size:22px;margin-bottom:2px}a{color:#3b82f6;text-decoration:none}code{background:#161c25;padding:2px 7px;border-radius:6px;font-size:13px}
.ok{color:#22c55e}.muted{color:#8b97a7;font-size:14px}li{margin:5px 0}</style></head><body>
<h1>MSNR Assistant — API</h1>
<p class=ok>● API running &middot; {{tf}}/{{bias_tf}} &middot; {{tr}}R &middot; {{broker}}</p>
<p class=muted>This service is the trading engine + JSON API. The full dashboard UI is the
separate <b>Next.js app</b> (the <code>web/</code> folder) — deploy it as its own Railway
service and set <code>NEXT_PUBLIC_API_URL</code> to this URL.</p>
<h3>Endpoints</h3>
<ul>
<li><a href="/health">/health</a> &middot; <a href="/api/config">/api/config</a> &middot;
<a href="/api/status">/api/status</a> &middot; <a href="/api/journal">/api/journal</a></li>
<li><code>POST /api/tick?refresh=1</code> — run a tick (first call fetches data + bootstraps the model; ~1-2 min)</li>
</ul>
<p class=muted>Seed it now: <code>curl -X POST "{{base}}/api/tick?refresh=1"</code></p>
</body></html>"""
    return render_template_string(html, base=request.host_url.rstrip("/"),
                                  tf=TF, bias_tf=BIAS_TF, tr=int(TARGET_R), broker=BROKER)


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


def _reason(s: dict) -> dict:
    """Human-readable 'why' for a signal, from its causal features (the SMC story)."""
    f = s.get("features", {})
    bias = "bullish" if s["direction"] == "long" else "bearish"
    kind = "demand (support)" if s["direction"] == "long" else "supply (resistance)"
    conf = []
    if f.get("choch_recent"):
        conf.append("CHoCH (structure shifted with the bias)")
    if f.get("sweep_recent"):
        conf.append("liquidity sweep (stops grabbed before the move)")
    if f.get("ob_conf"):
        conf.append("order block at the zone")
    if f.get("fvg_conf"):
        conf.append("fair value gap nearby")
    if f.get("rej_strength", 0) >= 0.6:
        conf.append("strong rejection candle")
    why = (f"{bias.title()} {s['tf']} bias into a fresh {kind} SNR level, confirmed by a "
           f"rejection candle" + (". Confluences: " + ", ".join(conf) if conf else "."))
    return {"why": why, "confluences": conf, "tf": s.get("tf", TF)}


def _scan_only() -> list:
    """Current signals across pairs (read-only) for display, scored by the policy.
    Never raises — returns [] until data + model are seeded."""
    if not _seeded():
        return []
    try:
        from src import backtest
        from src.ml.online import OnlinePolicy, vec
        pol = OnlinePolicy.load_or_bootstrap(TARGET_R)
    except Exception:  # noqa: BLE001
        return []
    out = []
    for pr in config.PAIRS:
        try:
            # scan a wider recent window so the page shows recent setups (each tagged
            # with its time), not only triggers on the last 3 bars.
            for s in backtest.signals(pr, TF, BIAS_TF, TARGET_R, lookback=40):
                p = pol.proba(vec(s["features"]))
                s["conf"], s["size"] = p, pol.size(p)
                s["time"] = str(s.get("time", ""))[:16]
                s.update(_reason(s))
                out.append({k: s[k] for k in ("pair", "direction", "entry", "stop", "target",
                                              "conf", "size", "features", "why", "confluences",
                                              "tf", "time")})
        except Exception:  # noqa: BLE001
            continue
        except Exception:  # noqa: BLE001
            continue
    return out


_OVERVIEW_CACHE = {"t": 0.0, "data": []}


def _overview() -> list:
    """Per-pair bias + signal flag, cached 60s (detectors are not free)."""
    if not _seeded():
        return []
    if time.time() - _OVERVIEW_CACHE["t"] < 60 and _OVERVIEW_CACHE["data"]:
        return _OVERVIEW_CACHE["data"]
    from src import backtest
    out = []
    for pr in config.PAIRS:
        try:
            out.append(backtest.overview(pr, TF, BIAS_TF, TARGET_R))
        except Exception:  # noqa: BLE001
            out.append({"pair": pr, "bias": "flat", "price": 0.0, "signal": False})
    _OVERVIEW_CACHE.update(t=time.time(), data=out)
    return out


# ---------------------------------------------------------------------------
# JSON API (consumed by the Next.js frontend in web/)
# ---------------------------------------------------------------------------
@app.after_request
def _cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = os.environ.get("CORS_ORIGIN", "*")
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


@app.route("/health")
def health():
    return jsonify({"ok": True})


@app.route("/api/config")
def api_config():
    from src.notify import telegram_configured
    return jsonify({"pairs": config.PAIRS, "tf": TF, "bias_tf": BIAS_TF,
                    "target_r": TARGET_R, "breakeven": 1 / (1 + TARGET_R),
                    "broker": BROKER, "telegram": telegram_configured(),
                    "seed_state": SEED["state"]})


@app.route("/api/status")
def api_status():
    _ensure_seeding()
    st = _load_last()
    from src import journal
    st["track_record"] = journal.track_record()
    st["seed_state"] = SEED["state"]
    return jsonify(st)


@app.route("/api/signals")
def api_signals():
    _ensure_seeding()
    return jsonify({"signals": _scan_only(), "seed_state": SEED["state"]})


@app.route("/api/overview")
def api_overview():
    _ensure_seeding()
    return jsonify({"overview": _overview(), "seed_state": SEED["state"]})


@app.route("/api/journal")
def api_journal():
    from src import journal
    return jsonify({"rows": journal.recent(int(request.args.get("n", 60)))})


@app.route("/api/tick", methods=["POST", "OPTIONS"])
def api_tick():
    if request.method == "OPTIONS":
        return ("", 204)
    refresh = request.values.get("refresh") == "1"
    st = engine.tick(BROKER, TF, BIAS_TF, TARGET_R, refresh=refresh)
    SEED["state"] = "ready"                       # a successful tick means we're seeded
    _OVERVIEW_CACHE["t"] = 0.0                     # force overview refresh
    import datetime as _dt
    sigs = sorted(_scan_only(), key=lambda s: -s.get("conf", 0))
    st["signals"] = sigs[:20]
    st["overview"] = _overview()
    st["seed_state"] = SEED["state"]
    st["when"] = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    LAST_TICK.write_text(json.dumps(st, indent=2, default=str))
    return jsonify(st)


_DATA_CACHE = {"t": 0.0, "data": None}


@app.route("/api/data")
def api_data():
    """Data-pipeline view: bars + date range per pair/timeframe (cached 5 min)."""
    if time.time() - _DATA_CACHE["t"] < 300 and _DATA_CACHE["data"]:
        return jsonify(_DATA_CACHE["data"])
    import pandas as pd
    from src.data import fetch as _fetch
    rows = []
    for pr in config.PAIRS:
        tfs = {}
        for tf in config.TIMEFRAMES:
            f = config.DATA_DIR / f"{pr}_{tf}.parquet"
            if f.exists():
                try:
                    idx = pd.read_parquet(f, columns=["close"]).index
                    tfs[tf] = {"bars": len(idx), "start": str(idx.min().date()),
                               "end": str(idx.max().date())}
                except Exception:  # noqa: BLE001
                    tfs[tf] = None
            else:
                tfs[tf] = None
        src = _fetch.source_for(pr)
        live = src in ("binance", "twelvedata")
        rows.append({"pair": pr, "tf": tfs, "source": src, "live": live})
    out = {"pairs": rows, "timeframes": list(config.TIMEFRAMES),
           "ladder": "D1->H4->H1->M30", "source": "yfinance", "seed_state": SEED["state"]}
    _DATA_CACHE.update(t=time.time(), data=out)
    return jsonify(out)


@app.route("/api/model")
def api_model():
    """Model internals: features, learned weights, updates, CV AUC."""
    from src.ml.dataset import FEATURES
    info = {"features": FEATURES, "target_r": TARGET_R, "breakeven": 1 / (1 + TARGET_R),
            "n_updates": 0, "coef": [], "cv_auc": None, "seed_state": SEED["state"]}
    if _seeded():
        try:
            from src.ml.online import OnlinePolicy
            pol = OnlinePolicy.load_or_bootstrap(TARGET_R)
            info["n_updates"] = pol.n_updates
            coef = pol.clf.coef_[0]
            info["coef"] = sorted(
                [{"feature": f, "weight": float(c)} for f, c in zip(FEATURES, coef)],
                key=lambda x: -abs(x["weight"]))
        except Exception:  # noqa: BLE001
            pass
    import joblib
    mf = config.ROOT / "models" / f"msnr_filter_{int(TARGET_R)}r.joblib"
    if mf.exists():
        try:
            info["cv_auc"] = joblib.load(mf).get("cv_auc")
        except Exception:  # noqa: BLE001
            pass
    return jsonify(info)


_BT_CACHE = {}


@app.route("/api/backtest")
def api_backtest():
    """On-demand backtest for a pair (or all). Cached per pair for 10 min."""
    if not _seeded():
        return jsonify({"seed_state": SEED["state"], "results": []})
    from src import backtest
    pairs = [request.args.get("pair")] if request.args.get("pair") else config.PAIRS
    results = []
    for pr in pairs:
        if not pr:
            continue
        key = f"{pr}:{TF}:{BIAS_TF}:{TARGET_R}"
        cached = _BT_CACHE.get(key)
        if cached and time.time() - cached[0] < 600:
            results.append(cached[1]); continue
        try:
            m = backtest.run(pr, TF, BIAS_TF, target_r=TARGET_R)
            row = {k: m[k] for k in ("pair", "trades", "wins", "losses", "win_rate",
                                     "breakeven_wr", "expectancy_r", "total_r",
                                     "avg_win_r", "avg_loss_r", "profit_factor", "max_dd_r")}
            row["profit_factor"] = None if row["profit_factor"] == float("inf") else row["profit_factor"]
            _BT_CACHE[key] = (time.time(), row)
            results.append(row)
        except Exception as e:  # noqa: BLE001
            results.append({"pair": pr, "error": str(e)})
    return jsonify({"results": results, "tf": TF, "bias_tf": BIAS_TF, "target_r": TARGET_R})


_ANALYSIS_CACHE = {}


@app.route("/api/analysis")
def api_analysis():
    """SMC analysis for a pair: bias, structure breaks (BOS/CHoCH), fresh SNR,
    order blocks, fair value gaps, and liquidity sweeps (BSL/SSL) — with levels."""
    pair = request.args.get("pair", config.PAIRS[0])
    if not _seeded():
        return jsonify({"seed_state": SEED["state"]})
    c = _ANALYSIS_CACHE.get(pair)
    if c and time.time() - c[0] < 60:
        return jsonify(c[1])
    from src.data.fetch import load
    from src.detectors import smc
    from src.detectors import snr as snrmod
    from src.detectors import structure as stmod
    df = load(pair, TF)
    last = len(df) - 1
    res = stmod.analyze(df)
    breaks = [{"type": b.kind, "dir": b.direction, "level": round(b.level, 5),
               "time": str(df.index[b.idx])[:16]} for b in res["breaks"][-6:]][::-1]
    bias = "long" if (breaks and breaks[0]["dir"] == "up") else "short" if breaks else "flat"
    fresh = [{"kind": z.kind, "top": round(z.top, 5), "bottom": round(z.bottom, 5),
              "time": str(z.anchor_time)[:16]}
             for z in snrmod.detect(df) if z.is_fresh_at(last) and z.is_valid_at(last)][-8:][::-1]
    obs = [{"kind": o.kind, "top": round(o.top, 5), "bottom": round(o.bottom, 5),
            "time": str(o.time)[:16]} for o in smc.order_blocks(df)[-6:]][::-1]
    fvgs = [{"kind": f.kind, "top": round(f.top, 5), "bottom": round(f.bottom, 5),
             "time": str(f.time)[:16]} for f in smc.fair_value_gaps(df)[-6:]][::-1]
    sweeps = [{"side": "BSL" if s.direction == "bsl" else "SSL", "level": round(s.level, 5),
               "time": str(s.time)[:16]} for s in smc.liquidity_sweeps(df)[-6:]][::-1]
    out = {"pair": pair, "tf": TF, "bias_tf": BIAS_TF, "price": round(float(df["close"].iat[-1]), 5),
           "bias": bias, "breaks": breaks, "fresh_snr": fresh, "order_blocks": obs,
           "fvgs": fvgs, "sweeps": sweeps}
    _ANALYSIS_CACHE[pair] = (time.time(), out)
    return jsonify(out)


@app.route("/api/chart")
def api_chart():
    """Server-rendered annotated chart PNG (SNR zones + structure + rejections)."""
    pair = request.args.get("pair", config.PAIRS[0])
    tf = request.args.get("tf", TF)
    if pair not in config.PAIRS or tf not in config.TIMEFRAMES:
        return ("bad params", 400)
    if not _seeded():
        return ("warming", 503)
    try:
        from src.viz.plot_chart import plot
        path = plot(pair, tf, bars=140, left=3, right=3)
        return send_file(path, mimetype="image/png")
    except Exception as e:  # noqa: BLE001
        return (str(e), 500)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), debug=False)
