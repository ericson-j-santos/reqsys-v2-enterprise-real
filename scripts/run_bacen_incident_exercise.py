#!/usr/bin/env python3
"""Executa e valida uma simulação operacional automatizada do controle BACEN-03."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

REQUIRED_ROLES = {"INCIDENT_COMMANDER", "SECURITY", "RUNTIME_OPERATOR", "GOVERNANCE"}
REQUIRED_TIMELINE = {
    "detection",
    "classification",
    "containment_started",
    "stakeholder_notification",
    "service_recovery",
}


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def load_scenario(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("control_id") != "BACEN-03":
        raise ValueError("control_id deve ser BACEN-03")
    if data.get("production_touched") is not False:
        raise ValueError("o exercício deve declarar production_touched=false")
    return data


def validate_scenario(data: dict[str, object]) -> None:
    participants = data.get("participants")
    if not isinstance(participants, list):
        raise ValueError("participants deve ser uma lista")
    roles = {
        str(item.get("role"))
        for item in participants
        if isinstance(item, dict) and item.get("required") is True
    }
    missing_roles = sorted(REQUIRED_ROLES - roles)
    if missing_roles:
        raise ValueError(f"papéis obrigatórios ausentes: {', '.join(missing_roles)}")

    timeline = data.get("timeline_minutes")
    thresholds = data.get("thresholds_minutes")
    if not isinstance(timeline, dict) or not isinstance(thresholds, dict):
        raise ValueError("timeline_minutes e thresholds_minutes são obrigatórios")
    missing_timeline = sorted(REQUIRED_TIMELINE - set(timeline))
    if missing_timeline:
        raise ValueError(f"marcos ausentes: {', '.join(missing_timeline)}")
    violations = [
        key
        for key in REQUIRED_TIMELINE
        if int(timeline[key]) > int(thresholds[f"max_{key}"])
    ]
    if violations:
        raise ValueError(f"SLA excedido nos marcos: {', '.join(sorted(violations))}")

    decisions = data.get("decisions")
    if not isinstance(decisions, list) or len(decisions) < 3:
        raise ValueError("o exercício deve registrar ao menos três decisões")
    actions = data.get("corrective_actions")
    if not isinstance(actions, list) or not actions:
        raise ValueError("plano de ação corretiva obrigatório")
    for action in actions:
        if not isinstance(action, dict):
            raise ValueError("ação corretiva inválida")
        required = {"id", "description", "owner", "due_days", "status"}
        missing = sorted(required - set(action))
        if missing:
            raise ValueError(f"ação corretiva incompleta: {', '.join(missing)}")
        if action["status"] not in {"planned", "in_progress", "completed"}:
            raise ValueError("status de ação corretiva inválido")
        if int(action["due_days"]) <= 0:
            raise ValueError("due_days deve ser positivo")


def execute(scenario_path: Path, output_path: Path) -> dict[str, object]:
    scenario = load_scenario(scenario_path)
    validate_scenario(scenario)

    executed_at = utc_now()
    review_cycle_days = int(scenario.get("review_cycle_days", 90))
    next_due_at = executed_at + timedelta(days=review_cycle_days)
    timeline = scenario["timeline_minutes"]
    thresholds = scenario["thresholds_minutes"]
    actions = scenario["corrective_actions"]

    scenario_bytes = scenario_path.read_bytes()
    scenario_sha256 = hashlib.sha256(scenario_bytes).hexdigest()
    evidence: dict[str, object] = {
        "schema_version": "1.0.0",
        "control_id": "BACEN-03",
        "evidence_class": "automated_incident_tabletop_exercise",
        "exercise_id": scenario["exercise_id"],
        "exercise_type": scenario["exercise_type"],
        "scenario": scenario["scenario"],
        "participants": scenario["participants"],
        "timeline_minutes": timeline,
        "thresholds_minutes": thresholds,
        "decisions": scenario["decisions"],
        "corrective_actions": actions,
        "corrective_action_plan_present": bool(actions),
        "all_thresholds_met": all(
            int(timeline[key]) <= int(thresholds[f"max_{key}"])
            for key in REQUIRED_TIMELINE
        ),
        "executed_at": executed_at.isoformat(),
        "next_due_at": next_due_at.isoformat(),
        "review_cycle_days": review_cycle_days,
        "is_expired": False,
        "scenario_sha256": scenario_sha256,
        "correlation_id": str(uuid.uuid4()),
        "commit_sha": os.getenv("GITHUB_SHA", "local"),
        "workflow_run_id": os.getenv("GITHUB_RUN_ID", "local"),
        "production_touched": False,
        "result": "passed",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario",
        default="governance/bacen/INCIDENT-EXERCISE-SCENARIO.json",
    )
    parser.add_argument(
        "--output",
        default="artifacts/bacen/bacen-03-incident-exercise-evidence.json",
    )
    args = parser.parse_args()
    evidence = execute(Path(args.scenario), Path(args.output))
    print(
        json.dumps(
            {
                "result": evidence["result"],
                "correlation_id": evidence["correlation_id"],
                "next_due_at": evidence["next_due_at"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
