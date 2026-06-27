#!/usr/bin/env python3
"""Operational Governance Orchestrator.

Consolida leitura executiva dos principais workflows de governanca operacional
sem executar remediacao, merge, deploy ou alteracao de producao.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CRITICAL_WORKFLOWS = {
    "CI — ReqSys v2 Enterprise",
    "CI Enterprise Fast",
    "Fast CI - Operational Guardrails",
    "Governance Quality Gates",
    "Governança Padrão Ouro",
    "Trilha D — Qualidade e Governança",
    "PR CI Watch",
    "PR Evidence Gate",
    "PR Conflict Guard",
    "Branch Protection Audit",
    "Main Post-Merge Validation",
    "Actions Auto Operator",
    "Workflow Command Center",
}

BLOCKING_CONCLUSIONS = {"failure", "timed_out", "action_required"}
NON_BLOCKING_CONCLUSIONS = {"success", "neutral", "skipped", "cancelled"}


@dataclass(frozen=True)
class WorkflowRun:
    id: int
    name: str
    status: str
    conclusion: str | None
    event: str
    branch: str | None
    sha: str | None
    url: str
    created_at: str | None
    updated_at: str | None

    @property
    def is_critical(self) -> bool:
        return self.name in CRITICAL_WORKFLOWS

    @property
    def health(self) -> str:
        if self.status != "completed":
            return "pending"
        if self.conclusion == "success":
            return "green"
        if self.conclusion in BLOCKING_CONCLUSIONS:
            return "red"
        if self.conclusion in NON_BLOCKING_CONCLUSIONS:
            return "yellow"
        return "unknown"


def github_request(url: str, token: str) -> Any:
    request = Request(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - GitHub API URL is controlled.
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API error {exc.code} for {url}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"GitHub API connection error for {url}: {exc}") from exc


def repo_api(repo: str, path: str) -> str:
    return f"https://api.github.com/repos/{repo}/{path.lstrip('/')}"


def fetch_runs(repo: str, token: str, branch: str, limit: int) -> list[WorkflowRun]:
    data = github_request(repo_api(repo, f"actions/runs?branch={branch}&per_page={limit}"), token)
    runs = []
    for item in data.get("workflow_runs", []):
        runs.append(
            WorkflowRun(
                id=int(item.get("id") or 0),
                name=item.get("name") or "workflow-desconhecido",
                status=item.get("status") or "unknown",
                conclusion=item.get("conclusion"),
                event=item.get("event") or "unknown",
                branch=item.get("head_branch"),
                sha=item.get("head_sha"),
                url=item.get("html_url") or "",
                created_at=item.get("created_at"),
                updated_at=item.get("updated_at"),
            )
        )
    return runs


def fetch_open_prs(repo: str, token: str, limit: int) -> list[dict[str, Any]]:
    data = github_request(repo_api(repo, f"pulls?state=open&per_page={limit}"), token)
    prs = []
    for item in data:
        prs.append(
            {
                "number": item.get("number"),
                "title": item.get("title"),
                "draft": item.get("draft"),
                "state": item.get("state"),
                "base": item.get("base", {}).get("ref"),
                "head": item.get("head", {}).get("ref"),
                "head_sha": item.get("head", {}).get("sha"),
                "url": item.get("html_url"),
                "updated_at": item.get("updated_at"),
            }
        )
    return prs


def build_report(repo: str, branch: str, runs: list[WorkflowRun], prs: list[dict[str, Any]]) -> dict[str, Any]:
    critical = [run for run in runs if run.is_critical]
    health_counts = Counter(run.health for run in critical)
    red = [run for run in critical if run.health == "red"]
    pending = [run for run in critical if run.health == "pending"]
    missing = sorted(CRITICAL_WORKFLOWS - {run.name for run in critical})
    green = health_counts.get("green", 0)
    total = len(critical)
    score = round((green / total) * 100, 2) if total else 0.0

    if red:
        state = "red"
        decision = "bloquear_novos_merges_e_corrigir_falhas_reais"
    elif pending:
        state = "yellow"
        decision = "aguardar_checks_pendentes_ou_validar_logs"
    elif missing:
        state = "yellow"
        decision = "validar_workflows_ausentes_na_janela_recente"
    else:
        state = "green"
        decision = "continuar_incrementos"

    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repository": repo,
        "branch": branch,
        "mode": "report_only",
        "state": state,
        "decision": decision,
        "operational_score": score,
        "summary": {
            "recent_runs": len(runs),
            "critical_runs": total,
            "green": health_counts.get("green", 0),
            "yellow": health_counts.get("yellow", 0),
            "red": health_counts.get("red", 0),
            "pending": health_counts.get("pending", 0),
            "unknown": health_counts.get("unknown", 0),
            "missing_critical_workflows": len(missing),
            "open_prs": len(prs),
            "draft_prs": sum(1 for pr in prs if pr.get("draft")),
        },
        "missing_critical_workflows": missing,
        "red_runs": [asdict(run) | {"health": run.health} for run in red],
        "pending_runs": [asdict(run) | {"health": run.health} for run in pending],
        "critical_runs": [asdict(run) | {"health": run.health} for run in critical],
        "open_prs": prs,
        "guardrails": {
            "merge": False,
            "deploy": False,
            "production_change": False,
            "rerun": False,
            "branch_protection_change": False,
        },
    }


def write_report(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "operational-governance-orchestrator.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Operational Governance Orchestrator",
        "",
        f"- Repository: `{report['repository']}`",
        f"- Branch: `{report['branch']}`",
        f"- Mode: `{report['mode']}`",
        f"- State: `{report['state']}`",
        f"- Operational score: `{report['operational_score']}%`",
        f"- Decision: `{report['decision']}`",
        f"- Generated at: `{report['generated_at']}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for key, value in report["summary"].items():
        lines.append(f"| `{key}` | `{value}` |")

    lines.extend(["", "## Red runs", ""])
    if report["red_runs"]:
        for run in report["red_runs"]:
            lines.append(f"- [{run['name']}]({run['url']}) — `{run['conclusion']}` — `{run['event']}`")
    else:
        lines.append("- None")

    lines.extend(["", "## Pending runs", ""])
    if report["pending_runs"]:
        for run in report["pending_runs"]:
            lines.append(f"- [{run['name']}]({run['url']}) — `{run['status']}` — `{run['event']}`")
    else:
        lines.append("- None")

    lines.extend(["", "## Missing critical workflows", ""])
    if report["missing_critical_workflows"]:
        for name in report["missing_critical_workflows"]:
            lines.append(f"- `{name}`")
    else:
        lines.append("- None")

    lines.extend(["", "## Guardrails", ""])
    for key, value in report["guardrails"].items():
        lines.append(f"- `{key}`: `{value}`")

    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Operational Governance Orchestrator report-only.")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--branch", default="main")
    parser.add_argument("--run-limit", type=int, default=50)
    parser.add_argument("--pr-limit", type=int, default=30)
    parser.add_argument("--output-dir", default="artifacts/operational-governance-orchestrator")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN is required", file=sys.stderr)
        return 2
    if not args.repo:
        print("--repo or GITHUB_REPOSITORY is required", file=sys.stderr)
        return 2

    runs = fetch_runs(args.repo, token, args.branch, args.run_limit)
    prs = fetch_open_prs(args.repo, token, args.pr_limit)
    report = build_report(args.repo, args.branch, runs, prs)
    write_report(report, Path(args.output_dir))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if report["state"] == "red" else 0


if __name__ == "__main__":
    raise SystemExit(main())
