#!/usr/bin/env python3
"""Validate GitOps runtime governance evidence.

This checker is intentionally offline: it does not call GitHub, ArgoCD,
Kubernetes, Fly.io or any external runtime. CI can use it against a generated
or manually attached evidence JSON.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REQUIRED_SECTIONS = (
    "intencao",
    "mudanca_git",
    "execucao",
    "observabilidade",
    "recuperacao",
)

SUCCESS_STATUSES = {"ok", "passed", "success", "green", "validated", "evidenced"}
FAILURE_STATUSES = {"failed", "failure", "red", "blocked", "missing", "degraded"}


@dataclass(frozen=True)
class ValidationResult:
    status: str
    risk: str
    missing_sections: list[str]
    failed_sections: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0.0",
            "gate": "gitops_runtime_governance",
            "status": self.status,
            "risk": self.risk,
            "missing_sections": self.missing_sections,
            "failed_sections": self.failed_sections,
            "warnings": self.warnings,
        }


def load_json(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Arquivo de evidência não encontrado: {file_path}")
    return json.loads(file_path.read_text(encoding="utf-8"))


def _normalize_status(value: Any) -> str:
    return str(value or "missing").strip().lower()


def _section_status(section: Any) -> str:
    if not isinstance(section, dict):
        return "missing"
    return _normalize_status(section.get("status"))


def validate_evidence(payload: dict[str, Any]) -> ValidationResult:
    missing_sections: list[str] = []
    failed_sections: list[str] = []
    warnings: list[str] = []

    for section_name in REQUIRED_SECTIONS:
        section = payload.get(section_name)
        status = _section_status(section)
        if status == "missing":
            missing_sections.append(section_name)
            continue
        if status in FAILURE_STATUSES:
            failed_sections.append(section_name)
        if status not in SUCCESS_STATUSES and status not in FAILURE_STATUSES:
            warnings.append(f"Status não canônico em {section_name}: {status}")

        evidence = section.get("evidencia") if isinstance(section, dict) else None
        if status in SUCCESS_STATUSES and not evidence:
            warnings.append(f"Seção {section_name} marcada como verde sem campo evidencia")

    if missing_sections or failed_sections:
        return ValidationResult(
            status="failed",
            risk="high",
            missing_sections=missing_sections,
            failed_sections=failed_sections,
            warnings=warnings,
        )

    if warnings:
        return ValidationResult(
            status="warning",
            risk="medium",
            missing_sections=missing_sections,
            failed_sections=failed_sections,
            warnings=warnings,
        )

    return ValidationResult(
        status="passed",
        risk="low",
        missing_sections=missing_sections,
        failed_sections=failed_sections,
        warnings=warnings,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate GitOps runtime governance evidence")
    parser.add_argument("--input", required=True, help="Path to evidence JSON")
    parser.add_argument("--output", help="Optional path to write normalized validation result")
    args = parser.parse_args()

    result = validate_evidence(load_json(args.input))
    serialized = json.dumps(result.to_dict(), indent=2, ensure_ascii=False) + "\n"

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")

    return 0 if result.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
