#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EXPECTED_COMPONENTS = {
    "executive": "BACEN-08",
    "narrative": "BACEN-08",
    "incident_linkage": "BACEN-08",
    "action_plan": "BACEN-08",
}
VALID_STATUSES = {"partial", "implemented"}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON inválido: {path}")
    return payload


def build_consolidated(
    matrix_path: Path,
    executive_path: Path,
    narrative_path: Path,
    incident_path: Path,
    action_plan_path: Path,
) -> dict[str, Any]:
    paths = {
        "executive": executive_path,
        "narrative": narrative_path,
        "incident_linkage": incident_path,
        "action_plan": action_plan_path,
    }
    findings: list[str] = []
    components: dict[str, dict[str, Any]] = {}

    for name, path in paths.items():
        if not path.exists():
            findings.append(f"component_evidence_missing:{name}")
            continue
        evidence = load_json(path)
        control_id = str(evidence.get("control_id") or "")
        status = str(evidence.get("control_status") or "").lower()
        if control_id != EXPECTED_COMPONENTS[name]:
            findings.append(f"invalid_component_control_id:{name}")
        if status not in VALID_STATUSES:
            findings.append(f"invalid_component_status:{name}")
        if evidence.get("production_touched") is not False:
            findings.append(f"component_touched_production:{name}")
        if evidence.get("automatic_blocking") is True:
            findings.append(f"component_blocking:{name}")

        components[name] = {
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "control_status": status or None,
            "automatic_blocking": bool(evidence.get("automatic_blocking", False)),
            "human_action_required": bool(evidence.get("human_action_required", False)),
        }

    executive = load_json(executive_path) if executive_path.exists() else {}
    narrative = load_json(narrative_path) if narrative_path.exists() else {}
    incident = load_json(incident_path) if incident_path.exists() else {}
    action_plan = load_json(action_plan_path) if action_plan_path.exists() else {}

    technical_checks = {
        "executive_structure_ready": bool(executive.get("technical_readiness_passed")),
        "narrative_structure_ready": not bool(narrative.get("automatic_blocking", True)),
        "incident_linkage_ready": bool(incident.get("required_incident_linkage_complete")),
        "action_plan_structure_ready": bool(action_plan.get("action_plan_section_present"))
        and not bool(action_plan.get("automatic_blocking", True)),
    }
    consolidated_technical_readiness = all(technical_checks.values()) and not findings
    formal_completion = bool(components) and len(components) == len(EXPECTED_COMPONENTS) and all(
        component.get("control_status") == "implemented" for component in components.values()
    )
    pending_components = sorted(
        name
        for name, component in components.items()
        if component.get("control_status") != "implemented"
    )
    automatic_blocking = bool(findings or not consolidated_technical_readiness)

    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-08",
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "advisory",
        "matrix_path": str(matrix_path),
        "matrix_sha256": hashlib.sha256(matrix_path.read_bytes()).hexdigest(),
        "components": components,
        "technical_checks": technical_checks,
        "consolidated_technical_readiness": consolidated_technical_readiness,
        "formal_completion": formal_completion,
        "pending_components": pending_components,
        "findings": sorted(set(findings)),
        "control_status": "implemented" if formal_completion else "partial",
        "automatic_blocking": automatic_blocking,
        "human_action_required": not formal_completion,
        "production_touched": False,
        "next_stage": "complete_formal_designation_report_narratives_action_plan_and_signoff",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Consolida evidências de prontidão BACEN-08")
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--executive", type=Path, required=True)
    parser.add_argument("--narrative", type=Path, required=True)
    parser.add_argument("--incident-linkage", type=Path, required=True)
    parser.add_argument("--action-plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    evidence = build_consolidated(
        args.matrix,
        args.executive,
        args.narrative,
        args.incident_linkage,
        args.action_plan,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "technical_readiness": evidence["consolidated_technical_readiness"],
                "control_status": evidence["control_status"],
                "pending_components": evidence["pending_components"],
            },
            ensure_ascii=False,
        )
    )
    return 1 if evidence["automatic_blocking"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
