#!/usr/bin/env python3
"""Generate an executive HTML dashboard for GitHub Actions workflows."""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass
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
    "Branch Protection Audit",
    "PR Conflict Guard",
    "Main Smoke CI",
    "Main Operational Health",
    "Workflow Command Center",
}


@dataclass(frozen=True)
class Run:
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


def _request(url: str, token: str) -> Any:
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
        with urlopen(request, timeout=30) as response:  # noqa: S310 - GitHub API URL is controlled by this script.
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API error {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"GitHub API connection error: {exc}") from exc


def fetch_runs(repo: str, token: str, branch: str, limit: int) -> list[Run]:
    url = f"https://api.github.com/repos/{repo}/actions/runs?branch={branch}&per_page={limit}"
    payload = _request(url, token)
    return [
        Run(
            id=run["id"],
            name=run.get("name") or "",
            status=run.get("status") or "unknown",
            conclusion=run.get("conclusion"),
            event=run.get("event") or "unknown",
            branch=run.get("head_branch"),
            sha=run.get("head_sha"),
            url=run.get("html_url") or "",
            created_at=run.get("created_at"),
            updated_at=run.get("updated_at"),
        )
        for run in payload.get("workflow_runs", [])
    ]


def summarize(runs: list[Run]) -> dict[str, Any]:
    critical = [run for run in runs if run.name in CRITICAL_WORKFLOWS]
    by_conclusion = Counter(run.conclusion or run.status for run in critical)
    failed = [run for run in critical if run.conclusion in {"failure", "cancelled", "timed_out", "action_required"}]
    pending = [run for run in critical if run.status != "completed"]
    missing = sorted(CRITICAL_WORKFLOWS - {run.name for run in critical})
    total = len(critical)
    success = by_conclusion.get("success", 0)
    success_rate = round((success / total) * 100, 2) if total else 0.0
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_recent_runs": len(runs),
        "critical_runs": total,
        "success_rate": success_rate,
        "failed_count": len(failed),
        "pending_count": len(pending),
        "missing_count": len(missing),
        "missing_workflows": missing,
        "by_conclusion": dict(by_conclusion),
        "state": "green" if not failed and not pending else "attention",
    }


def _badge(text: str, kind: str) -> str:
    return f'<span class="badge {html.escape(kind)}">{html.escape(text)}</span>'


def build_html(repo: str, runs: list[Run], summary: dict[str, Any]) -> str:
    rows = []
    for run in runs:
        kind = "ok" if run.conclusion == "success" else "warn" if run.status != "completed" else "bad"
        rows.append(
            "<tr>"
            f"<td><a href=\"{html.escape(run.url)}\">{html.escape(run.name)}</a></td>"
            f"<td>{_badge(run.conclusion or run.status, kind)}</td>"
            f"<td>{html.escape(run.event)}</td>"
            f"<td>{html.escape(run.branch or '')}</td>"
            f"<td><code>{html.escape((run.sha or '')[:12])}</code></td>"
            f"<td>{html.escape(run.updated_at or '')}</td>"
            "</tr>"
        )

    missing = "".join(f"<li>{html.escape(name)}</li>" for name in summary["missing_workflows"])
    state_badge = _badge(summary["state"].upper(), "ok" if summary["state"] == "green" else "warn")
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ReqSys Workflow Dashboard</title>
<style>
:root {{ --bg:#0f172a; --panel:#111827; --text:#e5e7eb; --muted:#9ca3af; --ok:#22c55e; --warn:#f59e0b; --bad:#ef4444; --line:#334155; }}
body {{ margin:0; font-family: Arial, sans-serif; background:var(--bg); color:var(--text); }}
header {{ padding:24px; border-bottom:1px solid var(--line); }}
main {{ padding:24px; display:grid; gap:20px; }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; }}
.card {{ background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:16px; }}
.card .label {{ color:var(--muted); font-size:12px; text-transform:uppercase; }}
.card .value {{ font-size:28px; font-weight:700; margin-top:6px; }}
table {{ width:100%; border-collapse:collapse; background:var(--panel); border-radius:14px; overflow:hidden; }}
th,td {{ padding:10px 12px; border-bottom:1px solid var(--line); text-align:left; font-size:14px; }}
th {{ color:var(--muted); }}
a {{ color:#93c5fd; text-decoration:none; }}
.badge {{ display:inline-block; padding:4px 8px; border-radius:999px; font-size:12px; font-weight:700; }}
.badge.ok {{ background:rgba(34,197,94,.15); color:var(--ok); }}
.badge.warn {{ background:rgba(245,158,11,.15); color:var(--warn); }}
.badge.bad {{ background:rgba(239,68,68,.15); color:var(--bad); }}
section {{ background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:16px; }}
code {{ color:#c4b5fd; }}
</style>
</head>
<body>
<header>
<h1>ReqSys Workflow Dashboard {state_badge}</h1>
<p>Repositório: <code>{html.escape(repo)}</code> · Gerado em <code>{html.escape(summary['generated_at'])}</code></p>
</header>
<main>
<div class="cards">
<div class="card"><div class="label">Runs recentes</div><div class="value">{summary['total_recent_runs']}</div></div>
<div class="card"><div class="label">Runs críticos</div><div class="value">{summary['critical_runs']}</div></div>
<div class="card"><div class="label">Taxa sucesso</div><div class="value">{summary['success_rate']}%</div></div>
<div class="card"><div class="label">Falhas</div><div class="value">{summary['failed_count']}</div></div>
<div class="card"><div class="label">Pendentes</div><div class="value">{summary['pending_count']}</div></div>
</div>
<section>
<h2>Workflows críticos ausentes na janela recente</h2>
<ul>{missing or '<li>Nenhum</li>'}</ul>
</section>
<section>
<h2>Runs recentes</h2>
<table>
<thead><tr><th>Workflow</th><th>Status</th><th>Evento</th><th>Branch</th><th>SHA</th><th>Atualizado</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>
</section>
</main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate workflow dashboard.")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--branch", default="main")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--output-dir", default="artifacts/workflow-dashboard")
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
    runs = fetch_runs(args.repo, token, args.branch, args.limit)
    summary = summarize(runs)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "workflow-dashboard.html").write_text(build_html(args.repo, runs, summary), encoding="utf-8")
    (output_dir / "workflow-dashboard.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
