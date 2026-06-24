"""Patch: Ensure _seed always fetches missing data on startup, even if model exists."""
from pathlib import Path

path = Path("src/webapp/app.py")
text = path.read_text(encoding="utf-8")

OLD_SEEDED = """def _seeded() -> bool:
    return SEED["state"] == "ready" or _model_path().exists()"""

NEW_SEEDED = """def _seeded() -> bool:
    if SEED["state"] == "ready": return True
    if not _model_path().exists(): return False
    # Model exists, but do we have the multi-TF data files?
    pr = config.PAIRS[0]
    return (config.DATA_DIR / f"{pr}_H1.parquet").exists() and (config.DATA_DIR / f"{pr}_M30.parquet").exists()"""

if OLD_SEEDED in text:
    text = text.replace(OLD_SEEDED, NEW_SEEDED)
    path.write_text(text, encoding="utf-8")
    print("PATCH APPLIED: _seeded()")
else:
    print("FAILED TO APPLY _seeded() PATCH")
