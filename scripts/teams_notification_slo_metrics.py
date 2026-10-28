"""Classifica execução de workflows sem inventar entrega no Microsoft Teams."""

from __future__ import annotations

import math
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

CANDIDATE_EVENTS = frozenset({"push", "workflow_run"})
WATCHDOG_EVENT = "schedule"


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("run_timestamp_without_timezone")
    return parsed.astimezone(timezone.utc)


def calculate_metrics(
    pages: list[dict[str, Any]],
    *,
    now: datetime,
    window_days: int,
    target_percent: float,
) -> dict[str, Any]:
    """Resume dados GitHub; a conclusão da Action NÃO é recibo do Teams."""
    if now.tzinfo is None or window_days <= 0 or not 0 < target_percent <= 100:
        raise ValueError("invalid_slo_parameters")
    now = now.astimezone(timezone.utc)
    cutoff = now - timedelta(days=window_days)

    indexed: dict[int, dict[str, Any]] = {}
    for page in pages:
        if not isinstance(page, dict) or not isinstance(page.get("workflow_runs"), list):
            raise ValueError("invalid_github_page")
        for run in page["workflow_runs"]:
            if run.get("status") != "completed":
                continue
            run_id = run.get("id")
            if isinstance(run_id, bool) or not isinstance(run_id, int) or run_id <= 0:
                raise ValueError("invalid_run_id")
            created = _timestamp(run["created_at"])
            if not cutoff <= created <= now:
                continue
            previous = indexed.get(run_id)
            if previous is None or int(run.get("run_attempt") or 1) > int(
                previous.get("run_attempt") or 1
            ):
                indexed[run_id] = run

    runs = sorted(indexed.values(), key=lambda item: item["created_at"], reverse=True)
    candidates = [r for r in runs if r.get("event") in CANDIDATE_EVENTS]
    watchdog = [r for r in runs if r.get("event") == WATCHDOG_EVENT]
    excluded = [r for r in runs if r.get("event") not in CANDIDATE_EVENTS]

    conclusions = Counter(str(r.get("conclusion") or "unknown") for r in candidates)
    watchdog_conclusions = Counter(
        str(r.get("conclusion") or "unknown") for r in watchdog
    )
    events = Counter(str(r.get("event") or "unknown") for r in runs)
    total = len(candidates)
    successes = conclusions["success"]
    non_successes = total - successes
    rate = round(successes / total * 100, 2) if total else 0.0
    allowed = math.floor(total * (100 - target_percent) / 100)
    durations = []
    for run in candidates:
        started = run.get("run_started_at") or run.get("created_at")
        finished = run.get("updated_at")
        if started and finished:
            durations.append(max(0.0, (_timestamp(finished) - _timestamp(started)).total_seconds()))
    consecutive = 0
    for run in candidates:
        if run.get("conclusion") == "success":
            break
        consecutive += 1

    workflow_state = (
        "insufficient_data" if total == 0
        else "healthy" if rate >= target_percent else "breached"
    )
    return {
        "schema_version": "2.0.0",
        "service": "github-teams-commit-notification",
        "generated_at": now.isoformat(),
        "window_days": window_days,
        "target_percent": target_percent,
        "state": "insufficient_data" if not total else "unverified_delivery",
        "workflow_execution_state": workflow_state,
        "delivery_state": "unverified",
        "delivery_verified": False,
        "delivery_success_rate_percent": None,
        "remaining_delivery_error_budget": None,
        "metric_kind": "workflow_execution_proxy_not_delivery",
        "delivery_candidate_events": sorted(CANDIDATE_EVENTS),
        "total_runs": total,
        "successful_runs": successes,
        "failed_runs": non_successes,
        "non_successful_runs": non_successes,
        "workflow_execution_errors": conclusions["failure"] + conclusions["timed_out"],
        "workflow_conclusions": dict(sorted(conclusions.items())),
        "all_events": dict(sorted(events.items())),
        "excluded_non_candidate_runs": len(excluded),
        "success_rate_percent": rate,
        "workflow_success_rate_percent": rate,
        "allowed_failures": allowed,
        "remaining_error_budget": allowed - non_successes,
        "consecutive_failures": consecutive,
        "mean_duration_seconds": round(sum(durations) / len(durations), 2)
        if durations else 0.0,
        "locator_watch": {
            "total_runs": len(watchdog),
            "successful_runs": watchdog_conclusions["success"],
            "non_successful_runs": len(watchdog) - watchdog_conclusions["success"],
            "conclusions": dict(sorted(watchdog_conclusions.items())),
        },
        "latest_run": None if not candidates else {
            k: candidates[0].get(k)
            for k in ("id", "event", "conclusion", "created_at", "html_url", "head_sha")
        },
        "recent_runs": [
            {k: r.get(k) for k in ("id", "event", "conclusion", "created_at", "html_url")}
            for r in candidates[:20]
        ],
    }
