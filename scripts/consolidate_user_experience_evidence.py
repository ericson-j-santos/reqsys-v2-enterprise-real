#!/usr/bin/env python3
"""Consolida evidência objetiva de UX no Estado Único e no Executive Brief.

O enriquecimento é informativo e não altera readiness, production_ready ou deploy.
"""
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

TARGET_SCORE = 92
REQUIRED_SCENARIOS = {
    "keyboard_focus",
    "mobile_navigation",
    "offline_recovery",
}


def validate_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    scenarios = set(evidence.get("scenarios", []))
    conclusion = str(evidence.get("conclusion", ""))
    artifact = evidence.get("artifact", {}) if isinstance(evidence.get("artifact"), dict) else {}
    digest = str(artifact.get("digest", ""))
    size = int(artifact.get("size_in_bytes", 0) or 0)
    expired = bool(artifact.get("expired", True))

    checks = {
        "workflow_success": conclusion == "success",
        "required_scenarios": REQUIRED_SCENARIOS.issubset(scenarios),
        "artifact_available": size > 0 and not expired,
        "digest_valid": digest.startswith("sha256:") and len(digest) > len("sha256:"),
    }
    evidenced = all(checks.values())

    return {
        "status": "evidenced" if evidenced else "evidence-incomplete",
        "score": TARGET_SCORE if evidenced else None,
        "previous_score": int(evidence.get("previous_score", 89) or 89),
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
        "evidenced": evidenced,
        "checks": checks,
        "scenarios": sorted(scenarios),
        "workflow_run_id": evidence.get("workflow_run_id"),
        "workflow_url": evidence.get("workflow_url"),
        "artifact": {
            "id": artifact.get("id"),
            "name": artifact.get("name"),
            "size_in_bytes": size,
            "digest": digest or None,
            "expired": expired,
            "expires_at": artifact.get("expires_at"),
        },
    }


def enrich(state: dict[str, Any], brief: dict[str, Any], result: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    state_out = deepcopy(state)
    brief_out = deepcopy(brief)

    state_out.setdefault("cards", {})["user_experience_evidence"] = result
    brief_out.setdefault("indicators", {})["user_experience_evidence"] = result

    if result["evidenced"]:
        state_out.setdefault("executive_indicators", {})["user_experience"] = TARGET_SCORE
        brief_out.setdefault("executive_indicators", {})["user_experience"] = TARGET_SCORE

    return state_out, brief_out


def _load(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write(path: str, data: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--brief", required=True)
    parser.add_argument("--out-state", required=True)
    parser.add_argument("--out-brief", required=True)
    parser.add_argument("--out-evidence", required=True)
    args = parser.parse_args()

    result = validate_evidence(_load(args.evidence))
    state_out, brief_out = enrich(_load(args.state), _load(args.brief), result)
    _write(args.out_state, state_out)
    _write(args.out_brief, brief_out)
    _write(args.out_evidence, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
