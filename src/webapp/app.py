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
from src.webapp.news import get_high_impact_news, is_news_embargo

app = Flask(__name__)
LAST_TICK = config.DATA_DIR / "last_tick.json"

TARGET_R = float(os.environ.get("TARGET_R", "3"))   # MSNR is high-R:R; 3R default (set 5 for 5:1)
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
    return config.MODELS_DIR / f"online_policy_{int(TARGET_R)}r.joblib"


def _seeded() -> bool:
    if SEED["state"] == "ready": return True
    if not _model_path().exists(): return False
    # Model exists, but do we have the multi-TF data files?
    pr = config.PAIRS[0]
    return (config.DATA_DIR / f"{pr}_H1.parquet").exists() and (config.DATA_DIR / f"{pr}_M30.parquet").exists()


def _seed() -> None:
    with _seed_lock:
        if SEED["state"] == "warming":
            return
        SEED["state"] = "warming"
    try:
        from src.data import fetch
        from src.ml.online import OnlinePolicy
        # Fetch all timeframes needed: bias TF + entry TFs (H4, H1, M30)
        entry_tfs = ["H4", "H1", "M30"]
        for pr in config.PAIRS:
            for t in {BIAS_TF} | set(entry_tfs):
                if not (config.DATA_DIR / f"{pr}_{t}.parquet").exists():
                    try:
                        fetch.save(pr, t)
                    except Exception as e:  # noqa: BLE001
                        print(f"  (seed fetch {pr} {t} failed: {e})")
        if not _model_path().exists():
            OnlinePolicy.bootstrap(TARGET_R)
        SEED["state"] = "ready"
        print("[seed] ready")
        from src.data.sources import finnhub_ws
        finnhub_ws.start_background()
        threading.Thread(target=_post_seed_tick, daemon=True, name="seed-tick").start()
    except Exception as e:  # noqa: BLE001
        SEED["state"] = f"error: {e}"
        print(f"[seed] {SEED['state']}")


def _post_seed_tick() -> None:
    """First tick right after seed so dashboard + journal populate without waiting."""
    try:
        _run_and_cache(refresh=False)
        print("[seed] initial tick done")
    except Exception as e:  # noqa: BLE001
        print(f"[seed] initial tick failed: {e}")


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
<td>1:{{'%.2f'|format(s.rr)}}</td><td>{{'%.1f'|format(s.conf*100)}}%</td><td>{{'%.2f'|format(s.size)}}x</td></tr>
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

<div style="margin-top:16px"><a href="/journal" style="color:#3b82f6;text-decoration:none;">&rarr; View Full Trading Journal</a></div>

<div class="warn">Decision-support only — not financial advice. Paper-trade before risking real capital.
Last tick: {{when}}</div>
</body></html>
"""

JOURNAL_PAGE = """
<!doctype html><html><head><meta charset="utf-8"><title>MSNR Journal</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
 body{font-family:system-ui,Segoe UI,Arial;background:#0e1116;color:#e6edf3;margin:0;padding:24px}
 h1{font-size:20px;margin:0 0 4px}
 a{color:#3b82f6;text-decoration:none;margin-bottom:20px;display:inline-block}
 table{width:100%;border-collapse:collapse;margin:10px 0 26px;font-size:13px}
 th,td{text-align:left;padding:7px 10px;border-bottom:1px solid #21262d}
 th{color:#8b949e;font-weight:600} .long{color:#3fb950}.short{color:#f85149}
 .win{color:#3fb950} .loss{color:#f85149} .timeout{color:#d29922}
</style></head><body>
<a href="/">&larr; Back to Dashboard</a>
<h1>Trading Journal</h1>
<p>Track record: {{ record.wins }}W - {{ record.losses }}L ({{ '%.1f'|format(record.win_rate*100) }}%) | Net: {{ '%+.2f'|format(record.total_r) }}R</p>
<table>
<tr><th>Time</th><th>Pair</th><th>Dir</th><th>Outcome</th><th>R</th><th>P&L</th><th>Details</th></tr>
{% for t in trades %}
<tr>
  <td>{{ t.exit_time[:16] }}</td>
  <td>{{ t.pair }}</td>
  <td class="{{ t.direction }}">{{ t.direction|upper }}</td>
  <td class="{{ t.outcome }}">{{ t.outcome|upper }}</td>
  <td>{{ '%.2f'|format(t.r or 0) }}</td>
  <td>{{ '%+.2f'|format(t.pnl) }}</td>
  <td><span style="color:#8b949e;font-size:11px">{{ t.why }}</span></td>
</tr>
{% else %}<tr><td colspan="7">No trades recorded yet.</td></tr>{% endfor %}
</table>
</body></html>
"""


def _load_last() -> dict:
    if LAST_TICK.exists():
        try:
            return json.loads(LAST_TICK.read_text())
        except Exception:  # noqa: BLE001
            pass
    return {
        "nav": 10_000.0, "n_updates": 0, "breakeven": 1 / (1 + TARGET_R),
        "broker": BROKER, "target_r": TARGET_R,
        "open_positions": [], "closed": [], "opened": [], "signals": [],
        "overview": [], "when": "never",
    }


def _hydrate(st: dict) -> dict:
    """Never return an empty dashboard after seed — fill from live cache/scans."""
    st.setdefault("broker", BROKER)
    st.setdefault("target_r", TARGET_R)
    st.setdefault("breakeven", 1 / (1 + TARGET_R))
    if not st.get("nav"):
        st["nav"] = 10_000.0
    if not _seeded():
        st["seed_state"] = SEED["state"]
        return st
    try:
        if not st.get("overview"):
            st["overview"] = _overview()
    except Exception:  # noqa: BLE001
        st.setdefault("overview", [])
    if st.get("when") == "never" or not st.get("signals"):
        try:
            st["signals"] = sorted(_scan_only(), key=lambda s: -s.get("conf", 0))[:20]
        except Exception:  # noqa: BLE001
            st.setdefault("signals", [])
    st["seed_state"] = SEED["state"]
    return st


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

@app.route("/journal")
def journal_page():
    from src import journal
    trades = journal.recent(100)
    record = journal.track_record()
    # Add 'why' to trades for display if missing
    for t in trades:
        if "why" not in t:
            fp = get_fingerprint(t.get("features", {}))
            t["why"] = f"[{_fingerprint_name(fp)}] {t.get('direction', '').title()} setup"
    return render_template_string(JOURNAL_PAGE, trades=trades, record=record)

@app.route("/tick", methods=["POST", "GET"])
def do_tick():
    refresh = request.values.get("refresh") == "1"
    st = engine.tick(BROKER, TF, BIAS_TF, TARGET_R, refresh=refresh)
    sigs = sorted(_scan_only(), key=lambda s: -s.get("conf", 0))
    import datetime as _dt
    st["signals"] = sigs[:12]
    st["when"] = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    LAST_TICK.write_text(json.dumps(st, indent=2, default=str))
    return redirect("/")


def _reason(s: dict) -> dict:
    """Human-readable 'why' for a signal, from its causal features (the full SMC/MSNR story)."""
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
        conf.append("fair value gap in zone")
    if f.get("qml_at_zone"):
        conf.append("Quasimodo (3rd touch — institutional commitment)")
    if f.get("engulf_at_zone"):
        conf.append("engulfing candle at the zone")
    if f.get("flipped_level"):
        conf.append("flipped SNR level (RBS/SBR — strongest type)")
    if f.get("session_score"):
        conf.append("London/NY session (prime trading window)")
    pd_val = f.get("premium_discount", 0)
    if pd_val > 0.15:
        conf.append(f"in {'discount' if s['direction'] == 'long' else 'premium'} zone (+{pd_val:.0%})")
    if f.get("rej_strength", 0) >= 0.55:
        conf.append(f"strong rejection wick ({f.get('rej_wick_ratio', 0):.0%} of range)")
    if s.get("tf_aligned"):
        conf.append(f"multi-TF aligned ({s.get('aligned_tf', '')})")
        
    fp_name = "Standard MSNR"
    if f.get("qml_at_zone"): fp_name = "Quasimodo (QML)"
    elif f.get("sweep_recent") and f.get("choch_recent"): fp_name = "Turtle Soup / SH+BMS+RTO"
    elif f.get("flipped_level"): fp_name = "SBR/RBS Flip"
    elif f.get("ob_conf") or f.get("fvg_conf"): fp_name = "Order Block / FVG"

    why = (f"[{fp_name}] {bias.title()} {s['tf']} bias into a fresh {kind} SNR level, confirmed by a "
           f"rejection candle" + (". Confluences: " + ", ".join(conf) if conf else "."))
    return {"why": why, "confluences": conf, "tf": s.get("tf", TF)}


# Dashboard: only setups that are still open (not stopped/targeted) and recent.
_SIGNAL_MAX_AGE_HOURS = 48
_STRICT_SIGNALS = os.environ.get("SIGNAL_STRICT", "0") == "1"
_ENTRY_TFS = ["H4", "H1", "M30"]


def _ltf_zones(pr: str, ltf: str) -> list:
    """Load SNR zones for a lower TF (for multi-TF alignment check). Returns [] on error."""
    try:
        from src.data.fetch import load
        from src.detectors import snr
        df = load(pr, ltf)
        return snr.detect(df)
    except Exception:  # noqa: BLE001
        return []


def _scan_only() -> list:
    """Live ACTIVE signals only — not stopped out, not too old. Never raises."""
    if not _seeded():
        return []

    from src import backtest
    from src.data.fetch import load
    from src.signal_filter import LIVE_MAX_AGE, is_live

    ltf_cache: dict[tuple, list] = {}
    _ensure_fingerprints()
    news_data = _get_news()

    import datetime as _dt
    _now = _dt.datetime.utcnow()
    raw_signals = []
    for pr in config.PAIRS:
        for entry_tf in _ENTRY_TFS:
            try:
                max_age = LIVE_MAX_AGE.get(entry_tf, 8)
                lookback = max_age + 6
                try:
                    df = load(pr, entry_tf)
                except Exception:
                    continue
                for s in backtest.signals(pr, entry_tf, BIAS_TF, TARGET_R, lookback=lookback):
                    if not is_live(s, df, entry_tf):
                        continue

                    # --- Multi-TF alignment check (MSNR course rule) ---
                    ltf_map = {"H4": "H1", "H1": "M30"}   # H4 aligns with H1; H1 aligns with M30
                    align_tf = ltf_map.get(entry_tf)
                    tf_aligned = False
                    aligned_tf = ""
                    if align_tf:
                        key = (pr, align_tf)
                        if key not in ltf_cache:
                            ltf_cache[key] = _ltf_zones(pr, align_tf)
                        ltf_zones = ltf_cache[key]
                        # Check if any LTF fresh zone overlaps the signal's entry/stop range
                        entry_p, stop_p = s["entry"], s["stop"]
                        zone_lo = min(entry_p, stop_p)
                        zone_hi = max(entry_p, stop_p)
                        ltf_n = None
                        try:
                            from src.data.fetch import load
                            ltf_n = len(load(pr, align_tf))
                        except Exception:  # noqa: BLE001
                            pass
                        for z in ltf_zones:
                            if ltf_n and not z.is_fresh_at(ltf_n - 1):
                                continue
                            if z.bottom <= zone_hi and z.top >= zone_lo:
                                tf_aligned = True
                                aligned_tf = align_tf
                                break

                    s["tf_aligned"] = tf_aligned
                    s["aligned_tf"] = aligned_tf
                    
                    if hasattr(s["time"], "tzinfo") and s["time"].tzinfo is None:
                        # Assuming local timezone logic in backtest
                        pass
                        
                    embargo, news_title = is_news_embargo(pr, s["time"], news_data)
                    if embargo and _STRICT_SIGNALS:
                        continue

                    fp = get_fingerprint(s["features"])
                    base_conf = _FINGERPRINT_STATS.get(fp, 0.5)

                    # Confidence boost for multi-TF alignment (course: highest quality)
                    if tf_aligned:
                        base_conf = min(0.99, base_conf * 1.15)
                        
                    s["conf"] = base_conf
                    s["size"] = 1.0 if base_conf >= 0.5 else 0.5
                    s["active"] = True

                    s["time"] = str(s.get("time", ""))[:16]
                    s.update(_reason(s))
                    raw_signals.append({k: s[k] for k in (
                        "pair", "direction", "entry", "stop", "target", "rr",
                        "conf", "size", "features", "why", "confluences",
                        "tf", "time", "age_bars", "tf_aligned", "aligned_tf",
                        "bar_idx", "tap_bar", "zone_top", "zone_bottom", "zone_kind", "active",
                    ) if k in s})
            except FileNotFoundError:
                pass  # pair has no data file yet — skip silently
            except Exception as exc:  # noqa: BLE001
                print(f"  [scan_only] {pr} {entry_tf}: {exc}")
                
    # Sort: multi-TF aligned first, then by confidence
    raw_signals.sort(key=lambda s: (-int(s.get("tf_aligned", False)), -s.get("conf", 0)))
    
    out = []
    if _STRICT_SIGNALS:
        seen_groups = set()
        for s in raw_signals:
            grp_froz = frozenset(_get_group(s["pair"]))
            if grp_froz in seen_groups:
                continue
            seen_groups.add(grp_froz)
            out.append(s)
    else:
        out = raw_signals
    return out

_NEWS_CACHE = {"t": 0.0, "data": []}
def _get_news():
    if time.time() - _NEWS_CACHE["t"] > 3600:
        _NEWS_CACHE["data"] = get_high_impact_news()
        _NEWS_CACHE["t"] = time.time()
    return _NEWS_CACHE["data"]

def _fingerprint_name(fp: str) -> str:
    """Human label from a pipe-joined fingerprint string."""
    if "QML" in fp:
        return "Quasimodo (QML)"
    if "TurtleSoup" in fp:
        return "Turtle Soup / SH+BMS+RTO"
    if "Flipped" in fp:
        return "SBR/RBS Flip"
    if "OB_FVG" in fp:
        return "Order Block / FVG"
    return "Standard MSNR"


def get_fingerprint(feats: dict) -> str:
    parts = []
    if feats.get("qml_at_zone"): parts.append("QML")
    if feats.get("sweep_recent") and feats.get("choch_recent"): parts.append("TurtleSoup")
    elif feats.get("sweep_recent"): parts.append("Sweep")
    if feats.get("flipped_level"): parts.append("Flipped")
    if feats.get("ob_conf") or feats.get("fvg_conf"): parts.append("OB_FVG")
    if feats.get("session_score"): parts.append("Killzone")
    if not parts: parts.append("Base")
    return "|".join(parts)

_FINGERPRINT_STATS = {"Base": 0.5, "QML": 0.58, "TurtleSoup": 0.55, "Flipped": 0.52, "OB_FVG": 0.51, "Sweep": 0.48}
_fp_started = False

def _ensure_fingerprints():
    """Use instant defaults; refine from dataset in background (never block API)."""
    global _fp_started
    if _fp_started:
        return
    _fp_started = True

    def _build():
        global _FINGERPRINT_STATS
        try:
            from src.ml.dataset import build
            df = build(target_r=TARGET_R)
            stats: dict = {}
            for _, row in df.iterrows():
                fp = get_fingerprint(row.to_dict())
                if fp not in stats:
                    stats[fp] = {"w": 0, "n": 0}
                stats[fp]["n"] += 1
                if row["win"] == 1:
                    stats[fp]["w"] += 1
            if stats:
                _FINGERPRINT_STATS = {k: v["w"] / v["n"] for k, v in stats.items()}
        except Exception as e:
            print("Fingerprint err:", e)

    threading.Thread(target=_build, daemon=True, name="fingerprints").start()

CORR_GROUPS = [
    {"EURUSD", "GBPUSD", "AUDUSD", "NZDUSD"},
    {"USDCHF", "USDCAD", "USDJPY"},
    {"EURJPY", "GBPJPY", "CHFJPY"}
]

def _get_group(pair):
    for g in CORR_GROUPS:
        if pair in g: return g
    return {pair}


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
    try:
        from src.data.sources import finnhub_ws
        for row in out:
            q = finnhub_ws.live_quote(row["pair"])
            if q is not None:
                row["price"] = q
    except Exception:  # noqa: BLE001
        pass
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
    st = _hydrate(_load_last())
    from src import journal
    st["track_record"] = journal.track_record()
    return jsonify(st)


@app.route("/api/signals")
def api_signals():
    """Fast: cached signals from last tick; live scan if cache empty."""
    _ensure_seeding()
    last = _hydrate(_load_last())
    return jsonify({"signals": last.get("signals", []), "seed_state": SEED["state"],
                    "when": last.get("when", "")})


@app.route("/api/overview")
def api_overview():
    _ensure_seeding()
    last = _hydrate(_load_last())
    return jsonify({"overview": last.get("overview") or [], "seed_state": SEED["state"]})


@app.route("/api/journal")
def api_journal():
    from src import journal
    trades = journal.recent(int(request.args.get("n", 60)))
    for t in trades:
        if "why" not in t:
            fp = get_fingerprint(t.get("features", {}))
            t["why"] = f"[{_fingerprint_name(fp)}] {t.get('direction', '').title()} setup"
    return jsonify({
        "rows": trades,
        "count": journal.count(),
        "entries": journal.count("ENTRY"),
        "closes": journal.count("CLOSE"),
        "last_ts": journal.last_ts(),
    })


def _run_and_cache_inner(refresh: bool) -> dict:
    """Core tick logic — caller must hold _live_tick_lock."""
    import datetime as _dt
    # Auto-refresh data if it is more than 4 hours old
    if not refresh:
        try:
            last_mtime = max(f.stat().st_mtime for f in config.DATA_DIR.glob("*.parquet"))
            age_h = (_dt.datetime.now().timestamp() - last_mtime) / 3600
            if age_h > 4:
                refresh = True
                print(f"[tick] data is {age_h:.1f}h old - auto-refreshing")
        except Exception:
            pass
    st = engine.tick(BROKER, TF, BIAS_TF, TARGET_R, refresh=refresh)
    SEED["state"] = "ready"
    _OVERVIEW_CACHE["t"] = 0.0
    _ANALYSIS_CACHE.clear()
    st["signals"] = sorted(_scan_only(), key=lambda s: -s.get("conf", 0))[:20]
    st["overview"] = _overview()
    st["seed_state"] = SEED["state"]
    st["when"] = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    LAST_TICK.write_text(json.dumps(st, indent=2, default=str))
    return st


def _run_and_cache(refresh: bool) -> dict:
    """Run one engine tick (scan, trade, learn), cache results for the dashboard."""
    if not _live_tick_lock.acquire(blocking=False):
        return _load_last()
    try:
        return _run_and_cache_inner(refresh)
    finally:
        _live_tick_lock.release()


_manual_tick_lock = threading.Lock()
_live_tick_lock = threading.Lock()

def _async_manual_tick(refresh: bool):
    if not _manual_tick_lock.acquire(blocking=False):
        return  # already running
    try:
        SEED["state"] = "warming"
        _run_and_cache(refresh=refresh)
    finally:
        SEED["state"] = "ready"
        _manual_tick_lock.release()

@app.route("/api/tick", methods=["POST", "OPTIONS"])
def api_tick():
    if request.method == "OPTIONS":
        return ("", 204)
    refresh = request.values.get("refresh") == "1"
    threading.Thread(target=_async_manual_tick, args=(refresh,), daemon=True).start()
    # Return immediately so the dashboard doesn't hang for 13 minutes
    return jsonify({"status": "running", "seed_state": "warming"})


# ---------------------------------------------------------------------------
# Real-time tiered data updater
# ---------------------------------------------------------------------------
# Strategy:
#   FAST thread  – updates Binance (BTC) and Deriv (V100, V25) every 60 s.
#                  No API key required, no rate limits. These stream immediately.
#   SLOW thread  – Finnhub REST refresh for forex (60 calls/min free tier).
#                  One pair + one TF per cycle; live forming bars via WebSocket.
#   After every data update the engine tick + signal scan runs so the
#   dashboard reflects the freshest data without any user interaction.
# ---------------------------------------------------------------------------
TICK_INTERVAL = int(os.environ.get("TICK_INTERVAL", "60"))  # fast-loop interval (s)
_sched_started = [False]

_LIVE_PAIRS = {  # pairs grouped by their data source
    "fast": [],   # filled at runtime from config
    "slow": [],
}


def _get_live_groups():
    """Split config.PAIRS into fast (Binance/Deriv) and slow (Finnhub forex)."""
    from src.data.fetch import source_for
    fast, slow = [], []
    for pr in config.PAIRS:
        src = source_for(pr)
        if src in ("binance", "deriv"):
            fast.append(pr)
        else:
            slow.append(pr)
    return fast, slow


def _refresh_pair(pr: str, tfs=None) -> None:
    """Download fresh data for one pair — skip TFs that are still current."""
    from src.data import fetch
    tfs = tfs or ["H4", "H1", "M30", BIAS_TF]
    for tf in set(tfs):
        try:
            fetch.save_if_stale(pr, tf)
        except Exception as e:  # noqa: BLE001
            print(f"  [updater] {pr} {tf} fetch failed: {e}")


def _live_tick() -> None:
    """Run full engine tick in background — skip if one is already running."""
    if not _seeded():
        return
    if not _live_tick_lock.acquire(blocking=False):
        return
    try:
        _run_and_cache_inner(refresh=False)
    except Exception as e:  # noqa: BLE001
        print(f"  [updater] live tick failed: {e}")
    finally:
        _live_tick_lock.release()


def _fast_updater() -> None:
    """Thread: updates Binance + Deriv pairs every 60 s — no rate limit."""
    # Wait for initial seed
    for _ in range(180):
        if _seeded():
            break
        time.sleep(5)
    fast, _ = _get_live_groups()
    print(f"[fast-updater] live pairs: {fast} — polling every 60s")
    while True:
        for pr in fast:
            _refresh_pair(pr)
        _live_tick()
        print(f"[fast-updater] tick done ({', '.join(fast)})")
        time.sleep(60)  # Binance/Deriv have no rate limits


def _slow_updater() -> None:
    """Thread: Finnhub REST refresh for forex — WebSocket handles live forming bars."""
    # Wait for initial seed
    for _ in range(180):
        if _seeded():
            break
        time.sleep(5)
    _, slow = _get_live_groups()
    print(f"[slow-updater] forex pairs: {slow} — REST refresh + Finnhub WebSocket live")
    idx = 0
    tf_cycle = ["M30", "H1", "H4", BIAS_TF]
    while True:
        if not slow:
            time.sleep(60)
            _, slow = _get_live_groups()  # re-check in case config changed
            continue
        pr = slow[idx % len(slow)]
        # One TF per cycle to conserve API credits (full refresh over ~16 min)
        tf = tf_cycle[(idx // len(slow)) % len(tf_cycle)]
        from src.data import fetch
        try:
            fetch.save_if_stale(pr, tf)
        except Exception as e:  # noqa: BLE001
            print(f"  [updater] {pr} {tf} fetch failed: {e}")
        _live_tick()
        print(f"[slow-updater] updated {pr} {tf}")
        idx += 1
        time.sleep(15)  # Finnhub REST: 60/min — one call per 15s is safe


def _scheduler() -> None:
    # Wait for data+model to be seeded; _post_seed_tick usually runs first.
    for _ in range(180):
        if _seeded():
            break
        time.sleep(5)
    if LAST_TICK.exists():
        print("[scheduler] tick cache already warm — skipping duplicate initial tick")
        return
    try:
        _run_and_cache(refresh=False)
        print("[scheduler] initial full tick done")
    except Exception as e:  # noqa: BLE001
        print(f"[scheduler] initial tick error: {e}")



def _start_scheduler() -> None:
    if not _sched_started[0]:
        _sched_started[0] = True
        # 1. Initial full tick (runs once after seeding, fills the dashboard immediately)
        threading.Thread(target=_scheduler, daemon=True, name="scheduler-init").start()
        # 2. Fast loop: Binance + Deriv updated every 60 s (no rate limit)
        threading.Thread(target=_fast_updater, daemon=True, name="updater-fast").start()
        # 3. Slow loop: TwelveData forex, one pair per ~32 s (8 req/min)
        threading.Thread(target=_slow_updater, daemon=True, name="updater-slow").start()
        print("[scheduler] tiered real-time updater started: fast=60s, slow=8req/min forex cycle")


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
        live = src in ("binance", "finnhub", "deriv")
        rows.append({"pair": pr, "tf": tfs, "source": src, "live": live})
    out = {"pairs": rows, "timeframes": list(config.TIMEFRAMES),
           "ladder": "D1->H4->H1->M30",
           "source": "binance (crypto) · finnhub WS+REST (forex) · deriv (V100/V25)",
           "seed_state": SEED["state"]}
    try:
        from src.data.sources import finnhub_ws
        out["finnhub"] = finnhub_ws.status()
    except Exception:  # noqa: BLE001
        out["finnhub"] = None
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
    mf = config.MODELS_DIR / f"msnr_filter_{int(TARGET_R)}r.joblib"
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
    tf = request.args.get("tf", TF)
    if not _seeded():
        return jsonify({"seed_state": SEED["state"]})
    # Refresh this pair/tf if data is behind (keeps chart + analysis on live TwelveData)
    import datetime as _dt
    data_path = config.DATA_DIR / f"{pair}_{tf}.parquet"
    tf_hours = {"M30": 0.5, "H1": 1, "H4": 4, "D1": 24}.get(tf, 4)
    try:
        if data_path.exists():
            import pandas as pd
            last_ts = pd.read_parquet(data_path, columns=["close"]).index.max()
            age_h = (_dt.datetime.utcnow() - pd.Timestamp(last_ts).to_pydatetime()).total_seconds() / 3600
            if age_h > tf_hours * 1.2:
                from src.data import fetch
                fetch.save_if_stale(pair, tf)
                _ANALYSIS_CACHE.clear()
        elif _seeded():
            from src.data import fetch
            fetch.save_if_stale(pair, tf)
    except Exception:  # noqa: BLE001
        pass
    c = _ANALYSIS_CACHE.get(f"{pair}_{tf}")
    if c and time.time() - c[0] < 60:
        return jsonify(c[1])
    from src.data.fetch import load
    from src.detectors import smc
    from src.detectors import snr as snrmod
    from src.detectors import structure as stmod
    df = load(pair, tf)
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
    breakers = [{"kind": b.kind, "top": round(b.top, 5), "bottom": round(b.bottom, 5),
                 "time": str(b.time)[:16]} for b in smc.breaker_blocks(df)[-6:]][::-1]
    qms = [{"kind": q.kind, "sweep": round(q.sweep_level, 5), "choch": round(q.choch_level, 5),
            "time": str(q.time)[:16]} for q in smc.quasimodos(df)[-6:]][::-1]
    now_utc = _dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    last_bar = str(df.index[-1])[:16]
    last_dt = pd.Timestamp(df.index[-1]).to_pydatetime()
    stale_min = int((_dt.datetime.utcnow() - last_dt).total_seconds() / 60)
    out = {"pair": pair, "tf": tf, "bias_tf": BIAS_TF, "price": round(float(df["close"].iat[-1]), 5),
           "bias": bias, "breaks": breaks, "fresh_snr": fresh, "order_blocks": obs,
           "fvgs": fvgs, "sweeps": sweeps, "breakers": breakers, "quasimodos": qms,
           "last_bar": last_bar, "now_utc": now_utc, "stale_minutes": stale_min}
    _ANALYSIS_CACHE[f"{pair}_{tf}"] = (time.time(), out)
    return jsonify(out)


@app.route("/api/chart")
def api_chart():
    """Server-rendered annotated chart PNG (SNR zones + structure + rejections).

    Auto-fetches missing or stale data. Signal charts center on the setup bar and
    draw the exact SNR zone + confluence labels from the analysed signal.
    """
    import datetime as _dt

    pair = request.args.get("pair", config.PAIRS[0])
    tf = request.args.get("tf", TF)
    if pair not in config.PAIRS or tf not in config.TIMEFRAMES:
        return ("bad params", 400)

    data_path = config.DATA_DIR / f"{pair}_{tf}.parquet"
    if not data_path.exists():
        try:
            from src.data import fetch
            fetch.save(pair, tf)
            print(f"[api_chart] auto-fetched {pair} {tf}")
        except Exception as e:  # noqa: BLE001
            return _chart_placeholder(pair, tf, f"Fetching data… ({e})")
    else:
        # Refresh if the last bar is older than ~2× the candle period
        tf_hours = {"M30": 0.5, "H1": 1, "H4": 4, "D1": 24}.get(tf, 4)
        try:
            import pandas as pd
            last_ts = pd.read_parquet(data_path, columns=["close"]).index.max()
            age_h = (_dt.datetime.utcnow() - pd.Timestamp(last_ts).to_pydatetime()).total_seconds() / 3600
            if age_h > tf_hours * 1.2:
                from src.data import fetch
                fetch.save_if_stale(pair, tf)
                _ANALYSIS_CACHE.clear()
                print(f"[api_chart] refreshed stale {pair} {tf} ({age_h:.1f}h old)")
        except Exception:  # noqa: BLE001
            pass

    try:
        from src.viz.plot_chart import plot
        entry = request.args.get("entry", type=float)
        stop_p = request.args.get("stop", type=float)
        target = request.args.get("target", type=float)
        direction = request.args.get("dir", default=None)
        signal_bar = request.args.get("bar", type=int)
        zone_top = request.args.get("zt", type=float)
        zone_bottom = request.args.get("zb", type=float)
        zone_kind = request.args.get("zk", default=None)
        notes = request.args.get("notes", default="")

        has_signal = entry is not None and stop_p is not None and target is not None
        n_bars = 80 if has_signal else 140

        path = plot(
            pair, tf, bars=n_bars, left=3, right=3,
            entry=entry, stop=stop_p, target=target, direction=direction,
            signal_bar=signal_bar, zone_top=zone_top, zone_bottom=zone_bottom,
            zone_kind=zone_kind, confluences=notes.split("|") if notes else None,
        )
        return send_file(path, mimetype="image/png", max_age=0)
    except FileNotFoundError:
        return _chart_placeholder(pair, tf, "No data yet — click Refresh + tick")
    except Exception as e:  # noqa: BLE001
        return _chart_placeholder(pair, tf, str(e))


def _chart_placeholder(pair: str, tf: str, msg: str):
    """Return a simple dark PNG with an informative message instead of a broken image."""
    import io
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(14, 5), facecolor="#0e1116")
    ax.set_facecolor("#0e1116")
    ax.text(0.5, 0.6, f"{pair} {tf}", transform=ax.transAxes,
            ha="center", va="center", fontsize=24, color="#e6edf3", fontweight="bold")
    ax.text(0.5, 0.35, msg, transform=ax.transAxes,
            ha="center", va="center", fontsize=13, color="#8b949e")
    ax.text(0.5, 0.18, "Data will appear automatically as the background updater fetches it.",
            transform=ax.transAxes, ha="center", va="center", fontsize=10, color="#484f58")
    ax.axis("off")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=90, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


_start_scheduler()   # begin autonomous ticking (set TICK_INTERVAL=0 to disable)

# Log data-source status at boot (helps Railway debugging — never prints the key).
try:
    from src.data.sources import finnhub as _fh
    from src.data.sources import finnhub_ws as _fhw
    _fh_ok = _fh.available()
    print(f"[boot] data sources: binance=BTCUSD | deriv=V100,V25 | finnhub={'ON' if _fh_ok else 'OFF (set FINNHUB_KEY)'}")
    print(f"[boot] DATA_DIR={config.DATA_DIR}")
except Exception as _e:  # noqa: BLE001
    print(f"[boot] source check failed: {_e}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), debug=False)

@app.route("/api/debug_signals")
def api_debug_signals():
    """Return raw vs live signal counts to diagnose filtering."""
    from src import backtest
    from src.data.fetch import load
    from src.signal_filter import LIVE_MAX_AGE, is_active, is_live

    res = {}
    for pr in config.PAIRS:
        res[pr] = {}
        for tf in _ENTRY_TFS:
            try:
                df = load(pr, tf)
                max_age = LIVE_MAX_AGE.get(tf, 8)
                sigs = backtest.signals(pr, tf, BIAS_TF, TARGET_R, lookback=max_age + 20)
                out_sigs = []
                for s in sigs:
                    out_sigs.append({
                        "time": str(s.get("time")),
                        "direction": s.get("direction"),
                        "entry": s.get("entry"),
                        "rr": s.get("rr"),
                        "age_bars": s.get("age_bars"),
                        "active": is_active(s, df),
                        "live": is_live(s, df, tf),
                    })
                res[pr][tf] = out_sigs
            except FileNotFoundError:
                res[pr][tf] = "NO DATA FILE"
            except Exception as e:
                res[pr][tf] = f"ERROR: {e}"
    return jsonify(res)

