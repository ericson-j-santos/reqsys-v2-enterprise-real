#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ALLOWED = {
    "open": {"in_progress"},
    "in_progress": {"resolved", "open"},
    "resolved": {"in_progress"},
}


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_evidence(evidence: dict[str, Any], secret: str) -> str:
    if not secret:
        raise ValueError("secret de assinatura obrigatório")
    return hmac.new(secret.encode("utf-8"), _canonical(evidence), hashlib.sha256).hexdigest()


def apply_transition(
    history: list[dict[str, Any]], request: dict[str, Any], *, secret: str, qualified_evidence: dict[str, Any] | None = None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    remediation_id = str(request.get("remediation_id", ""))
    target = str(request.get("target_state", ""))
    actor = str(request.get("actor", ""))
    if not remediation_id or not actor:
        raise ValueError("remediation_id e actor são obrigatórios")
    item = next((entry for entry in history if str(entry.get("id")) == remediation_id), None)
    if item is None:
        raise ValueError("remediação não encontrada")
    current = str(item.get("state", "open"))
    if target not in ALLOWED.get(current, set()):
        raise ValueError(f"transição inválida: {current}->{target}")

    resolution = request.get("resolution_evidence")
    if target == "resolved":
        if not isinstance(resolution, dict):
            raise ValueError("resolution_evidence obrigatória para resolved")
        qualified = qualified_evidence or {}
        if qualified.get("ux_100_ready") is not True:
            raise ValueError("fechamento exige nova evidência UX qualificada")
        if str(qualified.get("source_run_id", "")) == str(item.get("source_run_id", "")):
            raise ValueError("evidência qualificada deve vir de execução posterior")
        expected = sign_evidence(resolution, secret)
        if not hmac.compare_digest(str(request.get("signature", "")), expected):
            raise ValueError("assinatura de evidência inválida")

    now = datetime.now(timezone.utc).isoformat()
    updated = dict(item)
    updated["state"] = target
    updated["updated_at"] = now
    updated["updated_by"] = actor
    if target == "resolved":
        updated["resolution_evidence"] = resolution
        updated["resolution_signature"] = request["signature"]
        updated["qualified_resolution_run_id"] = qualified_evidence.get("source_run_id")
        updated["resolved_at"] = now
    elif current == "resolved":
        updated["resolved_at"] = None

    result = [updated if str(entry.get("id")) == remediation_id else entry for entry in history]
    audit = {
        "remediation_id": remediation_id,
        "from_state": current,
        "to_state": target,
        "actor": actor,
        "at": now,
        "signed_resolution": target == "resolved",
        "qualified_resolution_run_id": updated.get("qualified_resolution_run_id"),
    }
    return result, audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", required=True, type=Path)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--qualified-evidence", type=Path)
    parser.add_argument("--secret", required=True)
    parser.add_argument("--history-output", required=True, type=Path)
    parser.add_argument("--audit-output", required=True, type=Path)
    args = parser.parse_args()
    history = json.loads(args.history.read_text(encoding="utf-8"))
    request = json.loads(args.request.read_text(encoding="utf-8"))
    qualified = json.loads(args.qualified_evidence.read_text(encoding="utf-8")) if args.qualified_evidence else None
    updated, audit = apply_transition(history, request, secret=args.secret, qualified_evidence=qualified)
    args.history_output.parent.mkdir(parents=True, exist_ok=True)
    args.history_output.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.audit_output.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
