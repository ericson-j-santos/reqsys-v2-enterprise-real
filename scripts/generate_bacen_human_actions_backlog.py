#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

TARGET_STATUSES = {"partial", "gap"}
INSTITUTIONAL_STAGES = {"PRODUCTION", "INSTITUTIONAL"}
DEFERRED_STATUSES = {"deferred_until_institutionalization"}
PRIORITY_BY_CRITICALITY = {
    "critical": "P0",
    "high": "P1",
    "medium": "P2",
    "low": "P3",
}


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"YAML inválido: {path}")
    return payload


def _normalized(value: Any) -> str:
    return str(value or "").strip()


def _deferred_by_lifecycle(control: dict[str, Any]) -> bool:
    lifecycle_stage = _normalized(control.get("lifecycle_stage")).upper()
    if lifecycle_stage in INSTITUTIONAL_STAGES:
        return False

    deferred_statuses = {
        _normalized(control.get("approval_status")),
        _normalized(control.get("institutional_governance_status")),
    }
    return bool(deferred_statuses & DEFERRED_STATUSES)


def _base_item(control: dict[str, Any]) -> dict[str, Any]:
    control_id = _normalized(control.get("id"))
    criticality = _normalized(control.get("criticality")).lower()
    owner_role = _normalized(control.get("owner"))
    next_stage = _normalized(control.get("next_stage"))
    evidence = _normalized(control.get("evidence"))
    lifecycle_stage = _normalized(control.get("lifecycle_stage")).upper() or None
    gate_stage = (
        _normalized(control.get("institutional_approval_gate_stage"))
        or _normalized(control.get("institutional_governance_gate_stage"))
        or None
    )

    return {
        "control_id": control_id,
        "title": control.get("title"),
        "domain": control.get("domain"),
        "status": _normalized(control.get("status")).lower(),
        "criticality": criticality or None,
        "priority": PRIORITY_BY_CRITICALITY.get(criticality, "P3"),
        "responsible_role": owner_role or None,
        "required_action": next_stage or None,
        "evidence_reference": evidence or None,
        "lifecycle_stage": lifecycle_stage,
        "institutional_gate_stage": gate_stage,
        "personal_assignee": None,
        "due_date": None,
        "approval_reference": None,
        "production_touched": bool(control.get("production_touched", False)),
    }


def build_backlog(matrix_path: Path) -> dict[str, Any]:
    matrix = load_yaml(matrix_path)
    controls = matrix.get("controls") or []
    if not isinstance(controls, list):
        raise ValueError("controls deve ser uma lista")

    items: list[dict[str, Any]] = []
    deferred_items: list[dict[str, Any]] = []
    findings: list[str] = []

    for control in controls:
        if not isinstance(control, dict):
            findings.append("invalid_control_entry")
            continue

        status = _normalized(control.get("status")).lower()
        if status not in TARGET_STATUSES:
            continue

        item = _base_item(control)
        control_id = item["control_id"]
        if not control_id:
            findings.append("pending_control_id_missing")
            continue
        if not item["responsible_role"]:
            findings.append(f"owner_role_missing:{control_id}")
        if not item["required_action"]:
            findings.append(f"next_stage_missing:{control_id}")
        if not item["evidence_reference"]:
            findings.append(f"evidence_reference_missing:{control_id}")

        if _deferred_by_lifecycle(control):
            deferred_items.append(
                {
                    **item,
                    "backlog_status": "deferred_until_institutionalization",
                    "human_action_required_now": False,
                }
            )
            continue

        items.append(
            {
                **item,
                "backlog_status": "pending_human_action",
                "human_action_required_now": True,
            }
        )

    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    sort_key = lambda item: (priority_order[item["priority"]], item["control_id"])
    items.sort(key=sort_key)
    deferred_items.sort(key=sort_key)
    automatic_blocking = bool(findings)

    if items:
        next_stage = "assign_real_people_dates_and_approval_references_without_fabrication"
    elif deferred_items:
        next_stage = "continue_technical_evidence_until_institutional_gate"
    else:
        next_stage = "no_pending_human_actions"

    return {
        "schema_version": "1.1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "advisory",
        "matrix_path": str(matrix_path),
        "matrix_sha256": hashlib.sha256(matrix_path.read_bytes()).hexdigest(),
        "summary": {
            "pending_controls": len(items),
            "deferred_controls": len(deferred_items),
            "p0": sum(item["priority"] == "P0" for item in items),
            "p1": sum(item["priority"] == "P1" for item in items),
            "without_personal_assignee": sum(
                item["personal_assignee"] is None for item in items
            ),
            "without_due_date": sum(item["due_date"] is None for item in items),
        },
        "items": items,
        "deferred_items": deferred_items,
        "findings": sorted(set(findings)),
        "automatic_blocking": automatic_blocking,
        "human_action_required": bool(items),
        "production_touched": False,
        "next_stage": next_stage,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera backlog humano dos controles BACEN pendentes")
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    evidence = build_backlog(args.matrix)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evidence["summary"], ensure_ascii=False))
    return 1 if evidence["automatic_blocking"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
