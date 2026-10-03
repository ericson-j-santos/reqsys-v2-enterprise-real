#!/usr/bin/env python3
"""Runner isolado da dimensão coverage da Trilha D.

Corrige o parsing do relatório pytest-cov para considerar a linha TOTAL ou o texto
"Total coverage", evitando falso negativo quando há percentuais intermediários no
stdout_tail.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
DEFAULT_OUTPUT = ROOT / "artifacts" / "trilha-d-qualidade-governanca"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def backend_test_env() -> dict[str, str]:
    return {
        "DATABASE_URL": "sqlite:///./reqsys_trilha_d.db",
        "JWT_SECRET_KEY": "ci-secret-key-for-testing-only",
        "JWT_SECRET": "ci-secret-key-for-testing-only-minimum-32-characters",
        "JWT_ISSUER": "reqsys-ci",
        "JWT_AUDIENCE": "reqsys-ci-tests",
        "JWT_EXP_MINUTES": "60",
        "ALLOW_DEMO_LOGIN": "true",
        "APP_ENV": "test",
        "AZURE_TENANT_ID": "00000000-0000-0000-0000-000000000000",
        "AZURE_CLIENT_ID": "11111111-1111-1111-1111-111111111111",
        "AZURE_AUTHORITY": "https://login.microsoftonline.com/00000000-0000-0000-0000-000000000000",
        "REDMINE_URL": "https://placeholder.example.com",
        "REDMINE_API_KEY": "placeholder",
        "ENABLE_GITHUB_REDMINE_IMPORT": "false",
        "SSRS_BASE_URL": "",
        "GITHUB_WEBHOOK_SECRET": "",
        "GITLAB_WEBHOOK_TOKEN": "",
    }


def run_command(command: list[str], *, cwd: Path, timeout: int = 900) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(backend_test_env())
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def parse_coverage_percent(output: str) -> float | None:
    """Extrai a cobertura total real do pytest-cov.

    Prioridade:
    1. linha TOTAL do relatório tabular, aceitando branch coverage e decimais;
    2. mensagem final "Total coverage: NN.NN%";
    3. mensagem "Required test coverage ... Total coverage: NN.NN%".
    """
    total_lines = [line.strip() for line in output.splitlines() if line.strip().startswith("TOTAL")]
    for line in reversed(total_lines):
        percentages = re.findall(r"(\d+(?:\.\d+)?)%", line)
        if percentages:
            return float(percentages[-1])

    match = re.search(r"Total coverage:\s*(\d+(?:\.\d+)?)%", output, re.IGNORECASE)
    if match:
        return float(match.group(1))

    match = re.search(r"Required test coverage.*?(\d+(?:\.\d+)?)%\s*$", output, re.IGNORECASE | re.MULTILINE)
    if match:
        return float(match.group(1))

    return None


def build_result(*, coverage: float | None, threshold: float, proc: subprocess.CompletedProcess[str], duration: float) -> dict[str, Any]:
    output = proc.stdout + proc.stderr
    passed = proc.returncode == 0 and coverage is not None and coverage >= threshold
    below_threshold = coverage is not None and coverage < threshold
    blockers: list[str] = []
    if below_threshold:
        blockers.append(f"coverage {coverage}% abaixo do gate {threshold}%")
    if proc.returncode != 0 and not below_threshold:
        blockers.append("pytest com cobertura falhou")
    if coverage is None:
        blockers.append("coverage total não identificado no relatório pytest-cov")

    return {
        "dimension": "coverage",
        "status": "passed" if passed else "failed",
        "score": round(coverage if coverage is not None else 0.0, 2),
        "duration_seconds": round(duration, 2),
        "summary": f"coverage {coverage if coverage is not None else 'n/a'}% (gate {threshold}%)",
        "details": {
            "exit_code": proc.returncode,
            "coverage_percent": coverage,
            "threshold_percent": threshold,
            "parser": "total-line-or-total-coverage-v2",
            "stdout_tail": output[-2000:],
        },
        "blockers": blockers,
        "recommendations": [] if passed else ["Aumentar cobertura em módulos críticos sem testes"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Executa a dimensão coverage da Trilha D.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--threshold", type=float, default=60.0)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", ""))
    args = parser.parse_args()

    started = datetime.now(timezone.utc)
    proc = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "-q",
            "--tb=line",
            "--cov=app",
            "--cov-report=term-missing:skip-covered",
            f"--cov-fail-under={int(args.threshold)}",
        ],
        cwd=BACKEND,
    )
    duration = (datetime.now(timezone.utc) - started).total_seconds()
    coverage = parse_coverage_percent(proc.stdout + proc.stderr)
    result = build_result(coverage=coverage, threshold=args.threshold, proc=proc, duration=duration)
    result["metadata"] = {
        "generated_at": utc_now(),
        "repository": args.repository,
        "run_id": args.run_id,
    }

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "coverage.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
