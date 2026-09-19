from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

FILES = ("worker_agent.py", "maintenance.py")


def install(source_root: Path, install_root: Path) -> dict:
    source_pkg = source_root / "orchestrator"
    target_pkg = install_root / "orchestrator"
    if not source_pkg.is_dir() or not target_pkg.is_dir():
        raise RuntimeError("source or target orchestrator package missing")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = install_root / f"adapter-backup-{stamp}" / "orchestrator"
    backup.mkdir(parents=True, exist_ok=False)

    installed = []
    for name in FILES:
        source = source_pkg / name
        target = target_pkg / name
        if not source.is_file() or not target.is_file():
            raise RuntimeError(f"required file missing: {name}")
        shutil.copy2(target, backup / name)
        temp = target.with_suffix(target.suffix + ".tmp")
        shutil.copy2(source, temp)
        os.replace(temp, target)
        installed.append(str(target))

    return {
        "ok": True,
        "backup": str(backup.parent),
        "installed": installed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--install-root", required=True)
    args = parser.parse_args()
    result = install(Path(args.source_root), Path(args.install_root))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
