#!/usr/bin/env python3
"""Evaluate release validation evidence as promotion precondition."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

PROMOTION_THRESHOLDS: dict[str, dict[str, Any]] = {
    "homolog": {
        "min_score": 70.0,
        "allowed_readiness": {"ready", "ready_with_observation", "needs_review"},
        "block_operational_states": {"red"},
    },
    "prod": {
        "min_score": 85.0,
        "allowed_readiness": {"ready", "ready_with_observation"},
        "block_operational_states": {"red", "yellow"},
    },
}


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def evaluate(
    release_validation: dict[str, Any] | None,
    target_environment: str,
    *,
    dry_run: bool = True,
    artifact_available: bool = False,
) -> dict[str, Any]:
    policy = PROMOTION_THRESHOLDS.get(target_environment)
    if not policy:
        return {
            "approved": False,
            "blocked_reason": f"ambiente alvo sem politica de release: {target_environment}",
            "release_readiness_score": None,
            "readiness": None,
            "risk": None,
            "operational_state": None,
            "blockers": ["unsupported_target_environment"],
            "warnings": [],
            "artifact_available": artifact_available,
            "dry_run": dry_run,
        }

    if not release_validation:
        blocked_reason = "release-validation-layer-evidence ausente"
        if dry_run:
            return {
                "approved": True,
                "blocked_reason": "",
                "release_readiness_score": None,
                "readiness": None,
                "risk": "unknown",
                "operational_state": None,
                "blockers": [],
                "warnings": [blocked_reason],
                "artifact_available": False,
                "dry_run": dry_run,
                "promotion_would_block": True,
                "promotion_block_reason": blocked_reason,
            }
        return {
            "approved": False,
            "blocked_reason": blocked_reason,
            "release_readiness_score": None,
            "readiness": None,
            "risk": "high",
            "operational_state": None,
            "blockers": ["release_validation_artifact_missing"],
            "warnings": [],
            "artifact_available": False,
            "dry_run": dry_run,
        }

    score = float(release_validation.get("release_readiness_score") or 0)
    readiness = str(release_validation.get("readiness") or "unknown")
    risk = str(release_validation.get("risk") or "unknown")
    operational_state = str(release_validation.get("operational_state") or "unknown")
    blockers = list(release_validation.get("blockers") or [])
    warnings = list(release_validation.get("warnings") or [])

    promotion_blockers: list[str] = []
    if readiness == "blocked":
        promotion_blockers.append("release_readiness_blocked")
    if readiness not in policy["allowed_readiness"]:
        promotion_blockers.append(f"release_readiness_{readiness}")
    if score < float(policy["min_score"]):
        promotion_blockers.append("release_readiness_score_below_threshold")
    if operational_state in policy["block_operational_states"]:
        promotion_blockers.append(f"operational_state_{operational_state}")
    for blocker in blockers:
        if blocker in {"operational_state_red", "pr_evidence_failures", "ci_semantic_validation_failed", "critical_gaps"}:
            promotion_blockers.append(blocker)

    blocked_reason = ""
    if promotion_blockers:
        blocked_reason = (
            f"release validation bloqueia promocao para {target_environment}: "
            f"score={score}, readiness={readiness}, blockers={','.join(sorted(set(promotion_blockers)))}"
        )

    approved = not promotion_blockers
    if dry_run and promotion_blockers:
        return {
            "approved": True,
            "blocked_reason": "",
            "release_readiness_score": score,
            "readiness": readiness,
            "risk": risk,
            "operational_state": operational_state,
            "blockers": promotion_blockers,
            "warnings": warnings,
            "artifact_available": artifact_available,
            "dry_run": dry_run,
            "promotion_would_block": True,
            "promotion_block_reason": blocked_reason,
        }

    return {
        "approved": approved,
        "blocked_reason": blocked_reason,
        "release_readiness_score": score,
        "readiness": readiness,
        "risk": risk,
        "operational_state": operational_state,
        "blockers": promotion_blockers,
        "warnings": warnings,
        "artifact_available": artifact_available,
        "dry_run": dry_run,
        "promotion_would_block": bool(promotion_blockers),
        "promotion_block_reason": blocked_reason,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate promotion release gate.")
    parser.add_argument(
        "--release-validation-json",
        default="audit/release-validation/release-validation-layer.json",
    )
    parser.add_argument("--target-environment", required=True, choices=sorted(PROMOTION_THRESHOLDS))
    parser.add_argument("--dry-run", choices=["true", "false"], default="true")
    parser.add_argument("--output-json", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = Path(args.release_validation_json)
    release_validation = load_json(path)
    result = evaluate(
        release_validation,
        args.target_environment,
        dry_run=args.dry_run == "true",
        artifact_available=release_validation is not None,
    )
    payload = json.dumps(result, indent=2, ensure_ascii=False)
    print(payload)
    if args.output_json:
        Path(args.output_json).write_text(payload + "\n", encoding="utf-8")
    return 0 if result["approved"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
