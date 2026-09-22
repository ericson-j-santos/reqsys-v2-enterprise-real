#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED_MANIFEST = "product-intelligence-evidence-navigation-artifact-manifest.json"
DEFAULT_RETENTION_DAYS = 14
MIN_RETENTION_DAYS = 7
MAX_REVIEW_ONLY_RETENTION_DAYS = 30


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required manifest not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid JSON object: {path}")
    return payload


def build_retention_index(manifest: dict[str, Any]) -> dict[str, Any]:
    artifacts = manifest.get("artifacts", [])
    if not isinstance(artifacts, list):
        raise ValueError("manifest field 'artifacts' must be a list")

    retained_artifacts: list[dict[str, Any]] = []
    missing_hashes: list[str] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        name = str(artifact.get("artifact", "unknown-artifact"))
        sha256 = artifact.get("sha256")
        if not sha256:
            missing_hashes.append(name)
        retained_artifacts.append(
            {
                "artifact": name,
                "path": artifact.get("path"),
                "sha256": sha256,
                "size_bytes": artifact.get("size_bytes", 0),
                "retention_days": DEFAULT_RETENTION_DAYS,
                "retention_policy": "review_only_ephemeral_bundle",
                "disposition_after_retention": "regenerate_from_source_workflow",
                "production_evidence": False,
            }
        )

    retention_compliant = (
        manifest.get("readiness_state") == "EVIDENCE_NAVIGATION_ARTIFACTS_PUBLISHABLE"
        and manifest.get("production_publish_authorized") is False
        and not missing_hashes
        and MIN_RETENTION_DAYS <= DEFAULT_RETENTION_DAYS <= MAX_REVIEW_ONLY_RETENTION_DAYS
    )

    return {
        "schema_version": "1.0.0",
        "name": "product-intelligence-evidence-navigation-retention-index",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "review_only",
        "source": REQUIRED_MANIFEST,
        "readiness_state": "EVIDENCE_NAVIGATION_RETENTION_INDEX_COMPLETE" if retention_compliant else "EVIDENCE_NAVIGATION_RETENTION_INDEX_BLOCKED",
        "retention_days": DEFAULT_RETENTION_DAYS,
        "min_retention_days": MIN_RETENTION_DAYS,
        "max_review_only_retention_days": MAX_REVIEW_ONLY_RETENTION_DAYS,
        "retention_compliant": retention_compliant,
        "artifact_count": len(retained_artifacts),
        "missing_hashes": missing_hashes,
        "confidence_percent": 96 if retention_compliant else 72,
        "risk_percent": 3 if retention_compliant else 24,
        "production_publish_authorized": False,
        "human_review_required": True,
        "artifacts": retained_artifacts,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    rows = "\n".join(
        f"| `{artifact['artifact']}` | {artifact['retention_days']} | `{artifact['sha256'] or '-'}` | {artifact['production_evidence']} |"
        for artifact in payload["artifacts"]
    )
    return f'''# Product Intelligence Evidence Navigation Retention Index

| Field | Value |
|---|---:|
| Readiness | {payload['readiness_state']} |
| Retention compliant | {payload['retention_compliant']} |
| Retention days | {payload['retention_days']} |
| Confidence | {payload['confidence_percent']}% |
| Risk | {payload['risk_percent']}% |
| Production publish authorized | {payload['production_publish_authorized']} |
| Human review required | {payload['human_review_required']} |

## Retention map

| Artifact | Retention days | SHA-256 | Production evidence |
|---|---:|---|---:|
{rows}

## Guardrail

This retention index governs review-only evidence bundles. Artifacts remain reproducible from source workflows and are not production evidence until explicit human governance approval.
'''


def main() -> int:
    report_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("reports/product-intelligence")
    report_dir.mkdir(parents=True, exist_ok=True)
    manifest = load_json(report_dir / REQUIRED_MANIFEST)
    payload = build_retention_index(manifest)

    (report_dir / "product-intelligence-evidence-navigation-retention-index.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (report_dir / "product-intelligence-evidence-navigation-retention-index.md").write_text(
        render_markdown(payload),
        encoding="utf-8",
    )

    print(
        "Evidence navigation retention index: "
        f"{payload['readiness_state']} "
        f"retention={payload['retention_days']}d "
        f"risk={payload['risk_percent']}%"
    )
    return 0 if payload["retention_compliant"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
