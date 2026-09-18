from __future__ import annotations

import sqlite3
from pathlib import Path


def backup_database(db_path: str | Path, backup_path: str | Path) -> None:
    source_path = Path(db_path)
    target_path = Path(backup_path)
    if not source_path.exists():
        raise FileNotFoundError(source_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source_path) as source, sqlite3.connect(target_path) as target:
        source.backup(target)
        target.execute("PRAGMA integrity_check")
        result = target.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise RuntimeError(f"backup integrity_check failed: {result}")


def restore_if_missing(db_path: str | Path, backup_path: str | Path) -> bool:
    target_path = Path(db_path)
    source_path = Path(backup_path)
    if target_path.exists() or not source_path.exists():
        return False
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source_path) as source, sqlite3.connect(target_path) as target:
        result = source.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise RuntimeError(f"backup integrity_check failed: {result}")
        source.backup(target)
    return True
