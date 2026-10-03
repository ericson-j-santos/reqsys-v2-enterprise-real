#!/usr/bin/env python3
"""Build a deep diagnostic dossier from GitHub Actions run/job metadata.

This script is designed to run inside GitHub Actions with `gh` available.
It captures run/job data, job logs and classifies logs through Failure Pattern Engine.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def run_command(command: list[str], *, allow_failure: bool = False) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode != 0 and not allow_failure:
        raise RuntimeError(
            f"Command failed: {' '.join(command)}\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )
    return completed


def gh_json(args: list[str]) -> Any:
    completed = run_command(["gh", *args])
    return json.loads(completed.stdout or "{}")


def fetch_job_logs(repo: str, job_id: str, out_file: Path) -> None:
    completed = run_command(
        ["gh", "api", f"/repos/{repo}/actions/jobs/{job_id}/logs"],
        allow_failure=True,
    )
    out_file.write_text(completed.stdout + completed.stderr, encoding="utf-8")


def build_report(repo: str, run_id: str | None, job_ids: list[str], out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = out_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    run_data: dict[str, Any] | None = None
    run_jobs: dict[str, Any] | None = None
    artifacts: dict[str, Any] | None = None

    if run_id:
        run_data = gh_json([
            "run",
            "view",
            run_id,
            "--repo",
            repo,
            "--json",
            "databaseId,name,workflowName,status,conclusion,event,headBranch,headSha,url,createdAt,updatedAt",
        ])
        run_jobs = gh_json(["run", "view", run_id, "--repo", repo, "--json", "jobs"])
        artifacts = gh_json(["api", f"/repos/{repo}/actions/runs/{run_id}/artifacts"])

        for job in run_jobs.get("jobs", []) if isinstance(run_jobs, dict) else []:
            job_id = str(job.get("databaseId") or job.get("id") or "")
            if job_id and job_id not in job_ids:
                job_ids.append(job_id)

    job_reports: list[dict[str, Any]] = []
    log_files: list[str] = []

    for job_id in dict.fromkeys(job_ids):
        if not job_id:
            continue
        job_data = gh_json(["api", f"/repos/{repo}/actions/jobs/{job_id}"])
        log_file = logs_dir / f"job-{job_id}.log"
        fetch_job_logs(repo, job_id, log_file)
        log_files.append(str(log_file))
        job_reports.append(
            {
                "job_id": job_id,
                "name": job_data.get("name"),
                "status": job_data.get("status"),
                "conclusion": job_data.get("conclusion"),
                "html_url": job_data.get("html_url"),
                "steps": job_data.get("steps", []),
                "log_file": str(log_file),
            }
        )

    report = {
        "schema_version": "1.0.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository": repo,
        "run_id": run_id,
        "run": run_data,
        "artifacts": artifacts,
        "jobs": job_reports,
        "log_files": log_files,
        "recommended_next_action": "Run Failure Pattern Engine over captured logs and inspect classified root cause before rerun/remediation.",
        "blocked_actions": [
            "merge_without_green_ci",
            "rerun_loop_without_root_cause",
            "ignore_post_merge_failure",
        ],
    }

    (out_dir / "deep-diagnostic.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "deep-diagnostic.md").write_text(render_markdown(report), encoding="utf-8")
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# GitHub Actions Deep Diagnostic",
        "",
        f"Atualizado em UTC: `{report['generated_at_utc']}`",
        f"Repositório: `{report['repository']}`",
        f"Run ID: `{report.get('run_id') or 'não informado'}`",
        "",
        "## Jobs capturados",
        "",
        "| Job ID | Nome | Status | Conclusão |",
        "|---|---|---|---|",
    ]
    for job in report.get("jobs", []):
        lines.append(f"| {job['job_id']} | {job.get('name')} | {job.get('status')} | {job.get('conclusion')} |")

    lines.extend([
        "",
        "## Arquivos de log",
        "",
    ])
    for log_file in report.get("log_files", []):
        lines.append(f"- `{log_file}`")

    lines.extend([
        "",
        "## Próxima ação recomendada",
        "",
        f"- {report['recommended_next_action']}",
        "",
        "## Bloqueios operacionais",
        "",
    ])
    for action in report.get("blocked_actions", []):
        lines.append(f"- `{action}`")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture GitHub Actions deep diagnostic evidence.")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--job-id", action="append", default=[])
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/deep-diagnostic"))
    args = parser.parse_args()

    build_report(args.repo, args.run_id, args.job_id, args.out_dir)
    print((args.out_dir / "deep-diagnostic.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
