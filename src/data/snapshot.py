"""Data snapshot: pack/restore the whole data dir (parquets + models) as tar.gz.

Kills the cold-start backfill: a fresh container (empty volume) restores history
from a snapshot in seconds instead of pulling every pair/TF through TwelveData's
rate limits (~minutes).

Usage:
  - GET /api/snapshot on a warm instance downloads msnr_snapshot.tar.gz
  - Host it anywhere (GitHub release, S3, another Railway instance's
    /api/snapshot URL) and set SNAPSHOT_URL on the new deployment.
  - _seed() calls restore_if_empty() before fetching — a hit means the seed
    fetch loop finds every file already present and skips straight to ready.
"""
from __future__ import annotations

import io
import os
import tarfile
import urllib.request

import config

# What goes in a snapshot: price history + learned models + paper account state.
_PATTERNS = ("*.parquet", "*.json", "*.joblib", "*.jsonl", "*.csv")


def pack() -> io.BytesIO:
    """Tar.gz everything matching _PATTERNS in DATA_DIR (incl. models/)."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for pat in _PATTERNS:
            for f in sorted(config.DATA_DIR.rglob(pat)):
                if f.is_file():
                    tar.add(f, arcname=str(f.relative_to(config.DATA_DIR)))
    buf.seek(0)
    return buf


def _safe_member(name: str) -> bool:
    """Only plain relative paths — no traversal, no absolute paths."""
    return not (name.startswith(("/", "\\")) or ".." in name.replace("\\", "/").split("/"))


def restore(data: bytes) -> int:
    """Extract a snapshot into DATA_DIR (never overwrites existing files).

    Returns the number of files written.
    """
    n = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for m in tar.getmembers():
            if not m.isfile() or not _safe_member(m.name):
                continue
            dest = config.DATA_DIR / m.name
            if dest.exists():
                continue  # live data on the volume always wins
            dest.parent.mkdir(parents=True, exist_ok=True)
            src = tar.extractfile(m)
            if src is None:
                continue
            dest.write_bytes(src.read())
            n += 1
    return n


def restore_if_empty() -> int:
    """If SNAPSHOT_URL is set and DATA_DIR has no price history yet, restore.

    Returns files restored (0 = nothing to do / no URL / already have data).
    """
    url = os.environ.get("SNAPSHOT_URL", "").strip()
    if not url:
        return 0
    if any(config.DATA_DIR.glob("*.parquet")):
        return 0  # volume already has data — never clobber it
    try:
        with urllib.request.urlopen(url, timeout=60) as r:  # noqa: S310
            data = r.read()
        n = restore(data)
        print(f"[snapshot] restored {n} files from SNAPSHOT_URL")
        return n
    except Exception as e:  # noqa: BLE001
        print(f"[snapshot] restore failed ({e}) — falling back to normal seed fetch")
        return 0
