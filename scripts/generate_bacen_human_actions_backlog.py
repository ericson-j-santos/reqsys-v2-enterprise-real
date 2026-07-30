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


def build_backlog(matrix_path: Path) -> dict[str, Any]:
    matrix = load_yaml(matrix_path)
    controls = matrix.get("controls") or []
    if not isinstance(controls, list):
        raise ValueError("controls deve ser uma lista")

    items: list[dict[str, Any]] = []
    findings: list[str] = []

    for control in controls:
        if not isinstance(control, dict):
            findings.append("invalid_control_entry")
            continue

        control_id = str(control.get("id") or "").strip()
        status = str(control.get("status") or "").strip().lower()
        if status not in TARGET_STATUSES:
            continue

        criticality = str(control.get("criticality") or "").strip().lower()
        owner_role = str(control.get("owner") or "").strip()
        next_stage = str(control.get("next_stage") or "").strip()
        evidence = str(control.get("evidence") or "").strip()

        if not control_id:
            findings.append("pending_control_id_missing")
            continue
        if not owner_role:
            findings.append(f"owner_role_missing:{control_id}")
        if not next_stage:
            findings.append(f"next_stage_missing:{control_id}")
        if not evidence:
            findings.append(f"evidence_reference_missing:{control_id}")

        items.append(
            {
                "control_id": control_id,
                "title": control.get("title"),
                "domain": control.get("domain"),
                "status": status,
                "criticality": criticality or None,
                "priority": PRIORITY_BY_CRITICALITY.get(criticality, "P3"),
                "responsible_role": owner_role or None,
                "required_action": next_stage or None,
                "evidence_reference": evidence or None,
                "personal_assignee": None,
                "due_date": None,
                "approval_reference": None,
                "backlog_status": "pending_human_action",
                "production_touched": bool(control.get("production_touched", False)),
            }
        )

    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    items.sort(key=lambda item: (priority_order[item["priority"]], item["control_id"]))
    automatic_blocking = bool(findings)

    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "advisory",
        "matrix_path": str(matrix_path),
        "matrix_sha256": hashlib.sha256(matrix_path.read_bytes()).hexdigest(),
        "summary": {
            "pending_controls": len(items),
            "p0": sum(item["priority"] == "P0" for item in items),
            "p1": sum(item["priority"] == "P1" for item in items),
            "without_personal_assignee": sum(
                item["personal_assignee"] is None for item in items
            ),
            "without_due_date": sum(item["due_date"] is None for item in items),
        },
        "items": items,
        "findings": sorted(set(findings)),
        "automatic_blocking": automatic_blocking,
        "human_action_required": bool(items),
        "production_touched": False,
        "next_stage": "assign_real_people_dates_and_approval_references_without_fabrication",
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
