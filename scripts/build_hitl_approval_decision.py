#!/usr/bin/env python3
"""Build an auditable Human-in-the-Loop approval decision record."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

COMMAND_RE = re.compile(r"^\s*/(approve|reject|adjust)\b(?:\s+(.*))?$", re.IGNORECASE | re.DOTALL)
ALLOWED_PERMISSIONS = {"admin", "maintain", "write"}
DECISION_STATUS = {
    "approve": "approved",
    "reject": "rejected",
    "adjust": "adjustment_requested",
}


def _sha256_json(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def parse_command(comment_body: str) -> tuple[str, str]:
    """Parse /approve, /reject or /adjust and require a meaningful rationale."""
    match = COMMAND_RE.match(comment_body or "")
    if not match:
        raise ValueError("comentario deve iniciar com /approve, /reject ou /adjust")
    decision = match.group(1).lower()
    rationale = (match.group(2) or "").strip()
    if len(rationale) < 10:
        raise ValueError("justificativa deve possuir ao menos 10 caracteres")
    return decision, rationale


def build_decision(
    *,
    issue_number: int,
    issue_url: str,
    issue_title: str,
    issue_body: str,
    comment_id: int,
    comment_url: str,
    comment_body: str,
    actor: str,
    permission: str,
    source_sha: str,
    decided_at: str | None = None,
) -> dict[str, Any]:
    actor_normalized = actor.strip()
    permission_normalized = permission.strip().lower()
    if not actor_normalized or actor_normalized.endswith("[bot]"):
        raise ValueError("decisao exige ator humano autenticado")
    if permission_normalized not in ALLOWED_PERMISSIONS:
        raise ValueError(
            f"permissao insuficiente: {permission_normalized or 'ausente'}; "
            f"permitidas={sorted(ALLOWED_PERMISSIONS)}"
        )
    if issue_number <= 0 or comment_id <= 0:
        raise ValueError("issue_number e comment_id devem ser positivos")
    if not issue_url.startswith("https://github.com/") or not comment_url.startswith("https://github.com/"):
        raise ValueError("issue_url e comment_url devem apontar para o GitHub")
    if not re.fullmatch(r"[0-9a-fA-F]{7,64}", source_sha.strip()):
        raise ValueError("source_sha invalido")

    decision, rationale = parse_command(comment_body)
    timestamp = decided_at or datetime.now(UTC).isoformat()
    request_fingerprint = {
        "issue_number": issue_number,
        "issue_url": issue_url,
        "issue_title": issue_title,
        "issue_body": issue_body,
        "source_sha": source_sha.lower(),
    }
    decision_fingerprint = {
        "decision": decision,
        "rationale": rationale,
        "actor": actor_normalized,
        "permission": permission_normalized,
        "comment_id": comment_id,
        "comment_url": comment_url,
        "decided_at": timestamp,
    }
    request_sha256 = _sha256_json(request_fingerprint)
    decision_sha256 = _sha256_json({"request": request_fingerprint, "decision": decision_fingerprint})
    correlation_id = f"hitl-{issue_number}-{comment_id}-{decision_sha256[:12]}"

    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-hitl-approval-decision",
        "correlation_id": correlation_id,
        "status": DECISION_STATUS[decision],
        "effective_decision": decision,
        "approval": {
            "actor": actor_normalized,
            "permission": permission_normalized,
            "rationale": rationale,
            "decided_at": timestamp,
            "comment_id": comment_id,
            "comment_url": comment_url,
        },
        "request": {
            "issue_number": issue_number,
            "issue_url": issue_url,
            "issue_title": issue_title,
            "source_sha": source_sha.lower(),
            "request_sha256": request_sha256,
        },
        "evidence": {
            "decision_sha256": decision_sha256,
            "immutable_reference": comment_url,
        },
        "next_action": {
            "approve": "rerun_safe_delivery_gates_and_prepare_followup_pr",
            "reject": "keep_delivery_blocked_and_close_request",
            "adjust": "keep_request_open_and_apply_requested_adjustments",
        }[decision],
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an auditable ReqSys HITL decision record")
    parser.add_argument("--issue-number", type=int, required=True)
    parser.add_argument("--issue-url", required=True)
    parser.add_argument("--issue-title", required=True)
    parser.add_argument("--issue-body-file", type=Path, required=True)
    parser.add_argument("--comment-id", type=int, required=True)
    parser.add_argument("--comment-url", required=True)
    parser.add_argument("--comment-body-file", type=Path, required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--permission", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--decided-at")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = build_decision(
        issue_number=args.issue_number,
        issue_url=args.issue_url,
        issue_title=args.issue_title,
        issue_body=args.issue_body_file.read_text(encoding="utf-8"),
        comment_id=args.comment_id,
        comment_url=args.comment_url,
        comment_body=args.comment_body_file.read_text(encoding="utf-8"),
        actor=args.actor,
        permission=args.permission,
        source_sha=args.source_sha,
        decided_at=args.decided_at,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
