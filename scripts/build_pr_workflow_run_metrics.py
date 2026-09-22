#!/usr/bin/env python3
"""Build PR workflow run metrics from a local GitHub Actions snapshot.

O script é offline/determinístico. Ele não consulta GitHub, não usa secrets e
aceita snapshots JSON gerados por automações existentes ou coletas manuais.

Entradas aceitas:
- lista de workflow runs;
- objeto com chave `workflow_runs`;
- objeto com chave `runs`.

Campos reconhecidos por run:
- `pull_requests`: lista nativa do GitHub Actions;
- `pr_number`, `number` ou `pull_request_number`;
- `name` ou `workflow_name`;
- `status`, `conclusion`, `created_at`, `updated_at`, `html_url`.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_INPUT = "artifacts/github-actions/workflow-runs.json"
DEFAULT_OUTPUT = "docs/ops-dashboard/data/pr-workflow-run-metrics.json"
REPO = "ericson-j-santos/reqsys-v2-enterprise-real"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_runs(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        runs = payload.get("workflow_runs") or payload.get("runs") or []
        if isinstance(runs, list):
            return [item for item in runs if isinstance(item, dict)]
    return []


def pr_number(run: dict[str, Any]) -> str | None:
    for key in ("pr_number", "pull_request_number", "number"):
        value = run.get(key)
        if value is not None:
            return str(value)
    pull_requests = run.get("pull_requests") or []
    if isinstance(pull_requests, list) and pull_requests:
        first = pull_requests[0]
        if isinstance(first, dict) and first.get("number") is not None:
            return str(first["number"])
    return None


def workflow_name(run: dict[str, Any]) -> str:
    return str(run.get("name") or run.get("workflow_name") or run.get("workflow") or "unknown")


def build_metrics(runs: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    ignored_without_pr = 0

    for run in runs:
        number = pr_number(run)
        if not number:
            ignored_without_pr += 1
            continue
        grouped[number].append(run)

    pr_metrics: list[dict[str, Any]] = []
    total_workflows = 0
    max_workflows = 0

    for number, items in sorted(grouped.items(), key=lambda pair: int(pair[0]) if pair[0].isdigit() else pair[0], reverse=True):
        names = sorted({workflow_name(item) for item in items})
        completed = sum(1 for item in items if str(item.get("status") or "").lower() == "completed")
        failed = sum(1 for item in items if str(item.get("conclusion") or "").lower() in {"failure", "timed_out", "cancelled", "action_required"})
        queued_or_running = sum(1 for item in items if str(item.get("status") or "").lower() in {"queued", "in_progress", "waiting", "requested"})
        run_count = len(items)
        workflow_count = len(names)
        total_workflows += workflow_count
        max_workflows = max(max_workflows, workflow_count)

        pr_metrics.append(
            {
                "pr_number": int(number) if number.isdigit() else number,
                "workflow_count": workflow_count,
                "run_count": run_count,
                "completed_runs": completed,
                "failed_runs": failed,
                "queued_or_running_runs": queued_or_running,
                "workflows": names,
                "latest_evidence_url": next((item.get("html_url") for item in items if item.get("html_url")), None),
            }
        )

    average = round(total_workflows / len(pr_metrics), 2) if pr_metrics else 0
    status = "green" if average <= 10 else "yellow" if average <= 18 else "red"

    return {
        "schema_version": "1.0.0",
        "repo": REPO,
        "generated_at": utc_now(),
        "source_path": DEFAULT_INPUT,
        "source_available": bool(runs),
        "summary": {
            "pr_count": len(pr_metrics),
            "ignored_without_pr": ignored_without_pr,
            "average_workflows_per_pr": average,
            "max_workflows_per_pr": max_workflows,
            "pareto_status": status,
            "target_average_workflows_per_pr": 10,
        },
        "pull_requests": pr_metrics[:20],
        "links": {
            "actions": f"https://github.com/{REPO}/actions",
            "pulls": f"https://github.com/{REPO}/pulls",
        },
    }


def write_output(payload: dict[str, Any], output: str) -> None:
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gera métricas de workflows por PR.")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_metrics(load_runs(Path(args.input)))
    write_output(payload, args.output)
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        summary = payload["summary"]
        print(
            f"pareto_status={summary['pareto_status']} "
            f"average_workflows_per_pr={summary['average_workflows_per_pr']} "
            f"output={args.output}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
