#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from build_ci_fixed_window_analytics import fetch_runs_for_window
from build_ci_process_improvement_analytics import parse_dt, percentile

DEFAULT_ANALYTICS_PATH = Path("audit/ci-lead-time-analytics.json")
DEFAULT_MARKDOWN_PATH = Path("audit/ci-lead-time-analytics.md")
DEFAULT_REGISTRY_PATH = Path("config/workflow-governance-registry.json")
FAILED_CONCLUSIONS = {
    "failure",
    "cancelled",
    "timed_out",
    "action_required",
    "startup_failure",
}
SECTION_MARKER = "## Eficiência por Pull Request"


def load_blocking_workflows(path: Path = DEFAULT_REGISTRY_PATH) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    blocking = (payload.get("canonical_pr_path") or {}).get("blocking") or []
    names = [str(item).strip() for item in blocking if str(item).strip()]
    if not names:
        raise ValueError("canonical_pr_path.blocking ausente ou vazio")
    if len(names) != len(set(names)):
        raise ValueError("canonical_pr_path.blocking contém duplicidades")
    return names


def _run_seconds(run: dict[str, Any]) -> float:
    created_at = parse_dt(run.get("created_at"))
    updated_at = parse_dt(run.get("updated_at"))
    if created_at is None or updated_at is None:
        return 0.0
    return max(0.0, (updated_at - created_at).total_seconds())


def _pr_number(run: dict[str, Any]) -> int | None:
    pull_requests = run.get("pull_requests") or []
    if not pull_requests or not isinstance(pull_requests[0], dict):
        return None
    try:
        return int(pull_requests[0].get("number"))
    except (TypeError, ValueError):
        return None


def _latest_by_workflow(runs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for run in runs:
        name = str(run.get("name") or "")
        if not name:
            continue
        current = latest.get(name)
        key = (int(run.get("run_attempt") or 1), str(run.get("updated_at") or ""))
        current_key = (
            int(current.get("run_attempt") or 1),
            str(current.get("updated_at") or ""),
        ) if current else (-1, "")
        if current is None or key > current_key:
            latest[name] = run
    return latest


def build_pr_efficiency(
    raw_runs: list[dict[str, Any]],
    *,
    blocking_workflows: list[str],
    start_at: datetime,
    end_at: datetime,
) -> dict[str, Any]:
    blocking = list(dict.fromkeys(blocking_workflows))
    if not blocking:
        raise ValueError("blocking_workflows não pode ser vazio")

    grouped: dict[int, list[dict[str, Any]]] = {}
    workflow_seconds: dict[str, float] = {}

    for run in raw_runs:
        created_at = parse_dt(run.get("created_at"))
        if (
            run.get("event") != "pull_request"
            or run.get("status") != "completed"
            or created_at is None
            or not (start_at <= created_at < end_at)
        ):
            continue
        pr_number = _pr_number(run)
        if pr_number is None:
            continue
        grouped.setdefault(pr_number, []).append(run)
        workflow_name = str(run.get("name") or "")
        if workflow_name:
            workflow_seconds[workflow_name] = (
                workflow_seconds.get(workflow_name, 0.0) + _run_seconds(run)
            )

    pr_rows: list[dict[str, Any]] = []
    green_times: list[float] = []
    ci_minutes_per_pr: list[float] = []
    repair_count = 0

    for pr_number, runs in sorted(grouped.items()):
        by_sha: dict[str, list[dict[str, Any]]] = {}
        for run in runs:
            sha = str(run.get("head_sha") or "")
            if sha:
                by_sha.setdefault(sha, []).append(run)
        if not by_sha:
            continue

        latest_sha = max(
            by_sha,
            key=lambda sha: max(
                str(item.get("created_at") or "") for item in by_sha[sha]
            ),
        )
        latest_runs = _latest_by_workflow(by_sha[latest_sha])
        selected = {name: latest_runs.get(name) for name in blocking}
        blockers_complete = all(item is not None for item in selected.values())
        latest_head_green = blockers_complete and all(
            item.get("conclusion") == "success"
            for item in selected.values()
            if item is not None
        )

        time_to_green: float | None = None
        if latest_head_green:
            starts = [
                parse_dt(item.get("created_at"))
                for item in selected.values()
                if item is not None
            ]
            ends = [
                parse_dt(item.get("updated_at"))
                for item in selected.values()
                if item is not None
            ]
            valid_starts = [value for value in starts if value is not None]
            valid_ends = [value for value in ends if value is not None]
            if valid_starts and valid_ends:
                time_to_green = max(
                    0.0,
                    (max(valid_ends) - min(valid_starts)).total_seconds(),
                )
                green_times.append(time_to_green)

        observed_seconds = sum(_run_seconds(run) for run in runs)
        observed_minutes = round(observed_seconds / 60.0, 2)
        ci_minutes_per_pr.append(observed_minutes)

        earlier_failure = False
        for sha, sha_runs in by_sha.items():
            if sha == latest_sha:
                continue
            by_name = _latest_by_workflow(sha_runs)
            if any(
                by_name.get(name) is not None
                and by_name[name].get("conclusion") in FAILED_CONCLUSIONS
                for name in blocking
            ):
                earlier_failure = True
                break

        repair_proxy = latest_head_green and earlier_failure
        repair_count += int(repair_proxy)
        pr_rows.append(
            {
                "pr_number": pr_number,
                "distinct_heads": len(by_sha),
                "latest_head_sha": latest_sha,
                "observed_ci_run_minutes": observed_minutes,
                "latest_head_blockers_complete": blockers_complete,
                "latest_head_green": latest_head_green,
                "latest_head_time_to_green_seconds": (
                    round(time_to_green, 2) if time_to_green is not None else None
                ),
                "ci_fix_commit_proxy": repair_proxy,
            }
        )

    total_seconds = sum(workflow_seconds.values())
    pareto: list[dict[str, Any]] = []
    cumulative = 0.0
    for name, seconds in sorted(
        workflow_seconds.items(), key=lambda item: (-item[1], item[0])
    ):
        cumulative += seconds
        share = seconds / total_seconds * 100.0 if total_seconds else 0.0
        cumulative_share = cumulative / total_seconds * 100.0 if total_seconds else 0.0
        pareto.append(
            {
                "name": name,
                "minutes": round(seconds / 60.0, 2),
                "share_percent": round(share, 2),
                "cumulative_share_percent": round(min(100.0, cumulative_share), 2),
            }
        )

    names_to_80: list[str] = []
    for item in pareto:
        names_to_80.append(str(item["name"]))
        if float(item["cumulative_share_percent"]) >= 80.0:
            break

    sample_prs = len(pr_rows)
    green_prs = sum(1 for row in pr_rows if row["latest_head_green"])
    return {
        "available": sample_prs > 0,
        "mode": "report-only",
        "creates_gate": False,
        "sample_prs": sample_prs,
        "green_sample_prs": green_prs,
        "incomplete_or_non_green_sample_prs": sample_prs - green_prs,
        "total_observed_ci_run_minutes": round(sum(ci_minutes_per_pr), 2),
        "avg_observed_ci_run_minutes_per_pr": (
            round(sum(ci_minutes_per_pr) / sample_prs, 2) if sample_prs else 0.0
        ),
        "p50_observed_ci_run_minutes_per_pr": (
            round(percentile(ci_minutes_per_pr, 0.50), 2)
            if ci_minutes_per_pr
            else 0.0
        ),
        "p90_observed_ci_run_minutes_per_pr": (
            round(percentile(ci_minutes_per_pr, 0.90), 2)
            if ci_minutes_per_pr
            else 0.0
        ),
        "p50_latest_head_time_to_green_seconds": (
            round(percentile(green_times, 0.50), 2) if green_times else 0.0
        ),
        "p90_latest_head_time_to_green_seconds": (
            round(percentile(green_times, 0.90), 2) if green_times else 0.0
        ),
        "ci_fix_commit_proxy_prs": repair_count,
        "ci_fix_commit_proxy_percent": (
            round(repair_count / sample_prs * 100.0, 2) if sample_prs else 0.0
        ),
        "workflow_minutes_pareto": pareto,
        "workflows_to_80_percent": {
            "count": len(names_to_80),
            "names": names_to_80,
        },
        "blocking_workflows": blocking,
        "semantics": {
            "ci_minutes": (
                "soma do wall-clock dos workflow runs observados; "
                "não representa minutos faturados pelo GitHub"
            ),
            "time_to_green": (
                "intervalo do primeiro início ao último término dos workflows "
                "bloqueantes no HEAD mais recente do PR"
            ),
            "ci_fix_commit_proxy": (
                "HEAD anterior com workflow bloqueante falho seguido por HEAD mais "
                "recente integralmente verde; não prova causalidade do commit"
            ),
        },
        "prs": pr_rows,
    }


def render_markdown(metrics: dict[str, Any]) -> str:
    lines = [
        SECTION_MARKER,
        "",
        f"- Modo: `{metrics['mode']}`",
        f"- PRs observadas: `{metrics['sample_prs']}`",
        f"- PRs com HEAD mais recente verde: `{metrics['green_sample_prs']}`",
        (
            "- Minutos de CI observados: "
            f"`{metrics['total_observed_ci_run_minutes']}`"
        ),
        (
            "- Média de minutos observados por PR: "
            f"`{metrics['avg_observed_ci_run_minutes_per_pr']}`"
        ),
        (
            "- P50 de minutos observados por PR: "
            f"`{metrics['p50_observed_ci_run_minutes_per_pr']}`"
        ),
        (
            "- P90 de minutos observados por PR: "
            f"`{metrics['p90_observed_ci_run_minutes_per_pr']}`"
        ),
        (
            "- P50 do HEAD mais recente até verde: "
            f"`{metrics['p50_latest_head_time_to_green_seconds']}s`"
        ),
        (
            "- P90 do HEAD mais recente até verde: "
            f"`{metrics['p90_latest_head_time_to_green_seconds']}s`"
        ),
        (
            "- PRs com proxy de commit corretivo de CI: "
            f"`{metrics['ci_fix_commit_proxy_percent']}%`"
        ),
        (
            "- Workflows necessários para 80% dos minutos observados: "
            f"`{metrics['workflows_to_80_percent']['count']}`"
        ),
        "",
        "### Pareto de minutos observados",
    ]
    pareto = metrics.get("workflow_minutes_pareto") or []
    if pareto:
        lines.extend(
            (
                f"- {item['name']}: {item['minutes']} min, "
                f"{item['share_percent']}%, acumulado "
                f"{item['cumulative_share_percent']}%"
            )
            for item in pareto[:15]
        )
    else:
        lines.append("- Sem workflow de pull request na janela.")
    lines.extend(
        [
            "",
            "> Minutos são wall-clock observado de workflow runs, não minutos faturados.",
            "> O proxy de commit corretivo é observacional e não prova causalidade.",
        ]
    )
    return "\n".join(lines) + "\n"


def enrich_files(
    analytics_path: Path,
    markdown_path: Path,
    metrics: dict[str, Any],
) -> None:
    analytics = json.loads(analytics_path.read_text(encoding="utf-8"))
    analytics["pr_efficiency"] = metrics
    analytics_path.write_text(
        json.dumps(analytics, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    existing = markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else ""
    if SECTION_MARKER in existing:
        existing = existing.split(SECTION_MARKER, 1)[0].rstrip() + "\n\n"
    elif existing and not existing.endswith("\n\n"):
        existing = existing.rstrip() + "\n\n"
    markdown_path.write_text(existing + render_markdown(metrics), encoding="utf-8")


def main() -> int:
    repository = os.environ["REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]
    analytics_path = Path(os.environ.get("CI_ANALYTICS_PATH", DEFAULT_ANALYTICS_PATH))
    markdown_path = Path(os.environ.get("CI_ANALYTICS_MARKDOWN_PATH", DEFAULT_MARKDOWN_PATH))
    registry_path = Path(os.environ.get("WORKFLOW_GOVERNANCE_REGISTRY", DEFAULT_REGISTRY_PATH))

    analytics = json.loads(analytics_path.read_text(encoding="utf-8"))
    window = analytics.get("collection_window") or {}
    start_at = parse_dt(window.get("start_at"))
    end_at = parse_dt(window.get("end_at"))
    if start_at is None or end_at is None or end_at <= start_at:
        raise ValueError("collection_window inválida no artifact de analytics")

    owner, name = repository.split("/", 1)
    raw_runs, meta = fetch_runs_for_window(
        owner,
        name,
        token,
        start_at=start_at,
        max_pages=max(1, int(os.environ.get("MAX_FETCH_PAGES", "20"))),
    )
    if not meta.get("collection_complete"):
        raise RuntimeError("coleta de workflow runs incompleta para a janela fixa")

    metrics = build_pr_efficiency(
        raw_runs,
        blocking_workflows=load_blocking_workflows(registry_path),
        start_at=start_at,
        end_at=end_at,
    )
    enrich_files(analytics_path, markdown_path, metrics)
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
