#!/usr/bin/env python3
"""Build a post-merge evidence index summary.

This report-only utility consumes a local JSON payload with recent GitHub Actions
runs and their artifacts, then emits a compact JSON/Markdown index focused on
post-merge evidence for the main branch.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

DEFAULT_INPUT = "artifacts/post-merge-evidence-index-summary/runs.json"
DEFAULT_OUTPUT_DIR = "artifacts/post-merge-evidence-index-summary"
EVIDENCE_KEYWORDS = (
    "evidence",
    "audit",
    "report",
    "summary",
    "post-merge",
    "runtime",
    "validation",
)


def load_json(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        return {"runs": []}
    data = json.loads(file_path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {"runs": data}
    if isinstance(data, dict):
        data.setdefault("runs", [])
        return data
    return {"runs": []}


def is_evidence_artifact(name: str) -> bool:
    lower = name.lower()
    return any(keyword in lower for keyword in EVIDENCE_KEYWORDS)


def normalize_run(run: dict[str, Any]) -> dict[str, Any]:
    artifacts = run.get("artifacts") or []
    evidence_artifacts = [artifact for artifact in artifacts if is_evidence_artifact(str(artifact.get("name") or ""))]
    return {
        "id": run.get("id"),
        "name": run.get("name") or "",
        "event": run.get("event") or "",
        "status": run.get("status") or "unknown",
        "conclusion": run.get("conclusion"),
        "head_branch": run.get("head_branch") or "",
        "head_sha": run.get("head_sha") or "",
        "html_url": run.get("html_url") or "",
        "created_at": run.get("created_at") or "",
        "updated_at": run.get("updated_at") or "",
        "artifact_count": len(artifacts),
        "evidence_artifact_count": len(evidence_artifacts),
        "evidence_artifacts": evidence_artifacts,
    }


def build_index(payload: dict[str, Any], *, repo: str, branch: str, run_id: str | None = None) -> dict[str, Any]:
    runs = [normalize_run(run) for run in payload.get("runs", []) if isinstance(run, dict)]
    main_runs = [run for run in runs if run["head_branch"] in {branch, ""}]
    evidence_runs = [run for run in main_runs if run["evidence_artifact_count"] > 0]
    completed_failures = [run for run in main_runs if run["status"] == "completed" and run.get("conclusion") not in {"success", "skipped", "cancelled", None}]
    active_runs = [run for run in main_runs if run["status"] != "completed"]

    status = "passed" if evidence_runs and not completed_failures else "warning" if evidence_runs else "attention"
    risk = "low" if status == "passed" else "medium"

    return {
        "schema_version": "1.0.0",
        "contract": "post-merge-evidence-index-summary",
        "generated_at_epoch": int(time.time()),
        "repo": repo,
        "branch": branch,
        "github_run_id": run_id,
        "summary": {
            "status": status,
            "risk": risk,
            "total_runs": len(runs),
            "main_runs": len(main_runs),
            "evidence_runs": len(evidence_runs),
            "active_runs": len(active_runs),
            "completed_failures": len(completed_failures),
            "mode": "report_only",
        },
        "runs": main_runs,
        "links": {
            "repository": f"https://github.com/{repo}" if repo else "",
            "actions": f"https://github.com/{repo}/actions" if repo else "",
        },
        "guardrails": [
            "report_only",
            "no_runtime_mutation",
            "reuse_existing_actions_artifacts",
            "main_branch_evidence_index",
        ],
    }


def render_markdown(index: dict[str, Any]) -> str:
    summary = index["summary"]
    lines = [
        "# Post-merge Evidence Index Summary",
        "",
        f"- Repository: `{index['repo']}`",
        f"- Branch: `{index['branch']}`",
        f"- Status: `{summary['status']}`",
        f"- Risk: `{summary['risk']}`",
        f"- Mode: `{summary['mode']}`",
        f"- Total runs inspected: `{summary['total_runs']}`",
        f"- Main runs indexed: `{summary['main_runs']}`",
        f"- Runs with evidence artifacts: `{summary['evidence_runs']}`",
        f"- Active runs: `{summary['active_runs']}`",
        f"- Completed failures: `{summary['completed_failures']}`",
        "",
        "## Evidence runs",
    ]

    evidence_runs = [run for run in index["runs"] if run["evidence_artifact_count"] > 0]
    if not evidence_runs:
        lines.append("- No evidence artifacts found in the inspected runs.")
    else:
        for run in evidence_runs[:20]:
            url = run.get("html_url") or ""
            title = f"{run['name']} #{run['id']}"
            if url:
                title = f"[{title}]({url})"
            lines.append(f"- {title} — `{run['status']}`/`{run.get('conclusion')}` — artifacts: `{run['evidence_artifact_count']}`")
            for artifact in run["evidence_artifacts"][:10]:
                lines.append(f"  - `{artifact.get('name')}` size=`{artifact.get('size_in_bytes', 0)}` expired=`{artifact.get('expired', False)}`")

    return "\n".join(lines) + "\n"


def write_outputs(index: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "post-merge-evidence-index-summary.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "summary.md").write_text(render_markdown(index), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build post-merge evidence index summary")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--repo", default="")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--github-run-id", default="")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    index = build_index(
        load_json(args.input),
        repo=args.repo,
        branch=args.branch,
        run_id=args.github_run_id or None,
    )
    write_outputs(index, Path(args.output_dir))
    print(json.dumps(index["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
