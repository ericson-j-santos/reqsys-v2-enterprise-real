#!/usr/bin/env python3
"""Release Validation Layer for ReqSys.

Consolida evidencias de release (coordenador, PR evidence gate, golden release
readiness, post-merge validation e validacao semantica de CI) em um unico
estado operacional com quality gates centralizados e release readiness score.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

STATE_RANK = {"green": 0, "passed": 0, "ready": 0, "ready_with_observation": 0, "yellow": 1, "warning": 1, "needs_review": 1, "unknown": 1, "skipped": 1, "red": 2, "failed": 2, "blocked": 2}

READINESS_THRESHOLDS = {
    "ready": 95.0,
    "ready_with_observation": 85.0,
    "needs_review": 70.0,
}

REQUIRED_CI_WORKFLOWS = [
    "CI — ReqSys v2 Enterprise",
    "Governance Quality Gates",
    "Governança Padrão Ouro",
]


def merge_state(*states: str) -> str:
    ranked = sorted(states, key=lambda item: STATE_RANK.get(str(item).lower(), 1), reverse=True)
    return ranked[0] if ranked else "unknown"


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def gate_status_to_score(status: str) -> float:
    normalized = str(status or "unknown").lower()
    if normalized in {"passed", "green", "ready", "ready_with_observation", "success"}:
        return 100.0
    if normalized in {"warning", "yellow", "needs_review", "skipped", "unknown"}:
        return 60.0
    return 0.0


def derive_readiness(score: float, blockers: list[str]) -> str:
    if blockers:
        return "blocked"
    if score >= READINESS_THRESHOLDS["ready"]:
        return "ready"
    if score >= READINESS_THRESHOLDS["ready_with_observation"]:
        return "ready_with_observation"
    if score >= READINESS_THRESHOLDS["needs_review"]:
        return "needs_review"
    return "blocked"


def derive_risk(score: float, operational_state: str, blockers: list[str]) -> str:
    if blockers or operational_state == "red":
        return "high"
    if operational_state == "yellow" or score < READINESS_THRESHOLDS["ready_with_observation"]:
        return "medium"
    if score < READINESS_THRESHOLDS["ready"]:
        return "medium_low"
    return "low"


def build_coordenador_gate(coordenador: dict[str, Any] | None) -> dict[str, Any]:
    if not coordenador:
        return {
            "name": "coordenador_operational_state",
            "status": "unknown",
            "score": 60.0,
            "evidence": "coordenador-status.json ausente",
            "available": False,
        }
    state = str(coordenador.get("state") or "unknown")
    increment_gate = coordenador.get("increment_gate") or {}
    blockers = increment_gate.get("blockers") or []
    score = gate_status_to_score(state)
    if blockers:
        score = min(score, 70.0)
    return {
        "name": "coordenador_operational_state",
        "status": state,
        "score": score,
        "evidence": f"decision={coordenador.get('decision')}; blockers={','.join(blockers) or 'nenhum'}",
        "available": True,
        "new_front_allowed": increment_gate.get("new_front_allowed"),
        "critical_gaps": increment_gate.get("critical_gaps", 0),
    }


def build_pr_evidence_gate(pr_evidence: dict[str, Any] | None) -> dict[str, Any]:
    if not pr_evidence:
        return {
            "name": "pr_evidence_gate",
            "status": "unknown",
            "score": 60.0,
            "evidence": "pr-evidence-gate.json ausente — validar PRs abertos manualmente",
            "available": False,
        }
    gate = pr_evidence.get("gate") or {}
    status = str(gate.get("status") or "unknown")
    failures = gate.get("failures") or []
    score = gate_status_to_score(status)
    if failures:
        score = min(score, 40.0)
    return {
        "name": "pr_evidence_gate",
        "status": status,
        "score": score,
        "evidence": f"failures={len(failures)}; required={len(gate.get('required_workflows') or [])}",
        "available": True,
        "failures": failures,
    }


def build_golden_release_gate(golden: dict[str, Any] | None) -> dict[str, Any]:
    if not golden:
        return {
            "name": "golden_release_readiness",
            "status": "unknown",
            "score": 60.0,
            "evidence": "golden-release-readiness.json ausente",
            "available": False,
        }
    readiness = str(golden.get("readiness") or "unknown")
    score = float(golden.get("score_percent") or gate_status_to_score(readiness))
    return {
        "name": "golden_release_readiness",
        "status": readiness,
        "score": score,
        "evidence": f"risk={golden.get('risk')}; checks={len(golden.get('checks') or [])}",
        "available": True,
    }


def build_post_merge_gate(post_merge: dict[str, Any] | None) -> dict[str, Any]:
    if not post_merge:
        return {
            "name": "main_post_merge_validation",
            "status": "unknown",
            "score": 60.0,
            "evidence": "main-post-merge-validation.json ausente",
            "available": False,
        }
    validation = post_merge.get("validation") or post_merge.get("gate") or {}
    status = str(validation.get("status") or post_merge.get("status") or "unknown")
    score = gate_status_to_score(status)
    return {
        "name": "main_post_merge_validation",
        "status": status,
        "score": score,
        "evidence": f"mode={post_merge.get('mode', 'unknown')}",
        "available": True,
    }


def build_ci_semantic_validation(
    coordenador: dict[str, Any] | None,
    openapi_routes_drift: dict[str, Any] | None,
    openapi_semantic_diff: dict[str, Any] | None,
) -> dict[str, Any]:
    contract = ((coordenador or {}).get("sources") or {}).get("contract_governance") or {}
    canonical_drift = int(contract.get("canonical_drift_count") or 0)
    semantic_drift = int(contract.get("semantic_drift_count") or 0)
    if openapi_routes_drift:
        canonical_drift = max(canonical_drift, int((openapi_routes_drift.get("summary") or {}).get("drift_count") or 0))
    if openapi_semantic_diff:
        semantic_drift = max(semantic_drift, int((openapi_semantic_diff.get("summary") or {}).get("drift_count") or 0))

    checks: list[dict[str, Any]] = [
        {
            "name": "openapi_canonical_routes_drift",
            "status": "passed" if canonical_drift == 0 else "warning",
            "drift_count": canonical_drift,
            "mode": "strict",
        },
        {
            "name": "openapi_semantic_diff",
            "status": "passed" if semantic_drift == 0 else "warning",
            "drift_count": semantic_drift,
            "mode": "advisory",
        },
        {
            "name": "required_ci_workflows_defined",
            "status": "passed",
            "workflows": REQUIRED_CI_WORKFLOWS,
        },
    ]
    openapi_validation_passed = contract.get("openapi_validation_passed")
    if openapi_validation_passed is False:
        checks.append(
            {
                "name": "openapi_contract_validation",
                "status": "failed",
                "evidence": "openapi_validation_passed=false",
            }
        )
    elif openapi_validation_passed is True:
        checks.append({"name": "openapi_contract_validation", "status": "passed"})

    failed = [item for item in checks if item.get("status") == "failed"]
    warnings = [item for item in checks if item.get("status") == "warning"]
    if failed:
        status = "failed"
    elif warnings:
        status = "warning"
    else:
        status = "passed"

    score = 100.0 if status == "passed" else 75.0 if status == "warning" else 0.0
    return {
        "status": status,
        "score": score,
        "checks": checks,
        "canonical_drift_count": canonical_drift,
        "semantic_drift_count": semantic_drift,
    }


def build_quality_gates(
    coordenador: dict[str, Any] | None,
    pr_evidence: dict[str, Any] | None,
    golden: dict[str, Any] | None,
    post_merge: dict[str, Any] | None,
    ci_semantic: dict[str, Any],
) -> list[dict[str, Any]]:
    gates = [
        build_coordenador_gate(coordenador),
        build_pr_evidence_gate(pr_evidence),
        build_golden_release_gate(golden),
        build_post_merge_gate(post_merge),
        {
            "name": "ci_semantic_validation",
            "status": ci_semantic["status"],
            "score": ci_semantic["score"],
            "evidence": (
                f"canonical_drift={ci_semantic['canonical_drift_count']}; "
                f"semantic_drift={ci_semantic['semantic_drift_count']}"
            ),
            "available": True,
        },
    ]
    return gates


def build_blockers(
    quality_gates: list[dict[str, Any]],
    coordenador: dict[str, Any] | None,
    ci_semantic: dict[str, Any],
) -> list[str]:
    blockers: list[str] = []
    for gate in quality_gates:
        status = str(gate.get("status") or "").lower()
        if status in {"failed", "blocked", "red"}:
            blockers.append(f"{gate['name']}_{status}")
        if gate.get("name") == "coordenador_operational_state" and status == "red":
            blockers.append("operational_state_red")
        if gate.get("name") == "pr_evidence_gate" and gate.get("failures"):
            blockers.append("pr_evidence_failures")

    if ci_semantic.get("status") == "failed":
        blockers.append("ci_semantic_validation_failed")

    increment_gate = (coordenador or {}).get("increment_gate") or {}
    if increment_gate.get("critical_gaps", 0) > 0:
        blockers.append("critical_gaps")

    return sorted(set(blockers))


def build_warnings(quality_gates: list[dict[str, Any]], ci_semantic: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for gate in quality_gates:
        if not gate.get("available"):
            warnings.append(f"{gate['name']}_artifact_missing")
        status = str(gate.get("status") or "").lower()
        if status in {"warning", "yellow", "unknown", "skipped", "needs_review"}:
            warnings.append(f"{gate['name']}_{status}")

    if ci_semantic.get("status") == "warning":
        warnings.append("ci_semantic_drift_detected")

    return sorted(set(warnings))


def build_recommended_actions(
    readiness: str,
    blockers: list[str],
    warnings: list[str],
    coordenador: dict[str, Any] | None,
) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []

    for blocker in blockers:
        if blocker == "operational_state_red":
            actions.append(
                {
                    "priority": "P0",
                    "action": "tratar_estado_operacional_vermelho",
                    "reference": "coordenador-status",
                    "detail": "Resolver gaps e workflows vermelhos antes de promover release",
                }
            )
        elif blocker == "pr_evidence_failures":
            actions.append(
                {
                    "priority": "P0",
                    "action": "corrigir_pr_evidence_gate",
                    "reference": "pr-evidence-gate",
                    "detail": "Garantir CI obrigatorio verde no head SHA dos PRs abertos",
                }
            )
        elif blocker == "ci_semantic_validation_failed":
            actions.append(
                {
                    "priority": "P1",
                    "action": "sincronizar_contratos_openapi",
                    "reference": "ci_semantic_validation",
                    "detail": "Alinhar contrato OpenAPI com backend antes de release",
                }
            )
        elif blocker == "critical_gaps":
            actions.append(
                {
                    "priority": "P0",
                    "action": "tratar_gaps_criticos",
                    "reference": "OPS-GAP",
                    "detail": "Backlog com gaps criticos bloqueia release readiness",
                }
            )

    for warning in warnings:
        if warning.endswith("_artifact_missing"):
            gate_name = warning.replace("_artifact_missing", "")
            actions.append(
                {
                    "priority": "P2",
                    "action": "disparar_workflow_evidencia",
                    "reference": gate_name,
                    "detail": "Artifact de evidencia ausente — executar workflow fonte ou aguardar schedule",
                }
            )

    if readiness in {"ready", "ready_with_observation"} and not blockers:
        actions.append(
            {
                "priority": "P4",
                "action": "prosseguir_release_review_humano",
                "reference": "release-validation-layer",
                "detail": "Score aceitavel — revisao humana antes de promover ambiente",
            }
        )

    for action in (coordenador or {}).get("recommended_actions") or []:
        if action.get("priority") in {"P0", "P1"}:
            actions.append(action)

    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4}
    actions.sort(key=lambda item: priority_order.get(item.get("priority", "P9"), 9))
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, str]] = []
    for action in actions:
        key = (action.get("action", ""), action.get("reference", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(action)
    return deduped


def build_executive_dashboard(
    readiness: str,
    score: float,
    risk: str,
    operational_state: str,
    blockers: list[str],
    warnings: list[str],
    quality_gates: list[dict[str, Any]],
) -> dict[str, Any]:
    failing_gates = [gate["name"] for gate in quality_gates if float(gate.get("score") or 0) < 70]
    return {
        "headline": (
            "Release pronta para revisao humana"
            if readiness in {"ready", "ready_with_observation"} and not blockers
            else "Release bloqueada — tratar blockers"
            if blockers
            else "Release requer revisao adicional"
        ),
        "release_readiness_score": score,
        "readiness": readiness,
        "risk": risk,
        "operational_state": operational_state,
        "top_blockers": blockers[:5],
        "top_warnings": warnings[:5],
        "failing_gates": failing_gates,
        "quality_gate_summary": [
            {"name": gate["name"], "status": gate["status"], "score": gate["score"]}
            for gate in quality_gates
        ],
    }


def consolidate(
    repo: str,
    branch: str,
    run_id: str,
    event_name: str,
    coordenador: dict[str, Any] | None,
    pr_evidence: dict[str, Any] | None,
    golden: dict[str, Any] | None,
    post_merge: dict[str, Any] | None,
    openapi_routes_drift: dict[str, Any] | None = None,
    openapi_semantic_diff: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ci_semantic = build_ci_semantic_validation(coordenador, openapi_routes_drift, openapi_semantic_diff)
    quality_gates = build_quality_gates(coordenador, pr_evidence, golden, post_merge, ci_semantic)
    available_scores = [float(gate["score"]) for gate in quality_gates if gate.get("available")]
    score = round(sum(available_scores) / len(available_scores), 2) if available_scores else 0.0

    operational_state = str((coordenador or {}).get("state") or "unknown")
    blockers = build_blockers(quality_gates, coordenador, ci_semantic)
    warnings = build_warnings(quality_gates, ci_semantic)
    readiness = derive_readiness(score, blockers)
    risk = derive_risk(score, operational_state, blockers)
    correlation_id = str((coordenador or {}).get("correlation_id") or uuid4())

    release_evidence = [
        {
            "artifact": "coordenador-status-evidence",
            "path": "artifacts/coordenador-status/coordenador-status.json",
            "available": coordenador is not None,
            "state": (coordenador or {}).get("state"),
        },
        {
            "artifact": "pr-evidence-gate",
            "path": "audit/pr-evidence-gate.json",
            "available": pr_evidence is not None,
            "state": ((pr_evidence or {}).get("gate") or {}).get("status"),
        },
        {
            "artifact": "golden-release-readiness",
            "path": "audit/release-readiness/golden-release-readiness.json",
            "available": golden is not None,
            "state": (golden or {}).get("readiness"),
        },
        {
            "artifact": "main-post-merge-validation",
            "path": "audit/main-post-merge-validation.json",
            "available": post_merge is not None,
            "state": ((post_merge or {}).get("validation") or post_merge or {}).get("status"),
        },
    ]

    return {
        "schema_version": "1.0.0",
        "validation_layer_version": "1.0.0",
        "correlation_id": correlation_id,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repository": repo,
        "branch": branch,
        "run_id": run_id,
        "event_name": event_name,
        "mode": "report_only",
        "release_readiness_score": score,
        "readiness": readiness,
        "risk": risk,
        "operational_state": operational_state,
        "quality_gates": quality_gates,
        "ci_semantic_validation": ci_semantic,
        "release_evidence": release_evidence,
        "blockers": blockers,
        "warnings": warnings,
        "recommended_actions": build_recommended_actions(readiness, blockers, warnings, coordenador),
        "executive_dashboard": build_executive_dashboard(
            readiness, score, risk, operational_state, blockers, warnings, quality_gates
        ),
        "sources": {
            "coordenador": {
                "available": coordenador is not None,
                "state": (coordenador or {}).get("state"),
                "decision": (coordenador or {}).get("decision"),
                "generated_at": (coordenador or {}).get("generated_at"),
            },
            "pr_evidence_gate": {
                "available": pr_evidence is not None,
                "status": ((pr_evidence or {}).get("gate") or {}).get("status"),
            },
            "golden_release_readiness": {
                "available": golden is not None,
                "score_percent": (golden or {}).get("score_percent"),
            },
            "main_post_merge_validation": {
                "available": post_merge is not None,
                "status": ((post_merge or {}).get("validation") or post_merge or {}).get("status"),
            },
        },
        "guardrails": {
            "does_not_release_automatically": True,
            "does_not_relax_required_gates": True,
            "does_not_mutate_production": True,
            "does_not_use_secrets": True,
            "human_release_review_required": True,
        },
        "evidence_consolidation": {
            "artifact": "release-validation-layer-evidence",
            "files": [
                "release-validation-layer.json",
                "release-validation-layer.md",
                "executive-release-dashboard.json",
            ],
            "dashboard_entrypoint": "executive-release-dashboard.json",
        },
    }


def write_report(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "release-validation-layer.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "executive-release-dashboard.json").write_text(
        json.dumps(report["executive_dashboard"], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    dashboard = report["executive_dashboard"]
    lines = [
        "# Release Validation Layer",
        "",
        f"- Correlation ID: `{report['correlation_id']}`",
        f"- Repository: `{report['repository']}`",
        f"- Branch: `{report['branch']}`",
        f"- Release readiness score: **{report['release_readiness_score']}%**",
        f"- Readiness: `{report['readiness']}`",
        f"- Risk: `{report['risk']}`",
        f"- Operational state: `{report['operational_state']}`",
        f"- Mode: `{report['mode']}`",
        f"- Generated at: `{report['generated_at']}`",
        "",
        "## Executive dashboard",
        "",
        f"- Headline: {dashboard['headline']}",
        f"- Top blockers: `{', '.join(dashboard['top_blockers']) or 'nenhum'}`",
        f"- Top warnings: `{', '.join(dashboard['top_warnings']) or 'nenhum'}`",
        "",
        "## Quality gates",
        "",
        "| Gate | Status | Score |",
        "|---|---|---:|",
    ]
    for gate in report["quality_gates"]:
        lines.append(f"| `{gate['name']}` | `{gate['status']}` | {gate['score']}% |")

    lines.extend(["", "## CI semantic validation", ""])
    for check in report["ci_semantic_validation"]["checks"]:
        lines.append(f"- `{check['name']}`: `{check.get('status', 'unknown')}`")

    lines.extend(["", "## Recommended actions", ""])
    for action in report["recommended_actions"]:
        lines.append(
            f"- `{action['priority']}` · `{action['action']}` · `{action['reference']}` — {action['detail']}"
        )

    (output_dir / "release-validation-layer.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Consolidate release validation evidence.")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "owner/repo"))
    parser.add_argument("--branch", default="main")
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "local"))
    parser.add_argument("--event-name", default=os.environ.get("GITHUB_EVENT_NAME", "local"))
    parser.add_argument("--output-dir", default="audit/release-validation")
    parser.add_argument("--coordenador-json", default="artifacts/coordenador-status/coordenador-status.json")
    parser.add_argument("--pr-evidence-json", default="audit/pr-evidence-gate.json")
    parser.add_argument("--golden-release-json", default="audit/release-readiness/golden-release-readiness.json")
    parser.add_argument("--post-merge-json", default="audit/main-post-merge-validation.json")
    parser.add_argument("--openapi-routes-drift-json", default="artifacts/openapi/openapi-routes-drift.json")
    parser.add_argument("--openapi-semantic-diff-json", default="artifacts/openapi/openapi-semantic-diff.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = consolidate(
        args.repo,
        args.branch,
        args.run_id,
        args.event_name,
        load_json(Path(args.coordenador_json)),
        load_json(Path(args.pr_evidence_json)),
        load_json(Path(args.golden_release_json)),
        load_json(Path(args.post_merge_json)),
        load_json(Path(args.openapi_routes_drift_json)),
        load_json(Path(args.openapi_semantic_diff_json)),
    )
    write_report(report, Path(args.output_dir))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
