#!/usr/bin/env python3
"""Avalia automaticamente o próximo incremento seguro do ReqSys.

Contrato report-only: não promove ambiente, não faz merge e não altera gates.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

REQUIRED_WORKFLOWS = {
    "CI — ReqSys v2 Enterprise",
    "PR Evidence Gate",
    "Governed Merge Queue",
    "Security Baseline Gate",
    "Security Specialized Scanners",
    "Instrumented Executive Readiness",
}
CI_WORKFLOW_NAME = "CI — ReqSys v2 Enterprise"
DEFAULT_AVAILABILITY_TARGET_MINUTES = 30


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def pct(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else round(numerator / denominator * 100, 2)


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def minutes_between(start: datetime | None, end: datetime | None) -> float | None:
    if not start or not end or end < start:
        return None
    return round((end - start).total_seconds() / 60, 2)


def latest_runs_by_name(runs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for run in sorted(runs, key=lambda item: item.get("created_at", ""), reverse=True):
        name = str(run.get("name") or "")
        if name and name not in latest:
            latest[name] = run
    return latest


def successful_ci_completion(
    runs: list[dict[str, Any]], merge_sha: str, merged_at: datetime
) -> datetime | None:
    candidates: list[datetime] = []
    for run in runs:
        if run.get("name") != CI_WORKFLOW_NAME:
            continue
        if run.get("head_sha") != merge_sha:
            continue
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            continue
        completed_at = parse_dt(run.get("updated_at"))
        if completed_at and completed_at >= merged_at:
            candidates.append(completed_at)
    return min(candidates) if candidates else None


def build_delivery_velocity(
    merged_prs: list[dict[str, Any]],
    runs: list[dict[str, Any]],
    runtime: dict[str, Any],
    target_minutes: int,
) -> dict[str, Any]:
    merge_lead_times: list[float] = []
    merge_to_ci_times: list[float] = []
    merged_by_sha: dict[str, dict[str, Any]] = {}

    for pr in merged_prs:
        created = parse_dt(pr.get("created_at"))
        merged = parse_dt(pr.get("merged_at"))
        merge_sha = str(pr.get("merge_commit_sha") or "")
        if created and merged and merged >= created:
            merge_lead_times.append((merged - created).total_seconds() / 60)
        if not merged or not merge_sha:
            continue
        merged_by_sha[merge_sha] = pr
        ci_completed = successful_ci_completion(runs, merge_sha, merged)
        ci_minutes = minutes_between(merged, ci_completed)
        if ci_minutes is not None:
            merge_to_ci_times.append(ci_minutes)

    runtime_build_sha = str(runtime.get("build_sha") or "").strip()
    runtime_observed_at = parse_dt(runtime.get("observed_at"))
    runtime_healthy = runtime.get("healthy") is True
    runtime_match = merged_by_sha.get(runtime_build_sha)

    merge_to_runtime_minutes = None
    created_to_runtime_minutes = None
    matched_pr_number = None
    matched_merge_sha = None
    measurement_gaps: list[str] = []

    if not runtime_build_sha or runtime_build_sha == "unknown":
        measurement_gaps.append("runtime_build_sha_missing")
    elif runtime_match is None:
        measurement_gaps.append("runtime_build_sha_not_mapped_to_recent_merge")
    if runtime_observed_at is None:
        measurement_gaps.append("runtime_observed_at_missing")
    if not runtime_healthy:
        measurement_gaps.append("runtime_not_healthy")

    if runtime_match and runtime_observed_at and runtime_healthy:
        merged = parse_dt(runtime_match.get("merged_at"))
        created = parse_dt(runtime_match.get("created_at"))
        if merged and runtime_observed_at >= merged:
            merge_to_runtime_minutes = minutes_between(merged, runtime_observed_at)
            created_to_runtime_minutes = minutes_between(created, runtime_observed_at)
            matched_pr_number = runtime_match.get("number")
            matched_merge_sha = runtime_build_sha
        else:
            measurement_gaps.append("runtime_observation_precedes_merge")

    if merged_prs and not merge_to_ci_times:
        measurement_gaps.append("merge_to_ci_evidence_missing")

    median_merge_minutes = round(median(merge_lead_times), 2) if merge_lead_times else None
    median_merge_to_ci = round(median(merge_to_ci_times), 2) if merge_to_ci_times else None
    target_met = None if merge_to_runtime_minutes is None else merge_to_runtime_minutes <= target_minutes

    return {
        "availability_target_minutes": target_minutes,
        "merge_lead_time": {
            "sample_count": len(merge_lead_times),
            "median_minutes": median_merge_minutes,
        },
        "merge_to_ci_green": {
            "sample_count": len(merge_to_ci_times),
            "median_minutes": median_merge_to_ci,
        },
        "sha_linked_runtime": {
            "matched_pr_number": matched_pr_number,
            "merge_commit_sha": matched_merge_sha,
            "runtime_build_sha": runtime_build_sha or None,
            "runtime_observed_at": runtime.get("observed_at"),
            "merge_to_runtime_observed_minutes": merge_to_runtime_minutes,
            "created_to_runtime_observed_minutes": created_to_runtime_minutes,
            "target_met": target_met,
            "measurement_semantics": "upper_bound_until_sha_linked_runtime_observation",
            "measurement_note": (
                "O intervalo termina na primeira observacao deste avaliador com o mesmo SHA e runtime saudavel; "
                "nao representa timestamp exato do deploy."
            ),
        },
        "wait_partition": {
            "technical_intervals_instrumented": True,
            "external_blocked_minutes": None,
            "external_wait_status": "not_instrumented",
        },
        "measurement_gaps": sorted(set(measurement_gaps)),
    }


def build_report(
    prs: list[dict[str, Any]],
    runs: list[dict[str, Any]],
    readiness: dict[str, Any],
    history: dict[str, Any],
    runtime: dict[str, Any] | None = None,
    merged_prs: list[dict[str, Any]] | None = None,
    availability_target_minutes: int = DEFAULT_AVAILABILITY_TARGET_MINUTES,
) -> dict[str, Any]:
    runtime = runtime or {}
    merged_prs = merged_prs or []
    now = datetime.now(timezone.utc)
    latest = latest_runs_by_name(runs)
    required = {name: latest.get(name) for name in sorted(REQUIRED_WORKFLOWS)}
    completed = [run for run in required.values() if run and run.get("status") == "completed"]
    successful = [run for run in completed if run.get("conclusion") == "success"]
    failed = [name for name, run in required.items() if run and run.get("status") == "completed" and run.get("conclusion") == "failure"]
    pending = [name for name, run in required.items() if not run or run.get("status") != "completed"]

    open_prs = [pr for pr in prs if pr.get("state") == "open"]
    mergeable_prs = [pr for pr in open_prs if pr.get("mergeable") is True]
    auto_merge_prs = [pr for pr in open_prs if pr.get("auto_merge_enabled") is True]
    queue_runs = [run for run in runs if run.get("name") == "Governed Merge Queue"]
    queue_active = any(run.get("status") in {"queued", "in_progress", "pending"} for run in queue_runs)

    metric_coverage = readiness.get("metric_coverage_percent")
    readiness_status = readiness.get("status") or "INSUFFICIENT_EVIDENCE"
    eta = history.get("eta") or history.get("milestones") or {}
    snapshots = history.get("snapshots") or history.get("history") or []
    history_points = len(snapshots)

    ci_stability = pct(len(successful), len(completed))
    parallel_throughput = pct(len(mergeable_prs), len(open_prs))

    endpoints = runtime.get("endpoints") or []
    smoke_total = len(endpoints)
    smoke_success = sum(1 for item in endpoints if item.get("ok") is True)
    smoke_success_percent = pct(smoke_success, smoke_total)
    latencies = [float(item["latency_ms"]) for item in endpoints if isinstance(item.get("latency_ms"), (int, float))]
    average_latency_ms = round(sum(latencies) / len(latencies), 2) if latencies else None
    runtime_healthy = smoke_total > 0 and smoke_success == smoke_total
    runtime["healthy"] = runtime_healthy

    merged_24h = 0
    merged_7d = 0
    lead_times: list[float] = []
    for pr in merged_prs:
        created = parse_dt(pr.get("created_at"))
        merged = parse_dt(pr.get("merged_at"))
        if not merged:
            continue
        age_hours = (now - merged).total_seconds() / 3600
        if age_hours <= 24:
            merged_24h += 1
        if age_hours <= 168:
            merged_7d += 1
        if created and merged >= created:
            lead_times.append((merged - created).total_seconds() / 3600)
    median_lead_time_hours = round(median(lead_times), 2) if lead_times else None
    delivery_velocity = build_delivery_velocity(
        merged_prs,
        runs,
        runtime,
        availability_target_minutes,
    )

    trend = history.get("trend")
    if trend is None and len(snapshots) >= 2:
        first = snapshots[0].get("operational_readiness_percent")
        last = snapshots[-1].get("operational_readiness_percent")
        if isinstance(first, (int, float)) and isinstance(last, (int, float)):
            trend = round(float(last) - float(first), 2)

    confidence_components = [value for value in (ci_stability, metric_coverage, smoke_success_percent) if isinstance(value, (int, float))]
    history_maturity = min(history_points / 5 * 100, 100) if history_points else None
    if history_maturity is not None:
        confidence_components.append(history_maturity)
    confidence_percent = round(sum(confidence_components) / len(confidence_components), 2) if confidence_components else None

    blockers: list[str] = []
    if failed:
        blockers.append("required_workflow_failure")
    if pending:
        blockers.append("required_workflows_pending_or_missing")
    if readiness_status in {"INSUFFICIENT_EVIDENCE", "EVIDENCE_INCOMPLETE"}:
        blockers.append("instrumented_readiness_incomplete")
    if smoke_total == 0:
        blockers.append("runtime_smoke_missing")
    elif not runtime_healthy:
        blockers.append("runtime_smoke_failure")
    if open_prs and not mergeable_prs:
        blockers.append("no_mergeable_open_pr")

    if failed:
        next_increment = "remediate_failed_required_workflows"
    elif pending:
        next_increment = "complete_required_workflows"
    elif smoke_total == 0 or not runtime_healthy:
        next_increment = "restore_runtime_and_smoke_evidence"
    elif readiness_status in {"INSUFFICIENT_EVIDENCE", "EVIDENCE_INCOMPLETE"}:
        next_increment = "complete_instrumented_evidence"
    elif history_points < 5:
        next_increment = "accumulate_instrumented_history"
    elif open_prs:
        next_increment = "governed_merge_of_eligible_prs"
    else:
        next_increment = "maintain_runtime_and_delivery_baseline"

    ready_for_human_decision = not blockers and readiness_status in {"READY", "CONSOLIDATING"}

    return {
        "schema_version": "1.2.0",
        "contract": "reqsys-next-increment-auto-evaluation",
        "generated_at": now.isoformat(),
        "mode": "report_only",
        "automatic_promotion_allowed": False,
        "automatic_merge_allowed": False,
        "human_approval_required": True,
        "status": "READY_FOR_HUMAN_DECISION" if ready_for_human_decision else "ACTION_REQUIRED",
        "implemented": True,
        "validated": not failed and not pending,
        "evidenced": bool(runs) and bool(readiness) and smoke_total > 0,
        "consolidated": readiness_status in {"READY", "CONSOLIDATING"} and history_points >= 5 and runtime_healthy,
        "production_ready": readiness_status == "READY" and runtime_healthy and not blockers,
        "merge_queue": {"active": queue_active, "latest_conclusion": (latest.get("Governed Merge Queue") or {}).get("conclusion")},
        "auto_merge": {"enabled_open_prs": len(auto_merge_prs), "eligible_mergeable_prs": len(mergeable_prs)},
        "ci": {
            "required_total": len(REQUIRED_WORKFLOWS),
            "completed_total": len(completed),
            "successful_total": len(successful),
            "stability_percent": ci_stability,
            "failed": failed,
            "pending_or_missing": pending,
        },
        "runtime": {
            "healthy": runtime_healthy,
            "smoke_total": smoke_total,
            "smoke_success": smoke_success,
            "smoke_success_percent": smoke_success_percent,
            "average_latency_ms": average_latency_ms,
            "build_sha": runtime.get("build_sha"),
            "observed_at": runtime.get("observed_at"),
            "environment": runtime.get("environment"),
            "endpoints": endpoints,
        },
        "integration": {
            "open_prs": len(open_prs),
            "mergeable_open_prs": len(mergeable_prs),
            "parallel_throughput_percent": parallel_throughput,
            "merged_prs_24h": merged_24h,
            "merged_prs_7d": merged_7d,
            "median_merge_lead_time_hours": median_lead_time_hours,
        },
        "delivery_velocity": delivery_velocity,
        "instrumented_metrics": {
            "readiness_status": readiness_status,
            "metric_coverage_percent": metric_coverage,
            "history_points": history_points,
            "history_maturity_percent": history_maturity,
            "trend_delta_percent": trend,
            "confidence_percent": confidence_percent,
            "eta": eta,
        },
        "human_blockers": blockers,
        "next_safe_increment": next_increment,
    }


def render_markdown(report: dict[str, Any]) -> str:
    ci = report["ci"]
    runtime = report["runtime"]
    integration = report["integration"]
    delivery = report["delivery_velocity"]
    metrics = report["instrumented_metrics"]
    linked = delivery["sha_linked_runtime"]
    gaps = delivery["measurement_gaps"]
    return "\n".join([
        "# Avaliação Automática do Próximo Incremento ReqSys",
        "",
        f"- Status: **{report['status']}**",
        f"- Próximo incremento seguro: **{report['next_safe_increment']}**",
        f"- Estabilidade CI: **{ci['stability_percent']}%**",
        f"- Smoke público: **{runtime['smoke_success']}/{runtime['smoke_total']} ({runtime['smoke_success_percent']}%)**",
        f"- Runtime build SHA: **{runtime['build_sha'] or 'não evidenciado'}**",
        f"- Latência média pública: **{runtime['average_latency_ms']} ms**",
        f"- PRs mergeadas 24h/7d: **{integration['merged_prs_24h']}/{integration['merged_prs_7d']}**",
        f"- PR criado → merge (mediana): **{delivery['merge_lead_time']['median_minutes']} min**",
        f"- Merge → CI verde (mediana): **{delivery['merge_to_ci_green']['median_minutes']} min**",
        f"- Merge → runtime observado no mesmo SHA: **{linked['merge_to_runtime_observed_minutes']} min**",
        f"- PR criado → runtime observado no mesmo SHA: **{linked['created_to_runtime_observed_minutes']} min**",
        f"- Alvo disponibilidade DEV sem gate externo: **≤ {delivery['availability_target_minutes']} min**",
        f"- Alvo observado: **{linked['target_met']}**",
        f"- Lacunas de medição: **{', '.join(gaps) or 'nenhuma'}**",
        f"- Throughput paralelo: **{integration['parallel_throughput_percent']}%**",
        f"- Confiança instrumentada: **{metrics['confidence_percent']}%**",
        f"- Tendência: **{metrics['trend_delta_percent']} p.p.**",
        f"- Pontos históricos: **{metrics['history_points']}**",
        f"- Bloqueios: **{', '.join(report['human_blockers']) or 'nenhum'}**",
        "- Modo: **report_only**",
        "",
    ])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prs", type=Path, required=True)
    parser.add_argument("--merged-prs", type=Path, required=True)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--readiness", type=Path, required=True)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--availability-target-minutes", type=int, default=DEFAULT_AVAILABILITY_TARGET_MINUTES)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    args = parser.parse_args()

    report = build_report(
        load_json(args.prs, []),
        load_json(args.runs, []),
        load_json(args.readiness, {}),
        load_json(args.history, {}),
        load_json(args.runtime, {}),
        load_json(args.merged_prs, []),
        args.availability_target_minutes,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.output_md.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"status": report["status"], "next": report["next_safe_increment"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
