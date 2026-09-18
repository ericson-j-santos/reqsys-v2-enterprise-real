#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / "docs" / "runbooks" / "session-launcher-adoption.md"
REQUIRED = (
    "SESSION_LAUNCH_OK",
    "state_validated=true",
    "session_id",
    "target_path",
    "head",
    "snapshot_sha256",
    "--expected-head",
    "risco 2 na base",
    "risco 2 no worktree",
    "fail-closed",
)

def validate_text(runbook_text: str) -> list[str]:
    return [f"marcador ausente: {item}" for item in REQUIRED if item not in runbook_text]

def validate() -> list[str]:
    if not RUNBOOK.is_file():
        return ["runbook ausente"]
    return validate_text(RUNBOOK.read_text(encoding="utf-8"))

def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("SESSION_LAUNCHER_ADOPTION_OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
