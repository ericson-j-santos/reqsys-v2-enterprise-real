#!/usr/bin/env python3
"""Persiste evidência pública de runtime em audit/runtime/.

Read-only: copia e enriquece artifacts do Public Runtime Evidence Gate
com metadados de execução para consumo por dashboards e índices de evidência.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RUNTIME_STRICT_ENDPOINTS = ("/api/runtime/health", "/api/runtime/readiness", "/api/runtime/liveness")
FLY_DEPLOY_LAG_NOTE = (
    "Os 404 nos endpoints strict do Fly indicam deploy anterior ao Runtime Operational "
    "Observability v1 — bloqueio evidenciado, fora do escopo wire-only (sem deploy). "
    "Corrigir exige incremento separado via ReqSys Fly Runtime P0 "
    "(workflow_dispatch deploy=true) antes de declarar produção healthy."
)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _results_by_endpoint(validation: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        result.get("endpoint", ""): result
        for result in validation.get("results", [])
        if isinstance(result, dict) and result.get("endpoint")
    }


def infer_operational_notes(
    validation: dict[str, Any],
    readiness: dict[str, Any],
    *,
    strict_gate_passed: bool,
) -> list[dict[str, Any]]:
    readiness = readiness or validation.get("readiness") or {}
    blocking = readiness.get("blocking_issues") or []
    by_endpoint = _results_by_endpoint(validation)
    health_ok = bool(by_endpoint.get("/health", {}).get("ok"))
    runtime_404s = [
        endpoint
        for endpoint in RUNTIME_STRICT_ENDPOINTS
        if by_endpoint.get(endpoint, {}).get("status_code") == 404
    ]
    has_runtime_404_blocking = any("404" in issue and "/api/runtime/" in issue for issue in blocking)

    if health_ok and runtime_404s and has_runtime_404_blocking:
        return [
            {
                "id": "fly_runtime_deploy_lag",
                "severity": "blocker",
                "scope": "fly_runtime_deploy",
                "wire_scope": False,
                "message": FLY_DEPLOY_LAG_NOTE,
                "affected_endpoints": runtime_404s,
                "next_increment": "fly-runtime-p0-deploy",
                "blocks_increment": "evidence-automation-observability-e2e",
                "reference": "docs/runbooks/public-runtime-smoke-test.md",
            }
        ]

    if not strict_gate_passed and blocking:
        return [
            {
                "id": "strict_gate_failed",
                "severity": "warning",
                "scope": "public_runtime_evidence",
                "wire_scope": None,
                "message": "Strict gate falhou; revisar blocking_issues antes de promover ambiente.",
                "reference": "docs/runbooks/public-runtime-evidence-gate.md",
            }
        ]
    return []


def build_evidence_index(
    validation: dict[str, Any],
    readiness: dict[str, Any],
    *,
    repository: str,
    run_id: str,
    event_name: str,
    sha: str,
    strict_gate_passed: bool,
) -> dict[str, Any]:
    readiness = readiness or validation.get("readiness") or {}
    operational_notes = infer_operational_notes(
        validation,
        readiness,
        strict_gate_passed=strict_gate_passed,
    )
    return {
        "schema_version": "1.1.0",
        "contract": "public-runtime-evidence-index",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": repository,
        "run_id": run_id,
        "event_name": event_name,
        "sha": sha,
        "workflow": "public-runtime-evidence",
        "strict_gate_passed": strict_gate_passed,
        "source_artifact": "public-runtime-evidence",
        "source_paths": {
            "validation": "audit/runtime/public-runtime-validation.json",
            "readiness": "audit/runtime/ops-readiness-report.json",
            "index": "audit/runtime/public-runtime-evidence-index.json",
        },
        "summary": {
            "base_url": validation.get("base_url") or readiness.get("base_url", ""),
            "environment": validation.get("environment") or readiness.get("environment", "prod"),
            "operational_status": readiness.get("operational_status", "unknown"),
            "readiness_percent": readiness.get("readiness_percent"),
            "success_percentual": validation.get("success_percentual"),
            "strict_ok": validation.get("ok"),
            "strict_total": validation.get("total"),
            "blocking_issues": readiness.get("blocking_issues", []),
        },
        "operational_notes": operational_notes,
        "consumers": [
            "docs/ops-dashboard/index.html",
            "scripts/generate_ops_dashboard_data.py",
            "docs/dashboard/live-operational-dashboard.dynamic.html",
        ],
    }


def build_markdown(index: dict[str, Any]) -> str:
    summary = index.get("summary") or {}
    blocking = summary.get("blocking_issues") or []
    blocking_lines = [f"- {issue}" for issue in blocking] if blocking else ["- nenhum"]
    lines = [
        "# Public Runtime Evidence — Audit Snapshot",
        "",
        f"- Repository: `{index.get('repository', 'unknown')}`",
        f"- Generated at: `{index.get('generated_at', '')}`",
        f"- Run ID: `{index.get('run_id', '')}`",
        f"- Strict gate passed: `{index.get('strict_gate_passed')}`",
        f"- Base URL: `{summary.get('base_url', '')}`",
        f"- Operational status: `{summary.get('operational_status', 'unknown')}`",
        f"- Readiness: `{summary.get('readiness_percent', 0)}%`",
        f"- Strict success: `{summary.get('success_percentual', 0)}%` ({summary.get('strict_ok', 0)}/{summary.get('strict_total', 0)})",
        "",
        "## Blocking issues",
        *blocking_lines,
        "",
    ]
    notes = index.get("operational_notes") or []
    if notes:
        lines.extend(["## Nota operacional", ""])
        for note in notes:
            lines.append(f"- **{note.get('id', 'nota')}**: {note.get('message', '')}")
            if note.get("next_increment"):
                lines.append(f"  - Próximo incremento: `{note['next_increment']}`")
            if note.get("blocks_increment"):
                lines.append(f"  - Bloqueia: `{note['blocks_increment']}`")
        lines.append("")
    lines.extend(
        [
        "## Consumers",
        *(f"- `{consumer}`" for consumer in index.get("consumers", [])),
        "",
        ]
    )
    return "\n".join(lines)


def persist_evidence(
    validation_path: Path,
    readiness_path: Path,
    output_dir: Path,
    *,
    repository: str = "local",
    run_id: str = "local",
    event_name: str = "local",
    sha: str = "local",
    strict_gate_passed: bool = False,
) -> dict[str, Any]:
    validation = _load_json(validation_path)
    readiness = _load_json(readiness_path)
    if not validation and not readiness:
        raise FileNotFoundError(f"Nenhuma evidência encontrada em {validation_path} ou {readiness_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    validation_out = output_dir / "public-runtime-validation.json"
    readiness_out = output_dir / "ops-readiness-report.json"
    index_out = output_dir / "public-runtime-evidence-index.json"
    markdown_out = output_dir / "public-runtime-evidence.md"

    if validation:
        validation_out.write_text(json.dumps(validation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if readiness:
        readiness_out.write_text(json.dumps(readiness, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    elif validation.get("readiness"):
        readiness_out.write_text(
            json.dumps(validation["readiness"], indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        readiness = validation["readiness"]

    index = build_evidence_index(
        validation,
        readiness,
        repository=repository,
        run_id=run_id,
        event_name=event_name,
        sha=sha,
        strict_gate_passed=strict_gate_passed,
    )
    index_out.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    markdown_out.write_text(build_markdown(index), encoding="utf-8")
    return index


def main() -> int:
    parser = argparse.ArgumentParser(description="Persiste evidência pública de runtime em audit/runtime/")
    parser.add_argument("--validation", default="artifacts/runtime/public-runtime-validation.json")
    parser.add_argument("--readiness", default="artifacts/runtime/ops-readiness-report.json")
    parser.add_argument("--output-dir", default="audit/runtime")
    parser.add_argument("--repository", default="local")
    parser.add_argument("--run-id", default="local")
    parser.add_argument("--event-name", default="local")
    parser.add_argument("--sha", default="local")
    parser.add_argument(
        "--strict-gate-passed",
        choices=("true", "false", "auto"),
        default="auto",
        help="auto infere a partir do payload de validação",
    )
    args = parser.parse_args()

    validation_path = Path(args.validation)
    readiness_path = Path(args.readiness)
    if args.strict_gate_passed == "auto":
        validation = _load_json(validation_path)
        strict_gate_passed = bool(validation) and validation.get("ok") == validation.get("total") and validation.get("total", 0) > 0
    else:
        strict_gate_passed = args.strict_gate_passed == "true"

    try:
        index = persist_evidence(
            validation_path,
            readiness_path,
            Path(args.output_dir),
            repository=args.repository,
            run_id=args.run_id,
            event_name=args.event_name,
            sha=args.sha,
            strict_gate_passed=strict_gate_passed,
        )
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(index, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
