#!/usr/bin/env python3
"""Valida contratos mínimos contra regressões em workflows críticos do ReqSys."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    raise AssertionError(message)


def validate_cofre_runtime_gate() -> None:
    path = ROOT / ".github/workflows/cofre-runtime-evidence-gate.yml"
    text = path.read_text(encoding="utf-8")

    top_level_env = re.search(r"(?ms)^env:\n(?P<body>(?:^[ \t]+.*\n?)*)", text)
    if top_level_env and "runner.temp" in top_level_env.group("body"):
        fail("Cofre Runtime Evidence Gate não pode usar runner.temp no env global")

    runtime_job = re.search(
        r"(?ms)^  runtime-evidence:\n(?P<body>.*?)(?=^  [a-zA-Z0-9_-]+:\n|\Z)",
        text,
    )
    if not runtime_job:
        fail("Job runtime-evidence não encontrado")
    if "STATE_FILE: ${{ runner.temp }}/cofre-runtime-state.bin" not in runtime_job.group("body"):
        fail("STATE_FILE deve permanecer no escopo do job runtime-evidence")


def validate_pr_evidence_gate() -> None:
    path = ROOT / ".github/workflows/pr-evidence-gate.yml"
    text = path.read_text(encoding="utf-8")

    if "types: [completed]" not in text:
        fail("PR Evidence Gate deve revalidar após workflow_run completed")
    if "deferred" not in text:
        fail("PR Evidence Gate deve representar timeout transitório como deferred")
    if re.search(r"gate\.failures\.push\(\.\.\.gate\.pending\).*gate\.status\s*=\s*['\"]failed['\"]", text, re.S):
        fail("PR Evidence Gate não pode converter pending em failure por timeout")
    if "strict_ci_failed" not in text:
        fail("Falha real do CI estrito deve continuar bloqueante")


def main() -> int:
    checks = [validate_cofre_runtime_gate, validate_pr_evidence_gate]
    failures: list[str] = []
    for check in checks:
        try:
            check()
            print(f"PASS {check.__name__}")
        except (AssertionError, OSError) as exc:
            failures.append(f"{check.__name__}: {exc}")
            print(f"FAIL {check.__name__}: {exc}", file=sys.stderr)

    if failures:
        print("\nWorkflow regression contract validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("All workflow regression contracts passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
