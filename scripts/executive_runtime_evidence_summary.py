#!/usr/bin/env python3
"""Executive runtime evidence summary.

Consolidates the governed runtime smoke and post-merge sentinel evidence into a
small executive JSON/Markdown artifact. The script is offline and read-only: it
only consumes local artifact files and writes local summary files.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

DEFAULT_SMOKE_PATH = "artifacts/runtime-production-smoke-governed.json"
DEFAULT_SENTINEL_PATH = "artifacts/post-merge-runtime-smoke-sentinel/post-merge-runtime-smoke-sentinel.json"
DEFAULT_OUTPUT_DIR = "artifacts/executive-runtime-evidence-summary"


def load_json(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    return json.loads(file_path.read_text(encoding="utf-8"))


def normalize(value: Any, default: str = "unknown") -> str:
    text = str(value or default).strip().lower()
    return text or default


def risk_from_status(status: Any) -> str:
    status_text = normalize(status)
    if status_text in {"healthy", "ready", "success", "passed", "ok", "low"}:
        return "low"
    if status_text in {"blocked", "degraded", "failure", "failed", "critical", "high"}:
        return "high"
    return "medium"


def worst_risk(*risks: Any) -> str:
    normalized = [normalize(risk, "medium") for risk in risks if risk is not None]
    if any(risk == "high" for risk in normalized):
        return "high"
    if any(risk == "medium" for risk in normalized):
        return "medium"
    return "low" if normalized else "medium"


def summarize_smoke(smoke: dict[str, Any]) -> dict[str, Any]:
    if not smoke:
        return {
            "available": False,
            "status": "missing",
            "risk": "medium",
            "base_url": "",
            "required": "0/0",
            "required_success_percentual": 0,
            "total_success_percentual": 0,
            "average_latency_ms": None,
            "github_run_id": None,
            "blocking_issues": ["runtime_smoke_artifact_missing"],
        }
    status = normalize(smoke.get("status"))
    checks = smoke.get("checks") or []
    failed_required = [item.get("path") for item in checks if item.get("required") and not item.get("ok")]
    return {
        "available": True,
        "status": status,
        "risk": risk_from_status(status),
        "base_url": smoke.get("base_url") or "",
        "required": f"{smoke.get('required_ok', 0)}/{smoke.get('required_total', 0)}",
        "required_success_percentual": smoke.get("required_success_percentual", 0),
        "total_success_percentual": smoke.get("total_success_percentual", 0),
        "average_latency_ms": smoke.get("average_latency_ms"),
        "github_run_id": smoke.get("github_run_id"),
        "blocking_issues": failed_required,
    }


def summarize_sentinel(sentinel: dict[str, Any]) -> dict[str, Any]:
    if not sentinel:
        return {
            "available": False,
            "status": "missing",
            "risk": "medium",
            "workflow_name": "",
            "run_id": None,
            "run_url": "",
            "expected_artifact": "runtime-production-smoke-governed",
            "artifact_present": False,
            "blocking_issues": ["post_merge_sentinel_artifact_missing"],
        }
    status = normalize(sentinel.get("status"))
    artifacts = sentinel.get("artifacts") or []
    expected_artifact = sentinel.get("expected_artifact") or "runtime-production-smoke-governed"
    blocking = sentinel.get("blocking_issues") or []
    return {
        "available": True,
        "status": status,
        "risk": risk_from_status(status),
        "workflow_name": sentinel.get("workflow_name") or "",
        "run_id": sentinel.get("run_id"),
        "run_url": sentinel.get("run_url") or "",
        "expected_artifact": expected_artifact,
        "artifact_present": expected_artifact in artifacts,
        "blocking_issues": blocking,
    }


def build_summary(smoke: dict[str, Any], sentinel: dict[str, Any], *, repo: str, run_id: str | None = None) -> dict[str, Any]:
    smoke_summary = summarize_smoke(smoke)
    sentinel_summary = summarize_sentinel(sentinel)
    risk = worst_risk(smoke_summary["risk"], sentinel_summary["risk"])
    production_ready = smoke_summary["status"] == "healthy" and sentinel_summary["status"] == "ready"
    status = "passed" if production_ready else "warning" if risk == "medium" else "critical"
    confidence = "high" if smoke_summary["available"] and sentinel_summary["available"] else "medium"
    return {
        "schema_version": "1.0.0",
        "contract": "executive-runtime-evidence-summary",
        "repo": repo,
        "generated_at_epoch": int(time.time()),
        "github_run_id": run_id,
        "summary": {
            "status": status,
            "risk": risk,
            "production_ready": production_ready,
            "confidence": confidence,
            "source": "local_runtime_evidence_artifacts",
        },
        "cards": {
            "runtime_smoke": smoke_summary,
            "post_merge_sentinel": sentinel_summary,
        },
        "links": {
            "repository": f"https://github.com/{repo}" if repo else "",
            "actions": f"https://github.com/{repo}/actions" if repo else "",
            "runtime_public_url": smoke_summary.get("base_url") or "https://reqsys-app.fly.dev",
            "sentinel_run": sentinel_summary.get("run_url") or "",
        },
        "guardrails": [
            "offline_static_generation",
            "no_runtime_mutation",
            "no_duplicate_smoke_execution",
            "artifact_only_consolidation",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    smoke = payload["cards"]["runtime_smoke"]
    sentinel = payload["cards"]["post_merge_sentinel"]
    lines = [
        "# Executive Runtime Evidence Summary",
        "",
        f"- Status: `{summary['status']}`",
        f"- Risk: `{summary['risk']}`",
        f"- Production ready: `{summary['production_ready']}`",
        f"- Confidence: `{summary['confidence']}`",
        "",
        "## Runtime smoke",
        f"- Available: `{smoke['available']}`",
        f"- Status: `{smoke['status']}`",
        f"- Required: `{smoke['required']}`",
        f"- Required success: `{smoke['required_success_percentual']}%`",
        f"- Base URL: `{smoke['base_url']}`",
        "",
        "## Post-merge sentinel",
        f"- Available: `{sentinel['available']}`",
        f"- Status: `{sentinel['status']}`",
        f"- Workflow: `{sentinel['workflow_name']}`",
        f"- Expected artifact: `{sentinel['expected_artifact']}`",
        f"- Artifact present: `{sentinel['artifact_present']}`",
        "",
    ]
    blockers = list(smoke.get("blocking_issues") or []) + list(sentinel.get("blocking_issues") or [])
    if blockers:
        lines.append("## Attention points")
        lines.extend(f"- `{item}`" for item in blockers)
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "executive-runtime-evidence-summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "summary.md").write_text(render_markdown(payload), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build executive runtime evidence summary")
    parser.add_argument("--runtime-smoke", default=DEFAULT_SMOKE_PATH)
    parser.add_argument("--post-merge-sentinel", default=DEFAULT_SENTINEL_PATH)
    parser.add_argument("--repo", default="")
    parser.add_argument("--github-run-id", default="")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    payload = build_summary(
        load_json(args.runtime_smoke),
        load_json(args.post_merge_sentinel),
        repo=args.repo,
        run_id=args.github_run_id or None,
    )
    write_outputs(payload, Path(args.output_dir))
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
