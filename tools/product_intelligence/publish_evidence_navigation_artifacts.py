#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED_ARTIFACTS = [
    "product-intelligence-evidence-navigation-ui.json",
    "product-intelligence-evidence-navigation-ui.md",
    "product-intelligence-evidence-navigation-ui.html",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(report_dir: Path) -> dict[str, Any]:
    artifacts: list[dict[str, Any]] = []
    missing: list[str] = []
    for name in REQUIRED_ARTIFACTS:
        path = report_dir / name
        available = path.exists() and path.is_file() and path.stat().st_size > 0
        if not available:
            missing.append(name)
        artifacts.append({
            "artifact": name,
            "path": f"reports/product-intelligence/{name}",
            "available": available,
            "size_bytes": path.stat().st_size if available else 0,
            "sha256": sha256_file(path) if available else None,
        })
    coverage = round(((len(REQUIRED_ARTIFACTS) - len(missing)) / len(REQUIRED_ARTIFACTS)) * 100, 2)
    readiness_state = "EVIDENCE_NAVIGATION_ARTIFACTS_PUBLISHABLE" if not missing else "EVIDENCE_NAVIGATION_ARTIFACTS_INCOMPLETE"
    return {
        "schema_version": "1.0.0",
        "name": "product-intelligence-evidence-navigation-artifact-publisher",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "review_only",
        "readiness_state": readiness_state,
        "artifact_coverage_percent": coverage,
        "confidence_percent": 95 if coverage == 100.0 else 70,
        "risk_percent": 4 if coverage == 100.0 else 25,
        "artifact_count": len(REQUIRED_ARTIFACTS) - len(missing),
        "required_artifact_count": len(REQUIRED_ARTIFACTS),
        "missing_artifacts": missing,
        "artifacts": artifacts,
        "human_review_required": True,
        "production_publish_authorized": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    rows = "\n".join(
        f"| `{artifact['artifact']}` | {artifact['available']} | {artifact['size_bytes']} | `{artifact['sha256'] or '-'}` |"
        for artifact in payload["artifacts"]
    )
    return f'''# Product Intelligence Evidence Navigation Artifact Publisher

| Field | Value |
|---|---:|
| Readiness | {payload['readiness_state']} |
| Artifact coverage | {payload['artifact_coverage_percent']}% |
| Confidence | {payload['confidence_percent']}% |
| Risk | {payload['risk_percent']}% |
| Artifacts | {payload['artifact_count']} / {payload['required_artifact_count']} |
| Production publish authorized | {payload['production_publish_authorized']} |

## Artifact manifest

| Artifact | Available | Size bytes | SHA-256 |
|---|---:|---:|---|
{rows}

## Guardrail

Artifacts are packaged for review and traceability only. Production publishing remains blocked until explicit human governance approval.
'''


def main() -> int:
    report_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("reports/product-intelligence")
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = build_manifest(report_dir)
    (report_dir / "product-intelligence-evidence-navigation-artifact-manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (report_dir / "product-intelligence-evidence-navigation-artifact-manifest.md").write_text(render_markdown(payload), encoding="utf-8")
    print(f"Evidence navigation artifact publisher: {payload['readiness_state']} coverage={payload['artifact_coverage_percent']}% risk={payload['risk_percent']}%")
    return 0 if payload["readiness_state"] == "EVIDENCE_NAVIGATION_ARTIFACTS_PUBLISHABLE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
