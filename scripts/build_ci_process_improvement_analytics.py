#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
import statistics
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * pct
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return float(ordered[int(index)])
    return float(ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower))


def rate(numerator: int, denominator: int) -> float:
    return round((numerator / denominator) * 100, 2) if denominator else 0.0


def avg(values: list[float]) -> float:
    return round(statistics.mean(values), 2) if values else 0.0


def pstdev(values: list[float]) -> float:
    return round(statistics.pstdev(values), 2) if len(values) > 1 else 0.0


def cv_percent(values: list[float]) -> float:
    mean = statistics.mean(values) if values else 0.0
    if mean <= 0:
        return 0.0
    return round((statistics.pstdev(values) / mean) * 100, 2) if len(values) > 1 else 0.0


def normalize_run(run: dict[str, Any]) -> dict[str, Any]:
    created_at = parse_dt(run.get("created_at"))
    started_at = parse_dt(run.get("run_started_at")) or created_at
    updated_at = parse_dt(run.get("updated_at"))

    if created_at is None or updated_at is None:
        raise ValueError("workflow run sem created_at/updated_at válido")

    queue_seconds = max(0.0, round(((started_at or created_at) - created_at).total_seconds(), 3))
    execution_seconds = max(0.0, round((updated_at - (started_at or created_at)).total_seconds(), 3))
    duration_seconds = max(0.0, round((updated_at - created_at).total_seconds(), 3))

    return {
        "id": int(run["id"]),
        "name": str(run["name"]),
        "event": str(run["event"]),
        "status": str(run["status"]),
        "conclusion": run.get("conclusion"),
        "head_branch": run.get("head_branch"),
        "head_sha": run.get("head_sha"),
        "html_url": run.get("html_url"),
        "created_at": run["created_at"],
        "run_started_at": run.get("run_started_at"),
        "updated_at": run["updated_at"],
        "run_attempt": int(run.get("run_attempt") or 1),
        "queue_seconds": queue_seconds,
        "execution_seconds": execution_seconds,
        "duration_seconds": duration_seconds,
        "duration_minutes": round(duration_seconds / 60, 2),
    }


def _window_metrics(runs: list[dict[str, Any]]) -> dict[str, float | int]:
    durations = [float(run["duration_seconds"]) for run in runs]
    success_count = sum(1 for run in runs if run.get("conclusion") == "success")
    failure_count = sum(1 for run in runs if run.get("conclusion") == "failure")
    return {
        "runs": len(runs),
        "success_rate_percent": rate(success_count, len(runs)),
        "failure_rate_percent": rate(failure_count, len(runs)),
        "p50_seconds": round(percentile(durations, 0.50), 2),
        "p95_seconds": round(percentile(durations, 0.95), 2),
        "cv_percent": cv_percent(durations),
    }


def _signal(delta: float, lower_is_better: bool = True, tolerance: float = 0.01) -> str:
    if abs(delta) <= tolerance:
        return "stable"
    improved = delta < 0 if lower_is_better else delta > 0
    return "improved" if improved else "regressed"


def _build_trend(completed: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(completed, key=lambda item: item["created_at"], reverse=True)
    if len(ordered) < 4:
        return {
            "available": False,
            "reason": "mínimo de 4 execuções concluídas para comparar janelas",
        }

    half = len(ordered) // 2
    current = ordered[:half]
    previous = ordered[half : half * 2]
    current_metrics = _window_metrics(current)
    previous_metrics = _window_metrics(previous)

    deltas = {
        "success_rate_pp": round(
            float(current_metrics["success_rate_percent"]) - float(previous_metrics["success_rate_percent"]), 2
        ),
        "failure_rate_pp": round(
            float(current_metrics["failure_rate_percent"]) - float(previous_metrics["failure_rate_percent"]), 2
        ),
        "p50_seconds": round(float(current_metrics["p50_seconds"]) - float(previous_metrics["p50_seconds"]), 2),
        "p95_seconds": round(float(current_metrics["p95_seconds"]) - float(previous_metrics["p95_seconds"]), 2),
        "cv_percent": round(float(current_metrics["cv_percent"]) - float(previous_metrics["cv_percent"]), 2),
    }

    return {
        "available": True,
        "current": current_metrics,
        "previous": previous_metrics,
        "delta": deltas,
        "signals": {
            "success_rate": _signal(deltas["success_rate_pp"], lower_is_better=False, tolerance=0.5),
            "failure_rate": _signal(deltas["failure_rate_pp"], lower_is_better=True, tolerance=0.5),
            "p50": _signal(deltas["p50_seconds"], lower_is_better=True, tolerance=1.0),
            "p95": _signal(deltas["p95_seconds"], lower_is_better=True, tolerance=1.0),
            "variability": _signal(deltas["cv_percent"], lower_is_better=True, tolerance=0.5),
        },
    }


def _throughput(completed: list[dict[str, Any]]) -> dict[str, float]:
    if not completed:
        return {"window_span_hours": 0.0, "runs_per_hour": 0.0, "runs_per_day": 0.0}

    starts = [parse_dt(run["created_at"]) for run in completed]
    ends = [parse_dt(run["updated_at"]) for run in completed]
    valid_starts = [value for value in starts if value is not None]
    valid_ends = [value for value in ends if value is not None]
    if not valid_starts or not valid_ends:
        return {"window_span_hours": 0.0, "runs_per_hour": 0.0, "runs_per_day": 0.0}

    span_seconds = max(1.0, (max(valid_ends) - min(valid_starts)).total_seconds())
    span_hours = span_seconds / 3600
    return {
        "window_span_hours": round(span_hours, 2),
        "runs_per_hour": round(len(completed) / span_hours, 2),
        "runs_per_day": round((len(completed) / span_hours) * 24, 2),
    }


def build_summary(
    raw_runs: list[dict[str, Any]],
    *,
    repository: str,
    window_runs: int,
    warning_seconds: int = 900,
    alert_seconds: int = 3600,
    baseline_incident_minutes: int = 143,
    event_name: str | None = None,
    run_id: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    completed: list[dict[str, Any]] = []
    by_workflow: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for raw_run in raw_runs[:window_runs]:
        normalized = normalize_run(raw_run)
        if normalized["status"] != "completed":
            continue
        completed.append(normalized)
        by_workflow[normalized["name"]].append(normalized)

    durations = [float(run["duration_seconds"]) for run in completed]
    queue_times = [float(run["queue_seconds"]) for run in completed]
    success_count = sum(1 for run in completed if run["conclusion"] == "success")
    failure_count = sum(1 for run in completed if run["conclusion"] == "failure")
    cancelled_count = sum(1 for run in completed if run["conclusion"] == "cancelled")
    skipped_count = sum(1 for run in completed if run["conclusion"] == "skipped")
    rerun_count = sum(1 for run in completed if int(run["run_attempt"]) > 1)
    first_pass_success_count = sum(
        1 for run in completed if run["conclusion"] == "success" and int(run["run_attempt"]) == 1
    )
    total_completed = len(completed)

    workflow_stats: list[dict[str, Any]] = []
    failure_pareto: list[dict[str, Any]] = []
    for workflow_name, workflow_runs in by_workflow.items():
        workflow_durations = [float(run["duration_seconds"]) for run in workflow_runs]
        workflow_queues = [float(run["queue_seconds"]) for run in workflow_runs]
        workflow_success = sum(1 for run in workflow_runs if run["conclusion"] == "success")
        workflow_failure = sum(1 for run in workflow_runs if run["conclusion"] == "failure")
        workflow_reruns = sum(1 for run in workflow_runs if int(run["run_attempt"]) > 1)
        workflow_stats.append(
            {
                "name": workflow_name,
                "runs": len(workflow_runs),
                "success_rate_percent": rate(workflow_success, len(workflow_runs)),
                "failure_rate_percent": rate(workflow_failure, len(workflow_runs)),
                "rerun_rate_percent": rate(workflow_reruns, len(workflow_runs)),
                "avg_seconds": avg(workflow_durations),
                "p50_seconds": round(percentile(workflow_durations, 0.50), 2),
                "p90_seconds": round(percentile(workflow_durations, 0.90), 2),
                "p95_seconds": round(percentile(workflow_durations, 0.95), 2),
                "max_seconds": round(max(workflow_durations), 2) if workflow_durations else 0.0,
                "stddev_seconds": pstdev(workflow_durations),
                "cv_percent": cv_percent(workflow_durations),
                "p95_queue_seconds": round(percentile(workflow_queues, 0.95), 2),
            }
        )
        if workflow_failure:
            failure_pareto.append({"name": workflow_name, "failures": workflow_failure})

    workflow_stats.sort(key=lambda item: item["p95_seconds"], reverse=True)
    bottlenecks = workflow_stats[:10]

    failure_pareto.sort(key=lambda item: (-item["failures"], item["name"]))
    cumulative = 0
    for item in failure_pareto:
        cumulative += int(item["failures"])
        item["share_percent"] = rate(int(item["failures"]), failure_count)
        item["cumulative_share_percent"] = rate(cumulative, failure_count)

    p95_seconds = round(percentile(durations, 0.95), 2)
    max_seconds = round(max(durations), 2) if durations else 0.0
    failure_rate_percent = rate(failure_count, total_completed)
    first_pass_success_rate_percent = rate(first_pass_success_count, total_completed)

    status = "passed"
    warnings: list[str] = []
    if p95_seconds >= warning_seconds:
        warnings.append(f"P95 lead time acima do warning: {p95_seconds}s >= {warning_seconds}s")
        status = "warning"
    if max_seconds >= alert_seconds:
        warnings.append(f"Max lead time acima do alerta: {max_seconds}s >= {alert_seconds}s")
        status = "warning"
    if failure_rate_percent > 5:
        warnings.append(f"Failure rate acima do alvo: {failure_rate_percent}% > 5%")
        status = "warning"
    if total_completed and first_pass_success_rate_percent < 90:
        warnings.append(
            f"First-pass success abaixo do alvo: {first_pass_success_rate_percent}% < 90%"
        )
        status = "warning"

    return {
        "schema_version": "1.0.2",
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "repository": repository,
        "event_name": event_name,
        "run_id": run_id,
        "window_runs": window_runs,
        "completed_runs": total_completed,
        "success_count": success_count,
        "failure_count": failure_count,
        "cancelled_count": cancelled_count,
        "skipped_count": skipped_count,
        "rerun_count": rerun_count,
        "first_pass_success_count": first_pass_success_count,
        "success_rate_percent": rate(success_count, total_completed),
        "failure_rate_percent": failure_rate_percent,
        "first_pass_success_rate_percent": first_pass_success_rate_percent,
        "rerun_rate_percent": rate(rerun_count, total_completed),
        "avg_seconds": avg(durations),
        "p50_seconds": round(percentile(durations, 0.50), 2),
        "p90_seconds": round(percentile(durations, 0.90), 2),
        "p95_seconds": p95_seconds,
        "max_seconds": max_seconds,
        "stddev_seconds": pstdev(durations),
        "cv_percent": cv_percent(durations),
        "avg_queue_seconds": avg(queue_times),
        "p95_queue_seconds": round(percentile(queue_times, 0.95), 2),
        "throughput": _throughput(completed),
        "trend_comparison": _build_trend(completed),
        "failure_pareto": failure_pareto,
        "baseline_incident_minutes": baseline_incident_minutes,
        "baseline_incident_seconds": baseline_incident_minutes * 60,
        "status": status,
        "warnings": warnings,
        "bottlenecks": bottlenecks,
        "workflow_stats": workflow_stats,
        "recent_completed_runs": completed[:25],
    }


def github_api(path: str, token: str) -> dict[str, Any]:
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "reqsys-ci-lead-time-analytics",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def render_markdown(summary: dict[str, Any]) -> str:
    throughput = summary["throughput"]
    trend = summary["trend_comparison"]
    lines = [
        "# CI Lead Time Analytics",
        "",
        f"- Repository: {summary['repository']}",
        f"- Status: {summary['status']}",
        f"- Completed runs: {summary['completed_runs']}",
        f"- Success rate: {summary['success_rate_percent']}%",
        f"- Failure rate: {summary['failure_rate_percent']}%",
        f"- First-pass success: {summary['first_pass_success_rate_percent']}%",
        f"- Rerun rate: {summary['rerun_rate_percent']}%",
        f"- Average lead time: {summary['avg_seconds']}s",
        f"- P50 lead time: {summary['p50_seconds']}s",
        f"- P90 lead time: {summary['p90_seconds']}s",
        f"- P95 lead time: {summary['p95_seconds']}s",
        f"- Standard deviation: {summary['stddev_seconds']}s",
        f"- Coefficient of variation: {summary['cv_percent']}%",
        f"- P95 queue time: {summary['p95_queue_seconds']}s",
        f"- Throughput: {throughput['runs_per_hour']} runs/hour",
        f"- Baseline incident: {summary['baseline_incident_minutes']}min",
        "",
        "## Warnings",
    ]
    lines.extend((f"- {warning}" for warning in summary["warnings"]) if summary["warnings"] else ["- None"])

    lines.extend(["", "## Trend comparison"])
    if trend.get("available"):
        lines.extend(
            [
                f"- P95 delta: {trend['delta']['p95_seconds']}s ({trend['signals']['p95']})",
                f"- Failure-rate delta: {trend['delta']['failure_rate_pp']} pp ({trend['signals']['failure_rate']})",
                f"- Variability delta: {trend['delta']['cv_percent']} pp ({trend['signals']['variability']})",
            ]
        )
    else:
        lines.append(f"- Unavailable: {trend.get('reason')}")

    lines.extend(["", "## Failure Pareto"])
    if summary["failure_pareto"]:
        lines.extend(
            f"- {item['name']}: failures={item['failures']}, share={item['share_percent']}%, cumulative={item['cumulative_share_percent']}%"
            for item in summary["failure_pareto"][:10]
        )
    else:
        lines.append("- None")

    lines.extend(["", "## Top bottlenecks by P95"])
    if summary["bottlenecks"]:
        lines.extend(
            f"- {item['name']}: runs={item['runs']}, success={item['success_rate_percent']}%, "
            f"p95={item['p95_seconds']}s, p95_queue={item['p95_queue_seconds']}s, "
            f"cv={item['cv_percent']}%, max={item['max_seconds']}s"
            for item in summary["bottlenecks"]
        )
    else:
        lines.append("- None")

    return "\n".join(lines) + "\n"


def main() -> int:
    repository = os.environ["REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]
    window_runs = max(1, min(int(os.environ.get("WINDOW_RUNS") or "100"), 100))
    warning_seconds = int(os.environ.get("LEAD_TIME_WARNING_SECONDS") or "900")
    alert_seconds = int(os.environ.get("LEAD_TIME_ALERT_SECONDS") or "3600")
    baseline_incident_minutes = int(os.environ.get("BASELINE_INCIDENT_MINUTES") or "143")
    owner, name = repository.split("/", 1)

    payload = github_api(f"/repos/{owner}/{name}/actions/runs?per_page={window_runs}", token)
    summary = build_summary(
        payload.get("workflow_runs", []),
        repository=repository,
        window_runs=window_runs,
        warning_seconds=warning_seconds,
        alert_seconds=alert_seconds,
        baseline_incident_minutes=baseline_incident_minutes,
        event_name=os.environ.get("EVENT_NAME"),
        run_id=os.environ.get("RUN_ID"),
    )

    Path("audit").mkdir(exist_ok=True)
    Path("audit/ci-lead-time-analytics.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    Path("audit/ci-lead-time-analytics.md").write_text(render_markdown(summary), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
