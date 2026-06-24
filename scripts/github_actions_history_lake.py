#!/usr/bin/env python3
"""GitHub Actions History Lake collector for ReqSys.

Collects GitHub Actions workflow runs from the GitHub REST API and builds a
persistent, deduplicated operational history dataset. The script is intentionally
read-only against GitHub APIs and writes only local artifacts/data files.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BLOCKING_CONCLUSIONS = {"failure", "timed_out", "action_required"}
NON_BLOCKING_CONCLUSIONS = {"cancelled", "skipped", "neutral"}


@dataclass(frozen=True)
class WorkflowRunRecord:
    id: int
    run_number: int | None
    run_attempt: int | None
    workflow_id: int | None
    workflow_name: str
    workflow_path: str | None
    event: str
    status: str
    conclusion: str | None
    branch: str | None
    commit_sha: str | None
    actor: str | None
    created_at: str | None
    updated_at: str | None
    started_at: str | None
    duration_seconds: int | None
    url: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _duration_seconds(start: str | None, end: str | None) -> int | None:
    started = _parse_dt(start)
    finished = _parse_dt(end)
    if not started or not finished:
        return None
    return max(0, int((finished - started).total_seconds()))


def _github_request(method: str, url: str, token: str) -> Any:
    request = Request(
        url,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urlopen(request, timeout=45) as response:  # noqa: S310 - controlled GitHub API URL.
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API error {exc.code} for {method} {url}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"GitHub API connection error for {method} {url}: {exc}") from exc


def _repo_api(repo: str, path: str, params: dict[str, Any] | None = None) -> str:
    base = f"https://api.github.com/repos/{repo}/{path.lstrip('/')}"
    return base if not params else f"{base}?{urlencode(params)}"


def _record_from_run(run: dict[str, Any]) -> WorkflowRunRecord:
    started_at = run.get("run_started_at") or run.get("created_at")
    updated_at = run.get("updated_at")
    return WorkflowRunRecord(
        id=int(run["id"]),
        run_number=run.get("run_number"),
        run_attempt=run.get("run_attempt"),
        workflow_id=run.get("workflow_id"),
        workflow_name=run.get("name") or "unknown",
        workflow_path=run.get("path"),
        event=run.get("event") or "unknown",
        status=run.get("status") or "unknown",
        conclusion=run.get("conclusion"),
        branch=run.get("head_branch"),
        commit_sha=run.get("head_sha"),
        actor=(run.get("actor") or {}).get("login"),
        created_at=run.get("created_at"),
        updated_at=updated_at,
        started_at=started_at,
        duration_seconds=_duration_seconds(started_at, updated_at),
        url=run.get("html_url") or "",
    )


def fetch_runs(repo: str, token: str, branch: str | None, pages: int, per_page: int) -> list[WorkflowRunRecord]:
    records: list[WorkflowRunRecord] = []
    for page in range(1, pages + 1):
        params: dict[str, Any] = {"per_page": per_page, "page": page}
        if branch:
            params["branch"] = branch
        payload = _github_request("GET", _repo_api(repo, "actions/runs", params), token)
        runs = payload.get("workflow_runs", [])
        if not runs:
            break
        records.extend(_record_from_run(run) for run in runs)
    return records


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in records) + "\n", encoding="utf-8")


def merge_records(existing: list[dict[str, Any]], fresh: list[WorkflowRunRecord]) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    for item in existing:
        key = f"{item.get('id')}:{item.get('run_attempt')}"
        by_key[key] = item
    for item in fresh:
        row = asdict(item)
        key = f"{row.get('id')}:{row.get('run_attempt')}"
        by_key[key] = row
    return sorted(by_key.values(), key=lambda row: str(row.get("created_at") or ""), reverse=True)


def _health(row: dict[str, Any]) -> str:
    conclusion = row.get("conclusion")
    if row.get("status") != "completed":
        return "pending"
    if conclusion == "success":
        return "success"
    if conclusion in BLOCKING_CONCLUSIONS:
        return "blocking_failure"
    if conclusion in NON_BLOCKING_CONCLUSIONS:
        return "non_blocking"
    return "unknown"


def build_summary(records: list[dict[str, Any]], fresh_count: int) -> dict[str, Any]:
    total = len(records)
    completed = sum(1 for row in records if row.get("status") == "completed")
    success = sum(1 for row in records if _health(row) == "success")
    failures = sum(1 for row in records if _health(row) == "blocking_failure")
    pending = sum(1 for row in records if _health(row) == "pending")
    durations = [int(row["duration_seconds"]) for row in records if isinstance(row.get("duration_seconds"), int)]
    workflow_names = sorted({row.get("workflow_name") or "unknown" for row in records})
    success_rate = round((success / completed) * 100, 2) if completed else 0.0
    failure_rate = round((failures / completed) * 100, 2) if completed else 0.0
    avg_duration = round(sum(durations) / len(durations), 2) if durations else 0.0
    precision_estimate = round(max(0.0, min(99.9, 100 - failure_rate - (pending * 0.15))), 2)
    risk_estimate = round(max(0.0, min(100.0, failure_rate + (pending * 0.15))), 2)
    return {
        "generated_at": _utc_now(),
        "fresh_records_collected": fresh_count,
        "total_records": total,
        "completed_records": completed,
        "success_records": success,
        "blocking_failure_records": failures,
        "pending_records": pending,
        "workflow_count": len(workflow_names),
        "workflow_names": workflow_names,
        "success_rate_percent": success_rate,
        "blocking_failure_rate_percent": failure_rate,
        "average_duration_seconds": avg_duration,
        "precision_estimate_percent": precision_estimate,
        "risk_estimate_percent": risk_estimate,
        "readiness_state": "HISTORY_BASELINE_READY" if total >= 30 else "HISTORY_BASELINE_WARMING_UP",
    }


def render_markdown(summary: dict[str, Any], records: list[dict[str, Any]]) -> str:
    lines = [
        "# GitHub Actions History Lake",
        "",
        f"Generated at: `{summary['generated_at']}`",
        "",
        "## Executive indicators",
        "",
        f"- Readiness: `{summary['readiness_state']}`",
        f"- Total records: `{summary['total_records']}`",
        f"- Success rate: `{summary['success_rate_percent']}%`",
        f"- Blocking failure rate: `{summary['blocking_failure_rate_percent']}%`",
        f"- Precision estimate: `{summary['precision_estimate_percent']}%`",
        f"- Risk estimate: `{summary['risk_estimate_percent']}%`",
        f"- Average duration: `{summary['average_duration_seconds']}s`",
        "",
        "## Latest runs",
        "",
    ]
    for row in records[:20]:
        lines.append(f"- `{_health(row)}` [{row.get('workflow_name')}]({row.get('url')}) — `{row.get('conclusion')}` — `{row.get('updated_at')}`")
    return "\n".join(lines) + "\n"


def render_html(summary: dict[str, Any], records: list[dict[str, Any]]) -> str:
    rows = []
    for row in records[:50]:
        rows.append(
            "<tr>"
            f"<td>{escape(_health(row))}</td>"
            f"<td><a href=\"{escape(str(row.get('url') or ''))}\">{escape(str(row.get('workflow_name') or 'unknown'))}</a></td>"
            f"<td>{escape(str(row.get('event')))}</td>"
            f"<td>{escape(str(row.get('conclusion')))}</td>"
            f"<td>{escape(str(row.get('duration_seconds')))}</td>"
            f"<td>{escape(str(row.get('updated_at')))}</td>"
            "</tr>"
        )
    return f"""<!doctype html>
<html lang=\"pt-BR\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>ReqSys GitHub Actions History Lake</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #111827; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
    .card {{ border: 1px solid #d1d5db; border-radius: 12px; padding: 16px; background: #f9fafb; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 18px; }}
    th, td {{ border: 1px solid #e5e7eb; padding: 8px; text-align: left; font-size: 14px; }}
    th {{ background: #f3f4f6; }}
  </style>
</head>
<body>
  <h1>ReqSys GitHub Actions History Lake</h1>
  <p>Gerado em UTC: <strong>{escape(summary['generated_at'])}</strong></p>
  <div class=\"grid\">
    <div class=\"card\"><strong>Readiness</strong><br>{escape(summary['readiness_state'])}</div>
    <div class=\"card\"><strong>Total records</strong><br>{summary['total_records']}</div>
    <div class=\"card\"><strong>Success rate</strong><br>{summary['success_rate_percent']}%</div>
    <div class=\"card\"><strong>Precision estimate</strong><br>{summary['precision_estimate_percent']}%</div>
    <div class=\"card\"><strong>Risk estimate</strong><br>{summary['risk_estimate_percent']}%</div>
    <div class=\"card\"><strong>Avg duration</strong><br>{summary['average_duration_seconds']}s</div>
  </div>
  <h2>Latest workflow runs</h2>
  <table>
    <thead><tr><th>Health</th><th>Workflow</th><th>Event</th><th>Conclusion</th><th>Duration</th><th>Updated</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</body>
</html>
"""


def write_outputs(records: list[dict[str, Any]], summary: dict[str, Any], data_path: Path, artifact_dir: Path) -> None:
    write_jsonl(data_path, records)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "github-actions-history-summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (artifact_dir / "github-actions-history-lake.jsonl").write_text(data_path.read_text(encoding="utf-8"), encoding="utf-8")
    (artifact_dir / "summary.md").write_text(render_markdown(summary, records), encoding="utf-8")
    (artifact_dir / "github-actions-history-lake.html").write_text(render_html(summary, records), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect GitHub Actions workflow runs into a persistent history lake.")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--branch", default=os.environ.get("GITHUB_REF_NAME", "main"))
    parser.add_argument("--pages", type=int, default=5)
    parser.add_argument("--per-page", type=int, default=100)
    parser.add_argument("--data-path", default="data/operational/github-actions-history/runs.jsonl")
    parser.add_argument("--output-dir", default="artifacts/github-actions-history-lake")
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
    fresh = fetch_runs(args.repo, token, args.branch, args.pages, args.per_page)
    data_path = Path(args.data_path)
    records = merge_records(read_jsonl(data_path), fresh)
    summary = build_summary(records, len(fresh))
    write_outputs(records, summary, data_path, Path(args.output_dir))
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
