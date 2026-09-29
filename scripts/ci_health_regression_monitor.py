#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from build_ci_process_improvement_analytics import github_api, parse_dt

FAILED_CONCLUSIONS = {"failure", "timed_out", "action_required", "startup_failure"}
POST_MERGE_FAILURE_CONCLUSIONS = {"failure", "timed_out", "action_required", "startup_failure"}
MARKER = "<!-- reqsys-ci-health-regression-watch -->"
DEFAULT_LOOKBACK_DAYS = 14
DEFAULT_MAX_RUN_PAGES = 100
DEFAULT_MAX_PULL_PAGES = 10
SHA_DIVERGENCE_GRACE_MINUTES = 30


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _pr_number(run: dict[str, Any]) -> int | None:
    pulls = run.get("pull_requests") or []
    if not pulls or not isinstance(pulls[0], dict):
        return None
    try:
        return int(pulls[0].get("number"))
    except (TypeError, ValueError):
        return None


def _pull_number(pull: dict[str, Any]) -> int | None:
    try:
        return int(pull.get("number"))
    except (TypeError, ValueError):
        return None


def _latest_by_workflow(runs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for run in runs:
        name = str(run.get("name") or "").strip()
        if not name:
            continue
        key = (
            int(run.get("run_attempt") or 1),
            str(run.get("updated_at") or ""),
            int(run.get("id") or 0),
        )
        current = latest.get(name)
        current_key = (
            int(current.get("run_attempt") or 1),
            str(current.get("updated_at") or ""),
            int(current.get("id") or 0),
        ) if current else (-1, "", -1)
        if current is None or key > current_key:
            latest[name] = run
    return latest


def _head_green(runs: list[dict[str, Any]], blocking: list[str]) -> bool:
    by_name = _latest_by_workflow(runs)
    return bool(blocking) and all(
        by_name.get(name) is not None
        and by_name[name].get("status") == "completed"
        and by_name[name].get("conclusion") == "success"
        for name in blocking
    )


def load_blocking_workflows(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    blocking = (payload.get("canonical_pr_path") or {}).get("blocking") or []
    result = [str(item).strip() for item in blocking if str(item).strip()]
    if not result:
        raise ValueError("canonical_pr_path.blocking ausente ou vazio")
    if len(result) != len(set(result)):
        raise ValueError("canonical_pr_path.blocking contém duplicidades")
    return result


def fetch_runs(
    owner: str,
    name: str,
    token: str,
    *,
    cutoff: datetime,
    max_pages: int = DEFAULT_MAX_RUN_PAGES,
    api_get: Callable[[str, str], Any] = github_api,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    complete = False
    pages = 0
    for page in range(1, max(1, max_pages) + 1):
        payload = api_get(f"/repos/{owner}/{name}/actions/runs?per_page=100&page={page}", token)
        if not isinstance(payload, dict):
            raise RuntimeError("resposta inválida ao listar workflow runs")
        batch = payload.get("workflow_runs") or []
        if not isinstance(batch, list):
            raise RuntimeError("workflow_runs inválido")
        pages = page
        if not batch:
            complete = True
            break
        rows.extend(item for item in batch if isinstance(item, dict))
        created = [parse_dt(item.get("created_at")) for item in batch if isinstance(item, dict)]
        valid = [item for item in created if item is not None]
        if len(batch) < 100 or (valid and min(valid) < cutoff):
            complete = True
            break
    filtered = []
    for run in rows:
        created = parse_dt(run.get("created_at"))
        updated = parse_dt(run.get("updated_at"))
        anchor = updated or created
        if anchor is not None and anchor >= cutoff:
            filtered.append(run)
    return filtered, {
        "collection_complete": complete,
        "pages": pages,
        "runs": len(filtered),
        "max_pages": max_pages,
    }


def fetch_pulls(
    owner: str,
    name: str,
    token: str,
    *,
    cutoff: datetime,
    max_pages: int = DEFAULT_MAX_PULL_PAGES,
    api_get: Callable[[str, str], Any] = github_api,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    complete = False
    pages = 0
    for page in range(1, max(1, max_pages) + 1):
        batch = api_get(
            f"/repos/{owner}/{name}/pulls?state=all&sort=updated&direction=desc&per_page=100&page={page}",
            token,
        )
        if not isinstance(batch, list):
            raise RuntimeError("resposta inválida ao listar pull requests")
        pages = page
        if not batch:
            complete = True
            break
        rows.extend(item for item in batch if isinstance(item, dict))
        updated = [parse_dt(item.get("updated_at")) for item in batch if isinstance(item, dict)]
        valid = [item for item in updated if item is not None]
        if len(batch) < 100 or (valid and min(valid) < cutoff):
            complete = True
            break
    filtered = [
        item
        for item in rows
        if (parse_dt(item.get("updated_at")) or datetime.min.replace(tzinfo=timezone.utc)) >= cutoff
    ]
    return filtered, {
        "collection_complete": complete,
        "pages": pages,
        "pulls": len(filtered),
        "max_pages": max_pages,
    }


def _period(ts: datetime, midpoint: datetime) -> str:
    return "current" if ts >= midpoint else "baseline"


def _median(values: list[float]) -> float:
    return round(float(statistics.median(values)), 2) if values else 0.0


def _rate(numerator: int, denominator: int) -> float:
    return round((numerator / denominator) * 100.0, 2) if denominator else 0.0


def _run_evidence(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": run.get("id"),
        "workflow": run.get("name"),
        "url": run.get("html_url"),
        "head_sha": run.get("head_sha"),
        "run_attempt": int(run.get("run_attempt") or 1),
        "conclusion": run.get("conclusion"),
        "updated_at": run.get("updated_at"),
    }


def analyze(
    runs: list[dict[str, Any]],
    pulls: list[dict[str, Any]],
    *,
    blocking_workflows: list[str],
    now: datetime,
    source_sha: str,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> dict[str, Any]:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    cutoff = now - timedelta(days=lookback_days)
    midpoint = now - timedelta(days=lookback_days / 2)

    pr_runs: list[dict[str, Any]] = []
    by_pr_sha: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for run in runs:
        if run.get("event") != "pull_request" or run.get("status") != "completed":
            continue
        pr = _pr_number(run)
        sha = str(run.get("head_sha") or "").strip()
        updated = parse_dt(run.get("updated_at")) or parse_dt(run.get("created_at"))
        if pr is None or not sha or updated is None or updated < cutoff:
            continue
        pr_runs.append(run)
        by_pr_sha.setdefault((pr, sha), []).append(run)

    ttff = {"baseline": [], "current": []}
    ttff_evidence: list[dict[str, Any]] = []
    for (pr, sha), cohort in by_pr_sha.items():
        relevant = [run for run in cohort if str(run.get("name") or "") in blocking_workflows]
        if not relevant:
            continue
        created = [parse_dt(run.get("created_at")) for run in relevant]
        valid_created = [item for item in created if item is not None]
        failures = [
            run
            for run in relevant
            if run.get("conclusion") in FAILED_CONCLUSIONS
            and parse_dt(run.get("updated_at")) is not None
        ]
        if not valid_created or not failures:
            continue
        first_failure = min(failures, key=lambda item: parse_dt(item.get("updated_at")) or now)
        failure_at = parse_dt(first_failure.get("updated_at"))
        if failure_at is None or failure_at < cutoff:
            continue
        seconds = max(0.0, (failure_at - min(valid_created)).total_seconds())
        bucket = _period(failure_at, midpoint)
        ttff[bucket].append(seconds)
        if bucket == "current":
            ttff_evidence.append(
                {
                    "pr_number": pr,
                    "head_sha": sha,
                    "seconds": round(seconds, 2),
                    "failure": _run_evidence(first_failure),
                }
            )

    rerun = {
        "baseline_total": 0,
        "baseline_reruns": 0,
        "current_total": 0,
        "current_reruns": 0,
    }
    rerun_evidence: list[dict[str, Any]] = []
    for run in pr_runs:
        observed_at = parse_dt(run.get("updated_at")) or parse_dt(run.get("created_at"))
        if observed_at is None:
            continue
        bucket = _period(observed_at, midpoint)
        rerun[f"{bucket}_total"] += 1
        if int(run.get("run_attempt") or 1) > 1:
            rerun[f"{bucket}_reruns"] += 1
            if bucket == "current":
                rerun_evidence.append(_run_evidence(run))

    pull_by_number = {
        number: pull for pull in pulls if (number := _pull_number(pull)) is not None
    }

    false_green = {"baseline": [], "current": []}
    for pr, pull in pull_by_number.items():
        merged_at = parse_dt(pull.get("merged_at"))
        merge_sha = str(pull.get("merge_commit_sha") or "").strip()
        head = pull.get("head") if isinstance(pull.get("head"), dict) else {}
        head_sha = str((head or {}).get("sha") or "").strip()
        if (
            merged_at is None
            or merged_at < cutoff
            or not merge_sha
            or not head_sha
            or not _head_green(by_pr_sha.get((pr, head_sha), []), blocking_workflows)
        ):
            continue
        failing_post = [
            run
            for run in runs
            if run.get("event") == "push"
            and str(run.get("head_sha") or "") == merge_sha
            and run.get("status") == "completed"
            and run.get("conclusion") in POST_MERGE_FAILURE_CONCLUSIONS
        ]
        if not failing_post:
            continue
        bucket = _period(merged_at, midpoint)
        false_green[bucket].append(
            {
                "pr_number": pr,
                "head_sha": head_sha,
                "merge_sha": merge_sha,
                "merged_at": _iso(merged_at),
                "failed_runs": [_run_evidence(item) for item in failing_post[:5]],
            }
        )

    divergences: list[dict[str, Any]] = []
    for pr, pull in pull_by_number.items():
        if str(pull.get("state") or "").lower() != "open":
            continue
        updated_at = parse_dt(pull.get("updated_at"))
        if updated_at is None or updated_at < cutoff:
            continue
        if now - updated_at < timedelta(minutes=SHA_DIVERGENCE_GRACE_MINUTES):
            continue
        head = pull.get("head") if isinstance(pull.get("head"), dict) else {}
        current_sha = str((head or {}).get("sha") or "").strip()
        if not current_sha:
            continue
        current_all_runs = [
            run
            for run in runs
            if run.get("event") == "pull_request"
            and _pr_number(run) == pr
            and str(run.get("head_sha") or "") == current_sha
        ]
        if any(
            str(run.get("status") or "") in {"queued", "in_progress", "pending", "waiting", "requested"}
            for run in current_all_runs
        ):
            continue
        current_runs = by_pr_sha.get((pr, current_sha), [])
        if _head_green(current_runs, blocking_workflows):
            continue

        stale: list[tuple[datetime, str, list[dict[str, Any]]]] = []
        for (candidate_pr, candidate_sha), cohort in by_pr_sha.items():
            if candidate_pr != pr or candidate_sha == current_sha:
                continue
            if not _head_green(cohort, blocking_workflows):
                continue
            times = [parse_dt(run.get("updated_at")) for run in cohort]
            valid = [item for item in times if item is not None]
            if valid:
                stale.append((max(valid), candidate_sha, cohort))
        if not stale:
            continue
        stale.sort(reverse=True, key=lambda item: item[0])
        _, stale_sha, stale_runs = stale[0]
        divergences.append(
            {
                "pr_number": pr,
                "current_head_sha": current_sha,
                "stale_green_head_sha": stale_sha,
                "updated_at": _iso(updated_at),
                "stale_green_runs": [
                    _run_evidence(item)
                    for item in _latest_by_workflow(stale_runs).values()
                    if str(item.get("name") or "") in blocking_workflows
                ][:5],
            }
        )

    baseline_ttff = _median(ttff["baseline"])
    current_ttff = _median(ttff["current"])
    baseline_rerun_rate = _rate(rerun["baseline_reruns"], rerun["baseline_total"])
    current_rerun_rate = _rate(rerun["current_reruns"], rerun["current_total"])
    alerts: list[dict[str, Any]] = []

    if (
        len(ttff["baseline"]) >= 3
        and len(ttff["current"]) >= 3
        and current_ttff - baseline_ttff >= 120
        and current_ttff >= baseline_ttff * 1.25
    ):
        alerts.append(
            {
                "metric": "time_to_first_failure",
                "trend": {
                    "baseline_p50_seconds": baseline_ttff,
                    "current_p50_seconds": current_ttff,
                    "delta_seconds": round(current_ttff - baseline_ttff, 2),
                    "baseline_samples": len(ttff["baseline"]),
                    "current_samples": len(ttff["current"]),
                },
                "evidence": sorted(
                    ttff_evidence, key=lambda item: float(item["seconds"]), reverse=True
                )[:5],
                "impact": "Feedback de falha está chegando mais tarde, aumentando tempo perdido antes da correção.",
                "risk": "médio",
                "correction": "Priorizar o primeiro gate bloqueante e fail-fast no caminho canônico, sem aumentar retries; revalidar o HEAD exato.",
            }
        )

    rerun_delta = round(current_rerun_rate - baseline_rerun_rate, 2)
    rerun_relative = (
        ((current_rerun_rate / baseline_rerun_rate) - 1.0) * 100.0
        if baseline_rerun_rate > 0
        else (100.0 if current_rerun_rate >= 5.0 else 0.0)
    )
    if (
        rerun["baseline_total"] >= 20
        and rerun["current_total"] >= 20
        and rerun_delta >= 5.0
        and rerun_relative >= 25.0
    ):
        alerts.append(
            {
                "metric": "reruns_without_change",
                "trend": {
                    "baseline_rate_percent": baseline_rerun_rate,
                    "current_rate_percent": current_rerun_rate,
                    "delta_percentage_points": rerun_delta,
                    "relative_change_percent": round(rerun_relative, 2),
                    "baseline_runs": rerun["baseline_total"],
                    "current_runs": rerun["current_total"],
                },
                "evidence": rerun_evidence[:10],
                "impact": "Reexecuções no mesmo workflow/SHA consomem capacidade sem mudança de código e aumentam fila.",
                "risk": "médio",
                "correction": "Corrigir a causa determinística ou flakiness do workflow e manter retries limitados/idempotentes, em vez de reexecutar sem mudança.",
            }
        )

    if false_green["current"]:
        alerts.append(
            {
                "metric": "post_merge_false_green",
                "trend": {
                    "previous_7d_count": len(false_green["baseline"]),
                    "current_7d_count": len(false_green["current"]),
                },
                "evidence": false_green["current"][:10],
                "impact": "Um HEAD verde antes do merge produziu falha no merge SHA, invalidando a evidência de entrega.",
                "risk": "alto",
                "correction": "Exigir validação pós-merge bloqueante no merge SHA exato e falhar fechado quando a evidência do SHA corrente não existir.",
            }
        )

    if divergences:
        alerts.append(
            {
                "metric": "sha_divergence",
                "trend": {
                    "current_open_prs_with_stale_green_evidence": len(divergences),
                },
                "evidence": divergences[:10],
                "impact": "Há PR aberto cujo HEAD atual não possui o conjunto verde observado em um SHA anterior.",
                "risk": "alto",
                "correction": "Invalidar evidência anterior em qualquer mudança de HEAD e exigir checks obrigatórios vinculados ao current_head_sha antes de decisão ou merge.",
            }
        )

    active_metrics = sorted(str(item["metric"]) for item in alerts)
    return {
        "schema_version": "1",
        "generated_at": _iso(now),
        "source_sha": source_sha,
        "window": {
            "lookback_days": lookback_days,
            "start_at": _iso(cutoff),
            "midpoint_at": _iso(midpoint),
            "end_at": _iso(now),
            "comparison": "previous_7d_vs_current_7d",
        },
        "blocking_workflows": blocking_workflows,
        "metrics": {
            "time_to_first_failure": {
                "baseline_p50_seconds": baseline_ttff,
                "current_p50_seconds": current_ttff,
                "baseline_samples": len(ttff["baseline"]),
                "current_samples": len(ttff["current"]),
            },
            "reruns_without_change": {
                "baseline_rate_percent": baseline_rerun_rate,
                "current_rate_percent": current_rerun_rate,
                **rerun,
            },
            "post_merge_false_green": {
                "baseline_count": len(false_green["baseline"]),
                "current_count": len(false_green["current"]),
            },
            "sha_divergence": {"current_count": len(divergences)},
        },
        "material_regression": bool(alerts),
        "active_metrics": active_metrics,
        "alerts": alerts,
    }


def render_markdown(report: dict[str, Any]) -> str:
    active = ",".join(report.get("active_metrics") or [])
    lines = [
        MARKER,
        f"<!-- active_metrics:{active} -->",
        "# CI/CD ReqSys — regressão material",
        "",
        f"- Observado em: {report['generated_at']}",
        f"- Monitor SHA: {report['source_sha']}",
        f"- Janela: {report['window']['start_at']} -> {report['window']['end_at']}",
        "- Comparação: 7 dias anteriores x 7 dias recentes dentro da janela móvel de 14 dias.",
        "",
    ]
    if not report.get("alerts"):
        lines.extend(["Nenhuma regressão material ativa.", ""])
        return "\n".join(lines)

    for alert in report["alerts"]:
        lines.extend(
            [
                f"## {alert['metric']}",
                "",
                f"- Tendência: {json.dumps(alert['trend'], ensure_ascii=False, sort_keys=True)}",
                f"- Impacto: {alert['impact']}",
                f"- Risco: **{alert['risk']}**",
                f"- Menor correção sistêmica: {alert['correction']}",
                "",
                "### Evidência atual",
                "~~~json",
                json.dumps(alert["evidence"], ensure_ascii=False, indent=2, sort_keys=True),
                "~~~",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> int:
    repository = os.environ["REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]
    source_sha = os.environ.get("EVALUATED_SHA") or os.environ.get("GITHUB_SHA", "")
    if len(source_sha) != 40:
        raise SystemExit("GITHUB_SHA_INVALID")
    owner, name = repository.split("/", 1)
    now = datetime.now(timezone.utc)
    lookback_days = max(2, int(os.environ.get("LOOKBACK_DAYS", str(DEFAULT_LOOKBACK_DAYS))))
    cutoff = now - timedelta(days=lookback_days)

    blocking = load_blocking_workflows(Path("config/workflow-governance-registry.json"))
    runs, runs_meta = fetch_runs(owner, name, token, cutoff=cutoff)
    pulls, pulls_meta = fetch_pulls(owner, name, token, cutoff=cutoff)
    if not runs_meta["collection_complete"]:
        raise SystemExit("CI_HEALTH_RUN_COLLECTION_INCOMPLETE")
    if not pulls_meta["collection_complete"]:
        raise SystemExit("CI_HEALTH_PULL_COLLECTION_INCOMPLETE")

    report = analyze(
        runs,
        pulls,
        blocking_workflows=blocking,
        now=now,
        source_sha=source_sha,
        lookback_days=lookback_days,
    )
    report["collection"] = {
        "workflow_runs": runs_meta,
        "pull_requests": pulls_meta,
    }

    out_dir = Path("audit/ci-health-regression-watch")
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "report.json"
    md_path = out_dir / "report.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_markdown(report), encoding="utf-8")

    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with Path(output).open("a", encoding="utf-8") as handle:
            handle.write(
                "material_regression="
                + ("true" if report["material_regression"] else "false")
                + "\n"
            )
            handle.write("active_metrics=" + ",".join(report["active_metrics"]) + "\n")

    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
