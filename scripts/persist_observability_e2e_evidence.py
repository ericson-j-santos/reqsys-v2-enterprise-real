#!/usr/bin/env python3
"""Persiste evidência do gate Observability E2E em audit/runtime/."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_evidence_index(
    validation: dict[str, Any],
    *,
    repository: str,
    run_id: str,
    event_name: str,
    sha: str,
    upstream_workflow: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "contract": "observability-e2e-evidence-index",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": repository,
        "run_id": run_id,
        "event_name": event_name,
        "sha": sha,
        "workflow": "evidence-automation-observability-e2e",
        "increment_id": "evidence-automation-observability-e2e",
        "upstream_workflow": upstream_workflow,
        "gate_passed": bool(validation.get("gate_passed")),
        "precondition_ok": bool(validation.get("precondition_ok")),
        "source_paths": {
            "validation": "audit/runtime/observability-e2e-validation.json",
            "index": "audit/runtime/observability-e2e-evidence-index.json",
        },
        "summary": {
            "base_url": validation.get("base_url", ""),
            "environment": validation.get("environment", "prod"),
            "success_percentual": validation.get("success_percentual"),
            "ok": validation.get("ok"),
            "total": validation.get("total"),
            "blocking_issues": validation.get("blocking_issues", []),
        },
        "operational_notes": _operational_notes(validation),
        "consumers": [
            "docs/ops-dashboard/index.html",
            "scripts/generate_ops_dashboard_data.py",
            "docs/dashboard/live-operational-dashboard.dynamic.html",
        ],
    }


def _operational_notes(validation: dict[str, Any]) -> list[dict[str, Any]]:
    if validation.get("gate_passed"):
        return [
            {
                "id": "observability_e2e_ready",
                "severity": "info",
                "scope": "observability_e2e",
                "wire_scope": True,
                "message": "Observabilidade runtime pública validada (métricas, dashboard, analytics, correlation_id).",
            }
        ]
    if not validation.get("precondition_ok"):
        return [
            {
                "id": "fly_runtime_deploy_lag",
                "severity": "blocker",
                "scope": "fly_runtime_deploy",
                "wire_scope": False,
                "message": (
                    "Observability E2E bloqueado: strict precondition falhou. "
                    "Executar fly-runtime-p0-deploy antes deste incremento."
                ),
                "next_increment": "fly-runtime-p0-deploy",
                "blocks_increment": "evidence-automation-observability-e2e",
            }
        ]
    return [
        {
            "id": "observability_e2e_degraded",
            "severity": "warning",
            "scope": "observability_e2e",
            "wire_scope": True,
            "message": "Precondition strict verde, mas checks de observabilidade falharam.",
            "reference": "docs/runbooks/evidence-automation-observability-e2e.md",
        }
    ]


def build_markdown(index: dict[str, Any]) -> str:
    summary = index.get("summary") or {}
    blocking = summary.get("blocking_issues") or []
    blocking_lines = [f"- {issue}" for issue in blocking] if blocking else ["- nenhum"]
    lines = [
        "# Observability E2E Evidence — Audit Snapshot",
        "",
        f"- Repository: `{index.get('repository', 'unknown')}`",
        f"- Generated at: `{index.get('generated_at', '')}`",
        f"- Run ID: `{index.get('run_id', '')}`",
        f"- Gate passed: `{index.get('gate_passed')}`",
        f"- Precondition OK: `{index.get('precondition_ok')}`",
        f"- Base URL: `{summary.get('base_url', '')}`",
        f"- Success: `{summary.get('success_percentual', 0)}%` ({summary.get('ok', 0)}/{summary.get('total', 0)})",
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
    output_dir: Path,
    *,
    repository: str = "local",
    run_id: str = "local",
    event_name: str = "local",
    sha: str = "local",
    upstream_workflow: str | None = None,
) -> dict[str, Any]:
    validation = _load_json(validation_path)
    if not validation:
        raise FileNotFoundError(f"Evidência ausente em {validation_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    validation_out = output_dir / "observability-e2e-validation.json"
    index_out = output_dir / "observability-e2e-evidence-index.json"
    markdown_out = output_dir / "observability-e2e-evidence.md"

    validation_out.write_text(json.dumps(validation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    index = build_evidence_index(
        validation,
        repository=repository,
        run_id=run_id,
        event_name=event_name,
        sha=sha,
        upstream_workflow=upstream_workflow,
    )
    index_out.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    markdown_out.write_text(build_markdown(index), encoding="utf-8")
    return index


def main() -> int:
    parser = argparse.ArgumentParser(description="Persiste evidência Observability E2E em audit/runtime/")
    parser.add_argument("--validation", default="artifacts/runtime/observability-e2e-validation.json")
    parser.add_argument("--output-dir", default="audit/runtime")
    parser.add_argument("--repository", default="local")
    parser.add_argument("--run-id", default="local")
    parser.add_argument("--event-name", default="local")
    parser.add_argument("--sha", default="local")
    parser.add_argument("--upstream-workflow", default="")
    args = parser.parse_args()

    try:
        index = persist_evidence(
            Path(args.validation),
            Path(args.output_dir),
            repository=args.repository,
            run_id=args.run_id,
            event_name=args.event_name,
            sha=args.sha,
            upstream_workflow=args.upstream_workflow or None,
        )
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(index, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
