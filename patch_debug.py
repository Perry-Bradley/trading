"""Patch: Add a debug endpoint for signals."""
from pathlib import Path

path = Path("src/webapp/app.py")
text = path.read_text(encoding="utf-8")

NEW_ENDPOINT = """
@app.route("/api/debug_signals")
def api_debug_signals():
    \"\"\"Return raw signal scan data to diagnose filtering.\"\"\"
    from src import backtest
    res = {}
    for pr in ["BTCUSD", "V100", "V25", "XAUUSD"]:
        res[pr] = {}
        for tf in ["H4", "H1", "M30"]:
            try:
                max_age = _TF_MAX_AGE.get(tf, 12)
                sigs = backtest.signals(pr, tf, BIAS_TF, TARGET_R, lookback=max_age * 4)
                
                # Check calendar age
                import datetime as _dt
                _now = _dt.datetime.utcnow()
                
                out_sigs = []
                for s in sigs:
                    sig_time = s.get("time")
                    age_hours = -1
                    if sig_time is not None:
                        try:
                            if hasattr(sig_time, 'to_pydatetime'):
                                sig_dt = sig_time.to_pydatetime().replace(tzinfo=None)
                            else:
                                sig_dt = _dt.datetime.fromisoformat(str(sig_time)[:16])
                            age_hours = (_now - sig_dt).total_seconds() / 3600
                        except Exception:
                            pass
                    out_sigs.append({
                        "time": str(sig_time),
                        "direction": s.get("direction"),
                        "entry": s.get("entry"),
                        "rr": s.get("rr"),
                        "age_bars": s.get("age_bars"),
                        "age_hours": age_hours,
                        "filtered_by_bars": s.get("age_bars", 999) > max_age,
                        "filtered_by_time": age_hours > _SIGNAL_MAX_AGE_HOURS if age_hours != -1 else False
                    })
                res[pr][tf] = out_sigs
            except FileNotFoundError:
                res[pr][tf] = "NO DATA FILE"
            except Exception as e:
                res[pr][tf] = f"ERROR: {e}"
    return jsonify(res)

"""

if "/api/debug_signals" not in text:
    text += NEW_ENDPOINT
    path.write_text(text, encoding="utf-8")
    print("PATCH APPLIED")
