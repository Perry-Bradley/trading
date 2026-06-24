"""Patch: add auto-refresh to _run_and_cache when data is stale."""
from pathlib import Path

path = Path("src/webapp/app.py")
text = path.read_text(encoding="utf-8")

OLD = (
    'def _run_and_cache(refresh: bool) -> dict:\n'
    '    """Run one engine tick (scan \u2192 trade \u2192 learn), cache results for the dashboard."""\n'
    '    import datetime as _dt\n'
    '    st = engine.tick(BROKER, TF, BIAS_TF, TARGET_R, refresh=refresh)\n'
    '    SEED["state"] = "ready"                       # a successful tick means we\'re seeded\n'
    '    _OVERVIEW_CACHE["t"] = 0.0                     # force overview refresh\n'
    '    st["signals"] = sorted(_scan_only(), key=lambda s: -s.get("conf", 0))[:20]\n'
    '    st["overview"] = _overview()\n'
    '    st["seed_state"] = SEED["state"]\n'
    '    st["when"] = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")\n'
    '    LAST_TICK.write_text(json.dumps(st, indent=2, default=str))\n'
    '    return st'
)

NEW = (
    'def _run_and_cache(refresh: bool) -> dict:\n'
    '    """Run one engine tick (scan, trade, learn), cache results for the dashboard."""\n'
    '    import datetime as _dt\n'
    '    # Auto-refresh data if it is more than 4 hours old\n'
    '    if not refresh:\n'
    '        try:\n'
    '            last_mtime = max(f.stat().st_mtime for f in config.DATA_DIR.glob("*.parquet"))\n'
    '            age_h = (_dt.datetime.now().timestamp() - last_mtime) / 3600\n'
    '            if age_h > 4:\n'
    '                refresh = True\n'
    '                print(f"[tick] data is {age_h:.1f}h old - auto-refreshing")\n'
    '        except Exception:\n'
    '            pass\n'
    '    st = engine.tick(BROKER, TF, BIAS_TF, TARGET_R, refresh=refresh)\n'
    '    SEED["state"] = "ready"\n'
    '    _OVERVIEW_CACHE["t"] = 0.0\n'
    '    st["signals"] = sorted(_scan_only(), key=lambda s: -s.get("conf", 0))[:20]\n'
    '    st["overview"] = _overview()\n'
    '    st["seed_state"] = SEED["state"]\n'
    '    st["when"] = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")\n'
    '    LAST_TICK.write_text(json.dumps(st, indent=2, default=str))\n'
    '    return st'
)

# Try different line endings
found = False
for lf in ['\n', '\r\n']:
    old_variant = OLD.replace('\n', lf)
    if old_variant in text:
        text = text.replace(old_variant, NEW)
        found = True
        print(f"PATCH APPLIED ({repr(lf)})")
        break

if not found:
    # Try finding just the function signature and replacing the whole block
    import re
    pattern = r'def _run_and_cache\(refresh: bool\) -> dict:.*?return st'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        text = text[:match.start()] + NEW + text[match.end():]
        found = True
        print("PATCH APPLIED (regex)")

if found:
    path.write_text(text, encoding="utf-8")
else:
    print("FAILED - could not find block")
