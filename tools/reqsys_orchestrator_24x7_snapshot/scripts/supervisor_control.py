from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


VALID_ACTIONS = {"restart-server", "restart-worker", "shutdown"}


def control_dir(install_root: Path) -> Path:
    return install_root / "data" / "control"


def request_action(install_root: Path, action: str) -> Path:
    if action not in VALID_ACTIONS:
        raise ValueError("invalid action")
    directory = control_dir(install_root)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{action}.request"
    temp = target.with_suffix(".request.tmp")
    temp.write_text(str(time.time()) + "\n", encoding="utf-8")
    temp.replace(target)
    return target


def status(install_root: Path) -> dict:
    path = install_root / "runtime-status.json"
    if not path.exists():
        return {"present": False}
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["present"] = True
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-root", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    request = sub.add_parser("request")
    request.add_argument("action", choices=sorted(VALID_ACTIONS))
    sub.add_parser("status")
    args = parser.parse_args()

    root = Path(args.install_root)
    if args.command == "request":
        path = request_action(root, args.action)
        print(json.dumps({"ok": True, "request": str(path)}, sort_keys=True))
        return

    print(json.dumps(status(root), sort_keys=True))


if __name__ == "__main__":
    main()
