#!/usr/bin/env python3
"""Inventory production mutation paths and governance gate coverage."""
from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROD_ENVIRONMENT = re.compile(r"environment:\s*production", re.IGNORECASE)
PROD_TARGET_PATTERNS = (
    re.compile(r"--environment\s+prod(?:uction)?(?=\s|$)", re.IGNORECASE),
    re.compile(r"--app\s+reqsys-(?:api|app)(?=\s|$|[\"'])", re.IGNORECASE),
    re.compile(r"https://reqsys-(?:api|app)\.fly\.dev", re.IGNORECASE),
)
NONPROD_TARGET_PATTERNS = (
    re.compile(r"environment:\s*(?:staging|development|dev)\b", re.IGNORECASE),
    re.compile(r"--environment\s+(?:stg|staging|dev|development)(?=\s|$)", re.IGNORECASE),
    re.compile(
        r"--app\s+reqsys-(?:api|app)-(?:stg|dev)(?=\s|$|[\"'])",
        re.IGNORECASE,
    ),
    re.compile(r"https://reqsys-(?:api|app)-(?:stg|dev)\.fly\.dev", re.IGNORECASE),
    re.compile(r"fly\.(?:staging|development|dev)\.toml", re.IGNORECASE),
)
MUTATION_PATTERNS = (
    re.compile(r"flyctl\s+deploy", re.IGNORECASE),
    re.compile(r"flyctl\s+secrets\s+(?:set|unset|import)", re.IGNORECASE),
    re.compile(r"flyctl\s+(?:scale|machine|machines|apps\s+destroy)", re.IGNORECASE),
    re.compile(r"configurar_fly_auth_azure\.py", re.IGNORECASE),
)
PROTECTION_MARKERS = (
    "REQSYS_PRODUCTION_GOVERNANCE_GATE",
    "generate_bacen_nonprod_tolerance_decision.py",
    "evaluate_environment_promotion_gate.py",
    "environment-promotion-readiness-gate.yml",
)
STRUCTURAL_PROTECTION_REQUIREMENTS = (
    "environment: production",
    "needs.evaluate-stg.outputs.prod_allowed == 'true'",
    "inputs.approve_prod == 'APROVO-PROD'",
    "prod_rollout_candidate_requires_approval",
    "gh pr create",
)
STRUCTURAL_PROTECTION_MARKER = "production_environment+stg_evidence+human_approval+pr_only"
EXCLUDED_SELF = "production-gate-coverage-inventory.yml"


def matching_patterns(patterns: tuple[re.Pattern[str], ...], text: str) -> list[str]:
    return sorted(pattern.pattern for pattern in patterns if pattern.search(text))


def detect_protection_markers(text: str) -> list[str]:
    markers = [marker for marker in PROTECTION_MARKERS if marker in text]
    if all(requirement in text for requirement in STRUCTURAL_PROTECTION_REQUIREMENTS):
        markers.append(STRUCTURAL_PROTECTION_MARKER)
    return sorted(markers)


def inspect_workflow(path: Path, root: Path) -> dict[str, Any] | None:
    text = path.read_text(encoding="utf-8")
    relative = path.relative_to(root.parent.parent).as_posix()
    if path.name == EXCLUDED_SELF:
        return None

    production_environment_access = PROD_ENVIRONMENT.search(text) is not None
    production_target_signals = matching_patterns(PROD_TARGET_PATTERNS, text)
    nonproduction_target_signals = matching_patterns(NONPROD_TARGET_PATTERNS, text)
    mutation_signals = matching_patterns(MUTATION_PATTERNS, text)

    if (
        not production_environment_access
        and not production_target_signals
        and not mutation_signals
    ):
        return None

    if production_environment_access or (
        production_target_signals and mutation_signals
    ):
        classification = "confirmed_production_mutation"
    elif mutation_signals and nonproduction_target_signals:
        classification = "nonproduction_mutation_only"
    elif mutation_signals:
        classification = "ambiguous_mutation_requires_review"
    else:
        classification = "production_observation_only"

    protection_markers = detect_protection_markers(text)
    gate_required = classification in {
        "confirmed_production_mutation",
        "ambiguous_mutation_requires_review",
    }
    return {
        "path": relative,
        "classification": classification,
        "production_environment_access": production_environment_access,
        "production_target_signals": production_target_signals,
        "nonproduction_target_signals": nonproduction_target_signals,
        "mutation_signals": mutation_signals,
        "protection_markers": protection_markers,
        "gate_required": gate_required,
        "protected": bool(protection_markers) if gate_required else None,
    }


def build_inventory(workflow_dir: Path) -> dict[str, Any]:
    workflows: list[dict[str, Any]] = []
    for pattern in ("*.yml", "*.yaml"):
        for path in sorted(workflow_dir.glob(pattern)):
            inspected = inspect_workflow(path, workflow_dir)
            if inspected:
                workflows.append(inspected)

    mutation_candidates = [item for item in workflows if item["gate_required"]]
    observations = [
        item
        for item in workflows
        if item["classification"] == "production_observation_only"
    ]
    nonproduction_mutations = [
        item
        for item in workflows
        if item["classification"] == "nonproduction_mutation_only"
    ]
    protected = [item for item in mutation_candidates if item["protected"]]
    unprotected = [item for item in mutation_candidates if not item["protected"]]
    confirmed = [
        item
        for item in mutation_candidates
        if item["classification"] == "confirmed_production_mutation"
    ]
    ambiguous = [
        item
        for item in mutation_candidates
        if item["classification"] == "ambiguous_mutation_requires_review"
    ]

    return {
        "schema_version": "1.3.0",
        "contract": "reqsys-production-gate-coverage-inventory",
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "advisory_until_all_mutation_paths_are_migrated",
        "summary": {
            "production_related_workflows": len(workflows) - len(nonproduction_mutations),
            "confirmed_mutation_workflows": len(confirmed),
            "ambiguous_mutation_workflows": len(ambiguous),
            "nonproduction_mutation_workflows": len(nonproduction_mutations),
            "observation_only_workflows": len(observations),
            "gate_required_workflows": len(mutation_candidates),
            "protected_workflows": len(protected),
            "unprotected_workflows": len(unprotected),
        },
        "workflows": workflows,
        "mutation_candidates": mutation_candidates,
        "observation_only_workflows": observations,
        "nonproduction_mutation_workflows": nonproduction_mutations,
        "unprotected_workflows": unprotected,
        "delivery_blocker": bool(unprotected),
        "automatic_enforcement_ready": not unprotected,
        "production_touched": False,
        "next_stage": (
            "enable_blocking_enforcement"
            if not unprotected
            else "migrate_each_unprotected_mutation_path_to_the_governed_production_gate"
        ),
    }


def render_issue_body(inventory: dict[str, Any]) -> str:
    summary = inventory["summary"]
    lines = [
        "<!-- reqsys-production-gate-coverage -->",
        "# Caminhos de mutação em produção sem gate governado",
        "",
        "Esta issue é mantida automaticamente pelo inventário de workflows.",
        "",
        f"- Mutação confirmada: **{summary['confirmed_mutation_workflows']}**",
        f"- Mutação ambígua para revisão: **{summary['ambiguous_mutation_workflows']}**",
        f"- Mutação explicitamente não produtiva: **{summary['nonproduction_mutation_workflows']}**",
        f"- Somente observação: **{summary['observation_only_workflows']}**",
        f"- Gate obrigatório: **{summary['gate_required_workflows']}**",
        f"- Protegidos: **{summary['protected_workflows']}**",
        f"- Não protegidos: **{summary['unprotected_workflows']}**",
        "",
        "## Pendências de mutação em produção",
        "",
    ]
    for item in inventory["unprotected_workflows"]:
        lines.append(f"- `{item['path']}` — `{item['classification']}`")

    lines.extend(["", "## Mutações não produtivas excluídas", ""])
    for item in inventory["nonproduction_mutation_workflows"]:
        lines.append(f"- `{item['path']}`")

    lines.extend(["", "## Fluxos somente leitura", ""])
    for item in inventory["observation_only_workflows"]:
        lines.append(f"- `{item['path']}`")

    lines.extend(
        [
            "",
            "## Critério de encerramento",
            "",
            "Todos os caminhos de mutação confirmada ou ambígua em produção devem consumir o gate BACEN/Environment Promotion antes de acessar secrets, environment `production` ou executar mudanças no Fly.io.",
            "",
            "`production_touched=false`",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--issue-body", type=Path, required=True)
    args = parser.parse_args()

    inventory = build_inventory(args.workflow_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.issue_body.write_text(render_issue_body(inventory), encoding="utf-8")
    print(json.dumps(inventory["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
