#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED_RETENTION_INDEX = "product-intelligence-evidence-navigation-retention-index.json"
LIFECYCLE_STAGES = [
    "generated",
    "published_for_review",
    "retained_review_only",
    "reviewed_by_human_governance",
    "promoted_or_regenerated",
]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required retention index not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid JSON object: {path}")
    return payload


def build_lifecycle_index(retention_index: dict[str, Any]) -> dict[str, Any]:
    artifacts = retention_index.get("artifacts", [])
    if not isinstance(artifacts, list):
        raise ValueError("retention index field 'artifacts' must be a list")

    lifecycle_map: list[dict[str, Any]] = []
    incomplete: list[str] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        name = str(artifact.get("artifact", "unknown-artifact"))
        has_hash = bool(artifact.get("sha256"))
        has_retention = int(artifact.get("retention_days", 0) or 0) > 0
        stage_state = "LIFECYCLE_REVIEW_ONLY_READY" if has_hash and has_retention else "LIFECYCLE_INCOMPLETE"
        if stage_state != "LIFECYCLE_REVIEW_ONLY_READY":
            incomplete.append(name)
        lifecycle_map.append(
            {
                "artifact": name,
                "path": artifact.get("path"),
                "sha256": artifact.get("sha256"),
                "retention_days": artifact.get("retention_days"),
                "current_stage": "retained_review_only",
                "allowed_stages": LIFECYCLE_STAGES,
                "state": stage_state,
                "requires_human_governance_review": True,
                "production_promotion_authorized": False,
                "next_allowed_action": "human_governance_review_or_regenerate_from_source_workflow",
            }
        )

    lifecycle_complete = (
        retention_index.get("readiness_state") == "EVIDENCE_NAVIGATION_RETENTION_INDEX_COMPLETE"
        and retention_index.get("retention_compliant") is True
        and retention_index.get("production_publish_authorized") is False
        and not incomplete
        and bool(lifecycle_map)
    )

    return {
        "schema_version": "1.0.0",
        "name": "product-intelligence-evidence-navigation-governance-lifecycle-index",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "review_only",
        "source": REQUIRED_RETENTION_INDEX,
        "readiness_state": "EVIDENCE_NAVIGATION_GOVERNANCE_LIFECYCLE_COMPLETE" if lifecycle_complete else "EVIDENCE_NAVIGATION_GOVERNANCE_LIFECYCLE_BLOCKED",
        "lifecycle_complete": lifecycle_complete,
        "artifact_count": len(lifecycle_map),
        "incomplete_artifacts": incomplete,
        "confidence_percent": 97 if lifecycle_complete else 73,
        "risk_percent": 2 if lifecycle_complete else 24,
        "production_promotion_authorized": False,
        "human_governance_review_required": True,
        "lifecycle_stages": LIFECYCLE_STAGES,
        "lifecycle_map": lifecycle_map,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    rows = "\n".join(
        f"| `{item['artifact']}` | {item['current_stage']} | {item['state']} | {item['production_promotion_authorized']} |"
        for item in payload["lifecycle_map"]
    )
    stages = " → ".join(payload["lifecycle_stages"])
    return f'''# Product Intelligence Evidence Navigation Governance Lifecycle Index

| Field | Value |
|---|---:|
| Readiness | {payload['readiness_state']} |
| Lifecycle complete | {payload['lifecycle_complete']} |
| Confidence | {payload['confidence_percent']}% |
| Risk | {payload['risk_percent']}% |
| Production promotion authorized | {payload['production_promotion_authorized']} |
| Human governance review required | {payload['human_governance_review_required']} |

## Lifecycle stages

`{stages}`

## Lifecycle map

| Artifact | Current stage | State | Production promotion authorized |
|---|---|---|---:|
{rows}

## Guardrail

This lifecycle index does not promote evidence to production. It only governs the review-only lifecycle until explicit human governance approval or regeneration from source workflows.
'''


def main() -> int:
    report_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("reports/product-intelligence")
    report_dir.mkdir(parents=True, exist_ok=True)
    retention_index = load_json(report_dir / REQUIRED_RETENTION_INDEX)
    payload = build_lifecycle_index(retention_index)

    (report_dir / "product-intelligence-evidence-navigation-governance-lifecycle-index.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (report_dir / "product-intelligence-evidence-navigation-governance-lifecycle-index.md").write_text(
        render_markdown(payload),
        encoding="utf-8",
    )

    print(
        "Evidence navigation governance lifecycle index: "
        f"{payload['readiness_state']} "
        f"risk={payload['risk_percent']}%"
    )
    return 0 if payload["lifecycle_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
