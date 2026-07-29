#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"Documento JSON inválido: {path}")
    return document


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def consolidate(access_path: Path, mfa_path: Path) -> dict[str, Any]:
    access = load_json(access_path)
    mfa = load_json(mfa_path)

    findings: list[str] = []
    if access.get("control_id") != "BACEN-02":
        findings.append("invalid_access_control_id")
    if mfa.get("control_id") != "BACEN-02":
        findings.append("invalid_mfa_control_id")
    if access.get("structural_checks_passed") is not True:
        findings.append("access_review_structure_invalid")
    if mfa.get("structural_checks_passed") is not True:
        findings.append("mfa_evidence_structure_invalid")
    if access.get("production_touched") is not False:
        findings.append("access_review_production_touched")
    if mfa.get("production_touched") is not False:
        findings.append("mfa_evidence_production_touched")

    formal_review_completed = access.get("formal_review_completed") is True
    mfa_evidenced = mfa.get("mfa_evidenced") is True
    structural_checks_passed = not findings
    implemented = structural_checks_passed and formal_review_completed and mfa_evidenced

    pending_actions: list[str] = []
    if not formal_review_completed:
        pending_actions.append("complete_formal_quarterly_access_review")
    if not mfa_evidenced:
        pending_actions.append("provide_validated_identity_provider_mfa_evidence")

    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-02",
        "generated_at": datetime.now(UTC).isoformat(),
        "sources": {
            "access_review": {
                "path": str(access_path),
                "sha256": sha256(access_path),
            },
            "mfa_evidence": {
                "path": str(mfa_path),
                "sha256": sha256(mfa_path),
            },
        },
        "formal_review_completed": formal_review_completed,
        "mfa_evidenced": mfa_evidenced,
        "structural_checks_passed": structural_checks_passed,
        "control_status": "implemented" if implemented else "partial",
        "findings": findings,
        "pending_actions": pending_actions,
        "automatic_blocking": bool(findings),
        "human_action_required": not formal_review_completed,
        "external_evidence_required": not mfa_evidenced,
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Consolida prontidão de revisão de acessos e evidência MFA do BACEN-02"
    )
    parser.add_argument("--access-review", type=Path, required=True)
    parser.add_argument("--mfa-evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = consolidate(args.access_review, args.mfa_evidence)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("BACEN-02 consolidated readiness generated")
    return 0 if result["structural_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
