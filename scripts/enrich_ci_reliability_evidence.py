#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

from build_ci_process_improvement_analytics import github_api

DEFAULT_ANALYTICS_PATH = Path("audit/ci-lead-time-analytics.json")
DEFAULT_MARKDOWN_PATH = Path("audit/ci-lead-time-analytics.md")
SECTION_MARKER = "## Evidência de confiabilidade do CI"
TERMINAL_CONCLUSIONS = {
    "success",
    "failure",
    "cancelled",
    "timed_out",
    "action_required",
    "startup_failure",
    "skipped",
    "neutral",
}


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


def _attempt_conclusions(
    owner: str,
    name: str,
    token: str,
    run: dict[str, Any],
    *,
    api_get: Callable[[str, str], Any],
) -> list[str]:
    run_id = int(run.get("id") or 0)
    attempt_count = int(run.get("run_attempt") or 1)
    if run_id <= 0:
        raise ValueError("workflow run sem id válido")
    if attempt_count < 1:
        raise ValueError(f"run_attempt inválido para run {run_id}")

    conclusions: list[str] = []
    for attempt in range(1, attempt_count + 1):
        payload = api_get(
            f"/repos/{owner}/{name}/actions/runs/{run_id}/attempts/{attempt}",
            token,
        )
        if not isinstance(payload, dict):
            raise RuntimeError(
                f"resposta inválida ao consultar tentativa {attempt} do run {run_id}"
            )
        conclusion = str(payload.get("conclusion") or "").strip()
        status = str(payload.get("status") or "").strip()
        if status != "completed" or conclusion not in TERMINAL_CONCLUSIONS:
            raise RuntimeError(
                f"tentativa não terminal/incompleta: run={run_id} attempt={attempt} "
                f"status={status!r} conclusion={conclusion!r}"
            )
        conclusions.append(conclusion)
    return conclusions


def _pickup_evidence(
    owner: str,
    name: str,
    token: str,
    run_id: int,
    *,
    api_get: Callable[[str, str], Any],
) -> dict[str, Any]:
    payload = api_get(
        f"/repos/{owner}/{name}/actions/runs/{run_id}/jobs?per_page=100",
        token,
    )
    if not isinstance(payload, dict):
        raise RuntimeError(f"resposta inválida ao listar jobs do run {run_id}")
    jobs = payload.get("jobs")
    if not isinstance(jobs, list):
        raise RuntimeError(f"jobs ausente/inválido no run {run_id}")
    total_count = int(payload.get("total_count") or len(jobs))
    if total_count != len(jobs):
        raise RuntimeError(
            f"coleta de jobs incompleta no run {run_id}: "
            f"total_count={total_count} coletados={len(jobs)}"
        )

    observed: list[dict[str, Any]] = []
    pickup_proven = False
    for job in jobs:
        if not isinstance(job, dict):
            continue
        runner_name = str(job.get("runner_name") or "").strip()
        started_at = str(job.get("started_at") or "").strip()
        job_id = int(job.get("id") or 0)
        if runner_name and started_at:
            pickup_proven = True
        observed.append(
            {
                "job_id": job_id,
                "name": str(job.get("name") or ""),
                "status": str(job.get("status") or ""),
                "conclusion": job.get("conclusion"),
                "runner_name": runner_name,
                "started_at": started_at,
            }
        )

    return {
        "pickup_proven": pickup_proven,
        "jobs": observed,
    }


def collect_reliability_baseline(
    analytics: dict[str, Any],
    *,
    owner: str,
    name: str,
    token: str,
    api_get: Callable[[str, str], Any] = github_api,
) -> dict[str, Any]:
    pr_efficiency = analytics.get("pr_efficiency")
    if not isinstance(pr_efficiency, dict):
        raise ValueError("pr_efficiency ausente; execute enrich_ci_pr_efficiency primeiro")

    rows = pr_efficiency.get("prs")
    if not isinstance(rows, list):
        raise ValueError("pr_efficiency.prs ausente ou inválido")

    blocking_workflows = [
        str(item).strip()
        for item in (pr_efficiency.get("blocking_workflows") or [])
        if str(item).strip()
    ]
    if not blocking_workflows:
        raise ValueError("pr_efficiency.blocking_workflows ausente ou vazio")

    pr_results: list[dict[str, Any]] = []
    sampled_runs = 0
    flaky_unresolved_runs = 0
    sha_divergent_prs = 0
    pickup_unproven_runs = 0

    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            pr_number = int(row["pr_number"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("pr_efficiency.prs contém pr_number inválido") from exc

        observed_head_sha = str(row.get("latest_head_sha") or "").strip()
        if not observed_head_sha:
            raise ValueError(f"PR #{pr_number} sem latest_head_sha")

        pr_payload = api_get(f"/repos/{owner}/{name}/pulls/{pr_number}", token)
        if not isinstance(pr_payload, dict):
            raise RuntimeError(f"resposta inválida ao consultar PR #{pr_number}")
        head_payload = pr_payload.get("head")
        if not isinstance(head_payload, dict):
            raise RuntimeError(f"PR #{pr_number} sem head válido")
        expected_head_sha = str(head_payload.get("sha") or "").strip()
        if not expected_head_sha:
            raise RuntimeError(f"PR #{pr_number} sem head.sha")

        sha_divergent = observed_head_sha != expected_head_sha
        sha_divergent_prs += int(sha_divergent)

        runs_payload = api_get(
            f"/repos/{owner}/{name}/actions/runs?"
            f"head_sha={observed_head_sha}&event=pull_request&per_page=100",
            token,
        )
        if not isinstance(runs_payload, dict):
            raise RuntimeError(f"resposta inválida ao listar runs do PR #{pr_number}")
        raw_runs = runs_payload.get("workflow_runs")
        if not isinstance(raw_runs, list):
            raise RuntimeError(f"workflow_runs inválido para PR #{pr_number}")

        completed = [
            item
            for item in raw_runs
            if isinstance(item, dict)
            and item.get("event") == "pull_request"
            and item.get("status") == "completed"
            and str(item.get("name") or "") in blocking_workflows
        ]
        latest = _latest_by_workflow(completed)

        run_results: list[dict[str, Any]] = []
        for workflow_name in blocking_workflows:
            run = latest.get(workflow_name)
            if run is None:
                continue
            run_id = int(run.get("id") or 0)
            attempt_conclusions = _attempt_conclusions(
                owner,
                name,
                token,
                run,
                api_get=api_get,
            )
            pickup = _pickup_evidence(
                owner,
                name,
                token,
                run_id,
                api_get=api_get,
            )
            flaky_unresolved = len(set(attempt_conclusions)) > 1
            pickup_unproven = not bool(pickup["pickup_proven"])
            flaky_unresolved_runs += int(flaky_unresolved)
            pickup_unproven_runs += int(pickup_unproven)
            sampled_runs += 1

            findings: list[str] = []
            if flaky_unresolved:
                findings.append("FLAKY_UNRESOLVED")
            if pickup_unproven:
                findings.append("PICKUP_UNPROVEN")

            run_results.append(
                {
                    "workflow": workflow_name,
                    "run_id": run_id,
                    "run_attempt": int(run.get("run_attempt") or 1),
                    "head_sha": str(run.get("head_sha") or ""),
                    "attempt_conclusions": attempt_conclusions,
                    "pickup_proven": bool(pickup["pickup_proven"]),
                    "jobs": pickup["jobs"],
                    "findings": findings,
                }
            )

        pr_findings: list[str] = []
        if sha_divergent:
            pr_findings.append("SHA_DIVERGENT")

        pr_results.append(
            {
                "pr_number": pr_number,
                "head_sha": observed_head_sha,
                "expected_head_sha": expected_head_sha,
                "findings": pr_findings,
                "runs": run_results,
            }
        )

    sample_valid = bool(pr_efficiency.get("baseline_sample_valid"))
    sampled_prs = len(pr_results)
    available = sampled_prs > 0 and sampled_runs > 0

    return {
        "contract": "ci-reliability-evidence.v1",
        "mode": "report-only",
        "creates_gate": False,
        "available": available,
        "baseline_sample_valid": sample_valid and available,
        "sampled_prs": sampled_prs,
        "sampled_runs": sampled_runs,
        "flaky_unresolved_runs": flaky_unresolved_runs,
        "sha_divergent_prs": sha_divergent_prs,
        "pickup_unproven_runs": pickup_unproven_runs,
        "semantics": {
            "FLAKY_UNRESOLVED": (
                "o mesmo workflow run_id apresentou conclusões terminais diferentes "
                "entre tentativas; rerun verde não apaga a instabilidade"
            ),
            "SHA_DIVERGENT": (
                "latest_head_sha da amostra difere do head.sha atual do PR"
            ),
            "PICKUP_UNPROVEN": (
                "nenhum job da tentativa observada possui runner_name e started_at "
                "na leitura independente da API de jobs"
            ),
        },
        "prs": pr_results,
    }


def render_markdown(metrics: dict[str, Any]) -> str:
    lines = [
        SECTION_MARKER,
        "",
        f"- Modo: {metrics['mode']}",
        f"- Cria gate: {'sim' if metrics['creates_gate'] else 'não'}",
        f"- Baseline amostral válida: {'sim' if metrics['baseline_sample_valid'] else 'não'}",
        f"- PRs amostrados: {metrics['sampled_prs']}",
        f"- Runs bloqueantes amostrados: {metrics['sampled_runs']}",
        f"- FLAKY_UNRESOLVED: {metrics['flaky_unresolved_runs']}",
        f"- SHA_DIVERGENT: {metrics['sha_divergent_prs']}",
        f"- PICKUP_UNPROVEN: {metrics['pickup_unproven_runs']}",
        "",
        "> Esta seção é observacional. Nenhum finding vira gate por este incremento.",
    ]
    return "\n".join(lines) + "\n"


def enrich_files(
    analytics_path: Path,
    markdown_path: Path,
    metrics: dict[str, Any],
) -> None:
    analytics = json.loads(analytics_path.read_text(encoding="utf-8"))
    analytics["ci_reliability_evidence"] = metrics
    analytics["schema_version"] = "1.0.6"
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
    analytics_path = Path(
        os.environ.get("CI_ANALYTICS_PATH", str(DEFAULT_ANALYTICS_PATH))
    )
    markdown_path = Path(
        os.environ.get("CI_ANALYTICS_MARKDOWN_PATH", str(DEFAULT_MARKDOWN_PATH))
    )

    analytics = json.loads(analytics_path.read_text(encoding="utf-8"))
    owner, name = repository.split("/", 1)
    metrics = collect_reliability_baseline(
        analytics,
        owner=owner,
        name=name,
        token=token,
    )
    enrich_files(analytics_path, markdown_path, metrics)
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
