#!/usr/bin/env python3
"""Valida se um Dynamic Performance Gate produziu evidência elegível para SLO.

Regra fail-closed:
- runtime live `skipped` => execução não elegível; downstream encerra com sucesso sem SLO;
- runtime live `success` => `dynamic-performance-evidence-main` é obrigatório;
- runtime ausente ou conclusão inesperada => erro;
- artifact esperado ausente/expirado => erro.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

RUNTIME_JOB_NAME = "Measure live runtime performance"
MAIN_ARTIFACT_NAME = "dynamic-performance-evidence-main"


class EligibilityError(RuntimeError):
    """Falha de contrato que deve interromper o gate."""


def assess_eligibility(
    jobs_payload: dict[str, Any],
    artifacts_payload: dict[str, Any],
) -> dict[str, Any]:
    jobs = jobs_payload.get("jobs") or []
    runtime_jobs = [job for job in jobs if job.get("name") == RUNTIME_JOB_NAME]
    if not runtime_jobs:
        raise EligibilityError(f"job obrigatório ausente: {RUNTIME_JOB_NAME}")

    runtime = runtime_jobs[-1]
    conclusion = str(runtime.get("conclusion") or "")
    if conclusion == "skipped":
        return {
            "eligible": False,
            "reason": "runtime_measurement_skipped",
            "runtime_conclusion": conclusion,
            "artifact_id": None,
        }
    if conclusion != "success":
        raise EligibilityError(
            f"conclusão inesperada do runtime live: {conclusion or 'missing'}"
        )

    artifacts = artifacts_payload.get("artifacts") or []
    matches = [
        artifact
        for artifact in artifacts
        if artifact.get("name") == MAIN_ARTIFACT_NAME and not artifact.get("expired", False)
    ]
    if not matches:
        raise EligibilityError(
            "runtime live aprovado sem dynamic-performance-evidence-main; falha fechada"
        )

    selected = max(matches, key=lambda item: int(item.get("id") or 0))
    return {
        "eligible": True,
        "reason": "main_runtime_evidence_available",
        "runtime_conclusion": conclusion,
        "artifact_id": selected.get("id"),
    }


def _write_github_output(path: Path, result: dict[str, Any]) -> None:
    values = {
        "eligible": str(bool(result["eligible"])).lower(),
        "reason": str(result["reason"]),
        "runtime_conclusion": str(result["runtime_conclusion"]),
        "artifact_id": "" if result.get("artifact_id") is None else str(result["artifact_id"]),
    }
    with path.open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Valida elegibilidade de evidence SLO")
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args(argv)

    try:
        jobs = json.loads(args.jobs.read_text(encoding="utf-8"))
        artifacts = json.loads(args.artifacts.read_text(encoding="utf-8"))
        result = assess_eligibility(jobs, artifacts)
        if args.github_output:
            _write_github_output(args.github_output, result)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, json.JSONDecodeError, EligibilityError) as exc:
        print(f"performance_slo_eligibility_error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
