#!/usr/bin/env python3
"""Seleciona testes backend afetados com fallback seguro para suite completa."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

BACKEND_DIR = Path.cwd()


def changed_files() -> list[str]:
    base_sha = os.environ.get("BASE_SHA")
    head_sha = os.environ.get("HEAD_SHA", "HEAD")
    commands: list[list[str]] = []
    if base_sha:
        commands.append(["git", "diff", "--name-only", base_sha, head_sha])
    commands.append(["git", "diff", "--name-only", "HEAD^"])

    for command in commands:
        try:
            result = subprocess.run(command, check=True, text=True, capture_output=True)
            files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            if files:
                return files
        except Exception:
            continue
    return []


def test_candidate(file_path: str) -> Path | None:
    path = Path(file_path)
    if len(path.parts) < 3 or path.parts[0] != "backend" or path.parts[1] != "app":
        return None
    if path.suffix != ".py":
        return None

    module_parts = path.parts[2:]
    test_name = f"test_{Path(module_parts[-1]).stem}.py"
    if len(module_parts) == 1:
        return BACKEND_DIR / "tests" / test_name
    return BACKEND_DIR / "tests" / Path(*module_parts[:-1]) / test_name


def main() -> int:
    candidates: list[str] = []
    for file_path in changed_files():
        candidate = test_candidate(file_path)
        if candidate and candidate.exists():
            candidates.append(str(candidate.relative_to(BACKEND_DIR)))

    if not candidates:
        print("tests/")
        return 0

    for candidate in sorted(set(candidates)):
        print(candidate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
