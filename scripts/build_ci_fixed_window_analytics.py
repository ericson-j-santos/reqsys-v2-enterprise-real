#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from build_ci_process_improvement_analytics import build_summary, github_api, parse_dt, render_markdown

POLICY_ID = "fixed-60m-settle-5m-min30-v1"
DEFAULT_WINDOW_MINUTES = 60
DEFAULT_SETTLE_MINUTES = 5
DEFAULT_ANCHOR_MINUTE = 40
DEFAULT_MIN_COMPLETED_RUNS = 30
DEFAULT_MIN_COMPLETION_COVERAGE_PERCENT = 90.0
DEFAULT_MAX_FETCH_PAGES = 20
DEFAULT_PER_PAGE = 100


def fixed_window_bounds(
    as_of: datetime,
    *,
    window_minutes: int = DEFAULT_WINDOW_MINUTES,
    settle_minutes: int = DEFAULT_SETTLE_MINUTES,
    anchor_minute: int = DEFAULT_ANCHOR_MINUTE,
) -> tuple[datetime, datetime]:
    if not 0 <= anchor_minute <= 59:
        raise ValueError("anchor_minute deve estar entre 0 e 59")
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    as_of = as_of.astimezone(timezone.utc)
    ready_before = as_of - timedelta(minutes=max(0, settle_minutes))
    end_at = as_of.replace(minute=anchor_minute, second=0, microsecond=0)
    if end_at > ready_before:
        end_at -= timedelta(hours=1)
    return end_at - timedelta(minutes=max(1, window_minutes)), end_at


def _in_window(run: dict[str, Any], start_at: datetime, end_at: datetime) -> bool:
    created_at = parse_dt(run.get("created_at"))
    return created_at is not None and start_at <= created_at < end_at


def fetch_runs_for_window(
    owner: str,
    name: str,
    token: str,
    *,
    start_at: datetime,
    max_pages: int = DEFAULT_MAX_FETCH_PAGES,
    per_page: int = DEFAULT_PER_PAGE,
    api_get: Callable[[str, str], dict[str, Any]] = github_api,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    complete = False
    pages = 0
    for page in range(1, max(1, max_pages) + 1):
        payload = api_get(f"/repos/{owner}/{name}/actions/runs?per_page={per_page}&page={page}", token)
        batch = list(payload.get("workflow_runs") or [])
        pages = page
        collected.extend(batch)
        if not batch:
            complete = True
            break
        created = [parse_dt(item.get("created_at")) for item in batch]
        valid = [value for value in created if value is not None]
        if valid and min(valid) < start_at:
            complete = True
            break
        if len(batch) < per_page:
            complete = True
            break
    return collected, {
        "collection_complete": complete,
        "fetched_pages": pages,
        "fetched_runs": len(collected),
        "max_fetch_pages": max_pages,
        "per_page": per_page,
    }


def build_fixed_window_summary(
    raw_runs: list[dict[str, Any]],
    *,
    repository: str,
    as_of: datetime,
    window_minutes: int = DEFAULT_WINDOW_MINUTES,
    settle_minutes: int = DEFAULT_SETTLE_MINUTES,
    anchor_minute: int = DEFAULT_ANCHOR_MINUTE,
    min_completed_runs: int = DEFAULT_MIN_COMPLETED_RUNS,
    min_completion_coverage_percent: float = DEFAULT_MIN_COMPLETION_COVERAGE_PERCENT,
    collection_complete: bool = True,
    fetched_pages: int = 1,
    fetched_runs: int | None = None,
    warning_seconds: int = 900,
    alert_seconds: int = 3600,
    baseline_incident_minutes: int = 143,
    event_name: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    start_at, end_at = fixed_window_bounds(
        as_of,
        window_minutes=window_minutes,
        settle_minutes=settle_minutes,
        anchor_minute=anchor_minute,
    )
    cohort = [run for run in raw_runs if _in_window(run, start_at, end_at)]
    # O coletor legado calcula as métricas; o limite de slice precisa cobrir todo o cohort.
    summary = build_summary(
        cohort,
        repository=repository,
        window_runs=max(1, len(cohort)),
        warning_seconds=warning_seconds,
        alert_seconds=alert_seconds,
        baseline_incident_minutes=baseline_incident_minutes,
        event_name=event_name,
        run_id=run_id,
        generated_at=as_of.astimezone(timezone.utc).isoformat(),
    )
    completed = int(summary.get("completed_runs") or 0)
    runs_in_window = len(cohort)
    coverage = round((completed / runs_in_window) * 100, 2) if runs_in_window else 0.0
    reasons: list[str] = []
    if not collection_complete:
        reasons.append("collection_incomplete")
    if completed < min_completed_runs:
        reasons.append("completed_runs_below_minimum")
    if coverage < min_completion_coverage_percent:
        reasons.append("completion_coverage_below_minimum")
    eligible = not reasons

    # Compatibilidade: o campo legado permanece dentro do contrato 1.0.x.
    summary["window_runs"] = min(max(1, runs_in_window), 100)
    hours = window_minutes / 60.0
    summary["throughput"] = {
        "window_span_hours": round(hours, 2),
        "runs_per_hour": round(completed / hours, 2) if hours else 0.0,
        "runs_per_day": round((completed / hours) * 24, 2) if hours else 0.0,
    }
    window_id = f"{POLICY_ID}:{start_at.isoformat()}:{end_at.isoformat()}"
    summary["collection_window"] = {
        "policy_id": POLICY_ID,
        "window_id": window_id,
        "mode": "fixed_time",
        "duration_minutes": window_minutes,
        "settle_minutes": settle_minutes,
        "anchor_minute": anchor_minute,
        "start_at": start_at.isoformat(),
        "end_at": end_at.isoformat(),
        "min_completed_runs": min_completed_runs,
        "min_completion_coverage_percent": min_completion_coverage_percent,
        "runs_in_window": runs_in_window,
        "completed_runs": completed,
        "incomplete_runs": max(0, runs_in_window - completed),
        "completion_coverage_percent": coverage,
        "collection_complete": bool(collection_complete),
        "fetched_pages": fetched_pages,
        "fetched_runs": int(fetched_runs if fetched_runs is not None else len(raw_runs)),
        "sample_eligible": eligible,
        "eligibility_reason_codes": reasons,
        "creates_gate": False,
    }
    if not eligible:
        summary["status"] = "warning"
        summary.setdefault("warnings", []).append(
            "Janela fixa inelegível para sustentabilidade: " + ", ".join(reasons)
        )
    return summary


def render_fixed_markdown(summary: dict[str, Any]) -> str:
    text = render_markdown(summary).rstrip()
    window = summary["collection_window"]
    lines = [
        "",
        "## Janela fixa de coleta",
        f"- Política: `{window['policy_id']}`",
        f"- Janela: `{window['start_at']}` até `{window['end_at']}`",
        f"- Duração: `{window['duration_minutes']} min`",
        f"- Maturação: `{window['settle_minutes']} min`",
        f"- Execuções na janela: `{window['runs_in_window']}`",
        f"- Concluídas: `{window['completed_runs']}`",
        f"- Cobertura de conclusão: `{window['completion_coverage_percent']}%`",
        f"- Amostra elegível: `{'sim' if window['sample_eligible'] else 'não'}`",
        f"- Motivos: `{window['eligibility_reason_codes'] or ['nenhum']}`",
        "- Cria gate: `não`",
    ]
    return text + "\n" + "\n".join(lines) + "\n"


def main() -> int:
    repository = os.environ["REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]
    owner, name = repository.split("/", 1)
    window_minutes = max(1, int(os.environ.get("WINDOW_MINUTES", DEFAULT_WINDOW_MINUTES)))
    settle_minutes = max(0, int(os.environ.get("WINDOW_SETTLE_MINUTES", DEFAULT_SETTLE_MINUTES)))
    anchor_minute = int(os.environ.get("WINDOW_ANCHOR_MINUTE", DEFAULT_ANCHOR_MINUTE))
    min_completed = max(1, int(os.environ.get("MIN_COMPLETED_RUNS", DEFAULT_MIN_COMPLETED_RUNS)))
    min_coverage = float(os.environ.get("MIN_COMPLETION_COVERAGE_PERCENT", DEFAULT_MIN_COMPLETION_COVERAGE_PERCENT))
    max_pages = max(1, int(os.environ.get("MAX_FETCH_PAGES", DEFAULT_MAX_FETCH_PAGES)))
    as_of = datetime.now(timezone.utc)
    start_at, _ = fixed_window_bounds(
        as_of, window_minutes=window_minutes, settle_minutes=settle_minutes, anchor_minute=anchor_minute
    )
    raw_runs, meta = fetch_runs_for_window(
        owner, name, token, start_at=start_at, max_pages=max_pages
    )
    summary = build_fixed_window_summary(
        raw_runs,
        repository=repository,
        as_of=as_of,
        window_minutes=window_minutes,
        settle_minutes=settle_minutes,
        anchor_minute=anchor_minute,
        min_completed_runs=min_completed,
        min_completion_coverage_percent=min_coverage,
        collection_complete=bool(meta["collection_complete"]),
        fetched_pages=int(meta["fetched_pages"]),
        fetched_runs=int(meta["fetched_runs"]),
        warning_seconds=int(os.environ.get("LEAD_TIME_WARNING_SECONDS", "900")),
        alert_seconds=int(os.environ.get("LEAD_TIME_ALERT_SECONDS", "3600")),
        baseline_incident_minutes=int(os.environ.get("BASELINE_INCIDENT_MINUTES", "143")),
        event_name=os.environ.get("EVENT_NAME"),
        run_id=os.environ.get("RUN_ID"),
    )
    Path("audit").mkdir(exist_ok=True)
    Path("audit/ci-lead-time-analytics.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    Path("audit/ci-lead-time-analytics.md").write_text(render_fixed_markdown(summary), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
