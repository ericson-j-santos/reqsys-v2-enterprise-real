#!/usr/bin/env python3
"""Validate Operational Runtime Governance Pareto artifacts.

The validator is intentionally read-only and does not call external services.
It checks only versioned repository files required by the governance consolidation layer.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "docs/ops-dashboard/data/operational-runtime-governance-consolidation.json"
RUNBOOK_PATH = ROOT / "docs/runbooks/operational-runtime-governance-consolidation.md"
CONTRACT_PATH = ROOT / "docs/contracts/runtime-contract-governance-pareto.md"
POWER_PLATFORM_PATH = ROOT / "docs/runbooks/power-platform-runtime-layer-pareto.md"

REQUIRED_INDEX_KEYS = {
    "schema_version",
    "generated_at",
    "repo",
    "strategy",
    "mode",
    "overall",
    "canonical_sources",
    "pareto_lanes",
    "guardrails",
}

REQUIRED_LANES = {
    "ci_recovery_runtime_stability",
    "governance_hub_consolidated",
    "runtime_observability_p1",
    "contract_governance",
    "power_platform_runtime_layer",
}

REQUIRED_GUARDRAILS = {
    "secrets_in_git",
    "production_mutation_without_human_approval",
    "workflow_auto_rerun",
    "dashboard_duplication",
    "contract_breaking_change_without_version_bump",
}


def fail(message: str) -> None:
    raise AssertionError(message)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        fail(f"required file not found: {path.relative_to(ROOT)}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid json in {path.relative_to(ROOT)}: {exc}")
    if not isinstance(data, dict):
        fail(f"expected object in {path.relative_to(ROOT)}")
    return data


def require_markdown(path: Path, required_terms: list[str]) -> None:
    if not path.exists():
        fail(f"required file not found: {path.relative_to(ROOT)}")
    text = path.read_text(encoding="utf-8")
    for term in required_terms:
        if term not in text:
            fail(f"missing term {term!r} in {path.relative_to(ROOT)}")


def validate_index() -> None:
    data = load_json(INDEX_PATH)
    missing = REQUIRED_INDEX_KEYS - set(data)
    if missing:
        fail(f"missing top-level index keys: {sorted(missing)}")

    if data["repo"] != "ericson-j-santos/reqsys-v2-enterprise-real":
        fail("unexpected repo value")

    lanes = data.get("pareto_lanes")
    if not isinstance(lanes, list) or not lanes:
        fail("pareto_lanes must be a non-empty list")

    lane_ids = {lane.get("id") for lane in lanes if isinstance(lane, dict)}
    missing_lanes = REQUIRED_LANES - lane_ids
    if missing_lanes:
        fail(f"missing required pareto lanes: {sorted(missing_lanes)}")

    for lane in lanes:
        if not isinstance(lane, dict):
            fail("each pareto lane must be an object")
        for key in ("id", "priority", "status", "impact", "risk", "target_outcome", "minimum_evidence", "next_actions"):
            if key not in lane:
                fail(f"lane {lane.get('id', '<unknown>')} missing {key}")
        if not isinstance(lane["minimum_evidence"], list) or not lane["minimum_evidence"]:
            fail(f"lane {lane['id']} must define minimum evidence")
        if not isinstance(lane["next_actions"], list) or not lane["next_actions"]:
            fail(f"lane {lane['id']} must define next actions")

    guardrails = data.get("guardrails")
    if not isinstance(guardrails, dict):
        fail("guardrails must be an object")
    missing_guardrails = REQUIRED_GUARDRAILS - set(guardrails)
    if missing_guardrails:
        fail(f"missing guardrails: {sorted(missing_guardrails)}")

    canonical_sources = data.get("canonical_sources")
    if not isinstance(canonical_sources, list) or not canonical_sources:
        fail("canonical_sources must be a non-empty list")
    for source in canonical_sources:
        if not isinstance(source, dict):
            fail("each canonical source must be an object")
        for key in ("id", "path", "type", "required"):
            if key not in source:
                fail(f"canonical source {source.get('id', '<unknown>')} missing {key}")


def validate_docs() -> None:
    require_markdown(
        RUNBOOK_PATH,
        ["Operational Runtime Governance Consolidation", "Quality gates obrigatórios", "Política Pareto"],
    )
    require_markdown(
        CONTRACT_PATH,
        ["Runtime Contract Governance", "correlation_id", "Schema version"],
    )
    require_markdown(
        POWER_PLATFORM_PATH,
        ["Power Platform Runtime Layer", "GET /api/power-platform/requisitos/{id}", "POST /api/power-platform/respostas"],
    )


def main() -> int:
    try:
        validate_index()
        validate_docs()
    except AssertionError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1

    print(json.dumps({"status": "passed", "validated": "operational_runtime_governance"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
