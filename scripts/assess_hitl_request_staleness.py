#!/usr/bin/env python3
"""Assess open HITL request staleness without inventing institutional deadlines."""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CONTROL_RE = re.compile(r"\[HITL\]\[([^\]]+)\]")


def parse_timestamp(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def label_names(issue: dict[str, Any]) -> set[str]:
    labels = issue.get("labels") or []
    names: set[str] = set()
    for label in labels:
        if isinstance(label, dict):
            value = str(label.get("name") or "").strip()
        else:
            value = str(label or "").strip()
        if value:
            names.add(value)
    return names


def control_id(title: str) -> str:
    match = CONTROL_RE.search(title)
    return match.group(1).strip() if match else "UNKNOWN"


def assess_requests(
    issues: list[dict[str, Any]],
    *,
    now: datetime,
    reminder_after_hours: int,
    escalation_after_hours: int,
) -> dict[str, Any]:
    if reminder_after_hours <= 0:
        raise ValueError("reminder_after_hours must be positive")
    if escalation_after_hours <= reminder_after_hours:
        raise ValueError("escalation_after_hours must exceed reminder_after_hours")

    items: list[dict[str, Any]] = []
    for issue in issues:
        if "hitl-approval-request" not in label_names(issue):
            continue
        number = int(issue.get("number") or 0)
        title = str(issue.get("title") or "").strip()
        url = str(issue.get("url") or "").strip()
        updated_at = parse_timestamp(str(issue.get("updatedAt") or issue.get("updated_at") or ""))
        age_hours = max(0.0, (now.astimezone(UTC) - updated_at).total_seconds() / 3600)
        if age_hours >= escalation_after_hours:
            state = "escalation_due"
        elif age_hours >= reminder_after_hours:
            state = "reminder_due"
        else:
            state = "fresh"
        items.append(
            {
                "issue_number": number,
                "control_id": control_id(title),
                "title": title,
                "url": url,
                "updated_at": updated_at.isoformat(),
                "age_hours": round(age_hours, 2),
                "state": state,
            }
        )

    items.sort(key=lambda item: (-float(item["age_hours"]), int(item["issue_number"])))
    summary = {
        "open_requests": len(items),
        "fresh": sum(item["state"] == "fresh" for item in items),
        "reminder_due": sum(item["state"] == "reminder_due" for item in items),
        "escalation_due": sum(item["state"] == "escalation_due" for item in items),
    }
    decision = (
        "escalation_required"
        if summary["escalation_due"]
        else "reminder_required"
        if summary["reminder_due"]
        else "no_action_required"
    )
    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-hitl-request-staleness-readiness",
        "generated_at": now.astimezone(UTC).isoformat(),
        "policy": {
            "reminder_after_hours": reminder_after_hours,
            "escalation_after_hours": escalation_after_hours,
            "institutional_deadline_created": False,
        },
        "summary": summary,
        "decision": decision,
        "items": items,
        "automatic_approval_allowed": False,
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issues", type=Path, required=True)
    parser.add_argument("--reminder-after-hours", type=int, default=24)
    parser.add_argument("--escalation-after-hours", type=int, default=72)
    parser.add_argument("--now")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    issues = json.loads(args.issues.read_text(encoding="utf-8"))
    if not isinstance(issues, list):
        raise ValueError("issues must be a list")
    now = parse_timestamp(args.now) if args.now else datetime.now(UTC)
    report = assess_requests(
        issues,
        now=now,
        reminder_after_hours=args.reminder_after_hours,
        escalation_after_hours=args.escalation_after_hours,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
