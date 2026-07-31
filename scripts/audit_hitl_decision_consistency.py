#!/usr/bin/env python3
"""Audit HITL decisions for contradictory or duplicated terminal commands."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

COMMAND_RE = re.compile(r"^\s*/(approve|reject|adjust)\b", re.IGNORECASE)


def command_from_comment(comment: dict[str, Any]) -> str | None:
    body = str(comment.get("body") or "")
    match = COMMAND_RE.match(body)
    return match.group(1).lower() if match else None


def audit_issue(issue: dict[str, Any]) -> dict[str, Any]:
    comments = issue.get("comments") or []
    if not isinstance(comments, list):
        raise ValueError("comments must be a list")

    decisions: list[dict[str, Any]] = []
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        command = command_from_comment(comment)
        if not command:
            continue
        author = str((comment.get("author") or {}).get("login") or comment.get("author_login") or "")
        if author.endswith("[bot]"):
            continue
        decisions.append(
            {
                "command": command,
                "url": str(comment.get("url") or "").strip(),
                "created_at": str(comment.get("createdAt") or comment.get("created_at") or "").strip(),
            }
        )

    terminal = [item for item in decisions if item["command"] in {"approve", "reject"}]
    terminal_commands = {item["command"] for item in terminal}
    if len(terminal_commands) > 1:
        state = "contradictory_terminal_decisions"
    elif len(terminal) > 1:
        state = "duplicate_terminal_decision"
    elif terminal:
        state = "terminal_decision_recorded"
    elif decisions:
        state = "adjustment_only"
    else:
        state = "no_decision"

    return {
        "issue_number": int(issue.get("number") or 0),
        "title": str(issue.get("title") or "").strip(),
        "url": str(issue.get("url") or "").strip(),
        "state": state,
        "decision_count": len(decisions),
        "terminal_decision_count": len(terminal),
        "decision_references": [item["url"] for item in decisions if item["url"]],
    }


def audit_issues(issues: list[dict[str, Any]]) -> dict[str, Any]:
    items = [audit_issue(issue) for issue in issues]
    conflicts = [
        item
        for item in items
        if item["state"] in {"contradictory_terminal_decisions", "duplicate_terminal_decision"}
    ]
    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-hitl-decision-consistency-audit",
        "summary": {
            "issues_checked": len(items),
            "conflicts": len(conflicts),
            "terminal_decisions": sum(
                item["state"] == "terminal_decision_recorded" for item in items
            ),
            "pending_without_decision": sum(item["state"] == "no_decision" for item in items),
        },
        "decision": "review_required" if conflicts else "consistent",
        "items": items,
        "automatic_decision_override_allowed": False,
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issues", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    issues = json.loads(args.issues.read_text(encoding="utf-8"))
    if not isinstance(issues, list):
        raise ValueError("issues must be a list")
    report = audit_issues(issues)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    if args.strict and report["summary"]["conflicts"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
