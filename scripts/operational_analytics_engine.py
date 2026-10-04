#!/usr/bin/env python3
"""Operational Analytics & Trend Engine.

Gera analytics operacional a partir de runs recentes do GitHub Actions.
Modo somente leitura: não executa rerun, merge, deploy ou alteração de produção.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BLOCKING_CONCLUSIONS = {"failure", "timed_out", "action_required"}
ATTENTION_CONCLUSIONS = {"cancelled", "neutral", "skipped"}


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
    run_started_at: str | None

    @property
    def health(self) -> str:
        if self.status != "completed":
            return "pending"
        if self.conclusion == "success":
            return "green"
        if self.conclusion in BLOCKING_CONCLUSIONS:
            return "red"
        if self.conclusion in ATTENTION_CONCLUSIONS:
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
    return [
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
            run_started_at=item.get("run_started_at"),
        )
        for item in data.get("workflow_runs", [])
    ]


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def duration_seconds(run: WorkflowRun) -> float | None:
    start = parse_dt(run.run_started_at or run.created_at)
    end = parse_dt(run.updated_at)
    if not start or not end:
        return None
    return max((end - start).total_seconds(), 0.0)


def build_report(repo: str, branch: str, runs: list[WorkflowRun]) -> dict[str, Any]:
    health_counts = Counter(run.health for run in runs)
    conclusion_counts = Counter(run.conclusion or run.status for run in runs)
    workflow_groups: dict[str, list[WorkflowRun]] = defaultdict(list)
    for run in runs:
        workflow_groups[run.name].append(run)

    workflow_stats = []
    for name, grouped in sorted(workflow_groups.items()):
        total = len(grouped)
        success = sum(1 for run in grouped if run.conclusion == "success")
        red = sum(1 for run in grouped if run.health == "red")
        yellow = sum(1 for run in grouped if run.health == "yellow")
        pending = sum(1 for run in grouped if run.health == "pending")
        durations = [value for run in grouped if (value := duration_seconds(run)) is not None]
        workflow_stats.append(
            {
                "workflow": name,
                "runs": total,
                "success": success,
                "success_rate": round((success / total) * 100, 2) if total else 0.0,
                "red": red,
                "yellow": yellow,
                "pending": pending,
                "avg_duration_seconds": round(statistics.mean(durations), 2) if durations else None,
                "latest_url": grouped[0].url if grouped else "",
            }
        )

    total = len(runs)
    success = health_counts.get("green", 0)
    red = health_counts.get("red", 0)
    pending = health_counts.get("pending", 0)
    success_rate = round((success / total) * 100, 2) if total else 0.0
    instability = round(((red + health_counts.get("yellow", 0)) / total) * 100, 2) if total else 0.0

    if red:
        trend = "regressao"
    elif pending:
        trend = "observacao"
    elif success_rate >= 95:
        trend = "estavel"
    else:
        trend = "atenção"

    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repository": repo,
        "branch": branch,
        "mode": "analytics_read_only",
        "summary": {
            "runs": total,
            "success_rate": success_rate,
            "instability_rate": instability,
            "green": health_counts.get("green", 0),
            "yellow": health_counts.get("yellow", 0),
            "red": red,
            "pending": pending,
            "unknown": health_counts.get("unknown", 0),
            "trend": trend,
        },
        "conclusion_counts": dict(conclusion_counts),
        "workflow_stats": sorted(workflow_stats, key=lambda item: (item["red"], item["yellow"], -item["success_rate"]), reverse=True),
        "recent_runs": [asdict(run) | {"health": run.health, "duration_seconds": duration_seconds(run)} for run in runs],
        "guardrails": {
            "merge": False,
            "deploy": False,
            "production_change": False,
            "rerun": False,
            "secrets_change": False,
            "branch_protection_change": False,
        },
    }


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def build_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    rows = []
    for item in report["workflow_stats"]:
        rows.append(
            "<tr>"
            f"<td>{esc(item['workflow'])}</td>"
            f"<td>{esc(item['runs'])}</td>"
            f"<td>{esc(item['success_rate'])}%</td>"
            f"<td>{esc(item['red'])}</td>"
            f"<td>{esc(item['yellow'])}</td>"
            f"<td>{esc(item['pending'])}</td>"
            f"<td>{esc(item['avg_duration_seconds'])}</td>"
            f"<td><a href=\"{esc(item['latest_url'])}\">abrir</a></td>"
            "</tr>"
        )
    table_rows = "\n".join(rows) or '<tr><td colspan="8">Sem dados.</td></tr>'
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Operational Analytics & Trend Engine</title>
<style>
:root {{ --bg:#0f172a; --panel:#111827; --muted:#9ca3af; --text:#e5e7eb; --border:#334155; --ok:#16a34a; --warn:#ca8a04; --bad:#dc2626; }}
* {{ box-sizing:border-box; }} body {{ margin:0; font-family:Arial,sans-serif; background:var(--bg); color:var(--text); }}
header {{ padding:24px; border-bottom:1px solid var(--border); background:linear-gradient(135deg,#0f172a,#1e293b); }}
main {{ padding:24px; display:grid; gap:18px; }}
.grid {{ display:grid; grid-template-columns:repeat(5,minmax(140px,1fr)); gap:12px; }}
.card {{ background:var(--panel); border:1px solid var(--border); border-radius:14px; padding:16px; }}
.metric-title {{ color:var(--muted); font-size:12px; text-transform:uppercase; }} .metric-value {{ display:block; font-size:26px; margin-top:8px; font-weight:700; }}
table {{ width:100%; border-collapse:collapse; }} th,td {{ padding:10px 12px; border-bottom:1px solid var(--border); text-align:left; font-size:13px; }} th {{ color:#cbd5e1; }}
a {{ color:#93c5fd; }} .muted {{ color:var(--muted); }}
@media(max-width:900px){{ .grid{{ grid-template-columns:1fr 1fr; }} table{{ display:block; overflow-x:auto; }} }}
@media(max-width:560px){{ .grid{{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>
<header>
<h1>Operational Analytics & Trend Engine</h1>
<p class="muted">Repo: <strong>{esc(report['repository'])}</strong> · Branch: <strong>{esc(report['branch'])}</strong> · Atualizado: <strong>{esc(report['generated_at'])}</strong></p>
</header>
<main>
<section class="grid">
<div class="card"><span class="metric-title">Runs</span><strong class="metric-value">{esc(summary['runs'])}</strong></div>
<div class="card"><span class="metric-title">Sucesso</span><strong class="metric-value">{esc(summary['success_rate'])}%</strong></div>
<div class="card"><span class="metric-title">Instabilidade</span><strong class="metric-value">{esc(summary['instability_rate'])}%</strong></div>
<div class="card"><span class="metric-title">Falhas</span><strong class="metric-value">{esc(summary['red'])}</strong></div>
<div class="card"><span class="metric-title">Tendência</span><strong class="metric-value">{esc(summary['trend'])}</strong></div>
</section>
<section class="card">
<h2>Heatmap de workflows</h2>
<table><thead><tr><th>Workflow</th><th>Runs</th><th>Sucesso</th><th>Falhas</th><th>Atenção</th><th>Pendentes</th><th>Duração média s</th><th>Link</th></tr></thead><tbody>{table_rows}</tbody></table>
</section>
</main>
</body>
</html>
"""


def write_outputs(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "operational-analytics.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "dashboard.html").write_text(build_html(report), encoding="utf-8")
    lines = [
        "# Operational Analytics & Trend Engine",
        "",
        f"- Repository: `{report['repository']}`",
        f"- Branch: `{report['branch']}`",
        f"- Generated at: `{report['generated_at']}`",
        f"- Trend: `{report['summary']['trend']}`",
        f"- Success rate: `{report['summary']['success_rate']}%`",
        f"- Instability rate: `{report['summary']['instability_rate']}%`",
        "",
        "## Guard rails",
    ]
    for key, value in report["guardrails"].items():
        lines.append(f"- `{key}`: `{value}`")
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Operational analytics and trend engine.")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--branch", default="main")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--output-dir", default="artifacts/operational-analytics")
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
    report = build_report(args.repo, args.branch, runs)
    write_outputs(report, Path(args.output_dir))
    print(json.dumps(report["summary"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
