#!/usr/bin/env python3
"""Create a consistent SQLite backup on a running Fly Machine.

This script is copied to the Machine and executed there. It never reads
credentials and writes only a temporary database copy plus non-sensitive
metadata.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def table_counts(connection: sqlite3.Connection) -> dict[str, int]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    counts: dict[str, int] = {}
    for (name,) in rows:
        quoted = str(name).replace('"', '""')
        counts[str(name)] = int(
            connection.execute(f'SELECT COUNT(*) FROM "{quoted}"').fetchone()[0]
        )
    return counts


def create_backup(source: Path, target: Path, metadata: Path) -> dict[str, object]:
    if not source.is_file():
        raise FileNotFoundError(f"SQLite source not found: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    metadata.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)

    started = time.monotonic()
    source_uri = f"file:{source}?mode=ro"
    with sqlite3.connect(source_uri, uri=True, timeout=30) as src:
        src.execute("PRAGMA busy_timeout=30000")
        with sqlite3.connect(target, timeout=30) as dst:
            src.backup(dst, pages=512, sleep=0.05)
            integrity = str(dst.execute("PRAGMA quick_check").fetchone()[0])
            counts = table_counts(dst)
    duration = time.monotonic() - started
    if integrity.lower() != "ok":
        raise RuntimeError(f"SQLite quick_check failed: {integrity}")

    payload: dict[str, object] = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "source_path": str(source),
        "backup_path": str(target),
        "size_bytes": target.stat().st_size,
        "sha256": sha256_file(target),
        "quick_check": integrity,
        "table_counts": counts,
        "table_count": len(counts),
        "row_count_total": sum(counts.values()),
        "duration_seconds": round(duration, 6),
        "hostname": os.uname().nodename,
    }
    metadata.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = create_backup(args.source, args.target, args.metadata)
    print(json.dumps(payload, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
