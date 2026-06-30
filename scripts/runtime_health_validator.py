#!/usr/bin/env python3
"""Runtime Health Validator for ReqSys operational governance.

Detecta estado operacional a partir dos runs recentes de GitHub Actions e gera
plano de remediacao governado sem executar mudancas por padrao.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.auto_rerun_governed import MAX_RERUN_ATTEMPTS, is_blocklisted

MATURITY_LEVELS = {
    "green": "managed",
    "yellow": "defined",
    "red": "reactive",
}

ENVIRONMENT_ENDPOINTS = {
    "dev": "https://reqsys-api-dev.fly.dev/health",
    "homolog": "https://reqsys-api-stg.fly.dev/health",
    "prod": "https://reqsys-api.fly.dev/health",
}

HEALTH_MATRIX_WEIGHTS = {
    "ci_github": 0.30,
    "fly_dev": 0.10,
    "fly_homolog": 0.10,
    "fly_prod": 0.15,
    "evidence_gate": 0.20,
    "security_gates": 0.15,
}

STATUS_SCORE = {
    "green": 100,
    "yellow": 70,
    "red": 20,
    "pending": 50,
    "unknown": 40,
    "declared": 85,
    "passed": 100,
    "warning": 70,
    "failed": 20,
    "missing": 30,
}

RETRY_COOLDOWN_MINUTES = 30

ALLOWLISTED_REMEDIATION_WORKFLOWS = {
    "Actions Auto Operator",
    "Operational Governance Orchestrator",
    "Main Post-Merge Validation",
    "PR CI Watch",
    "PR Conflict Guard",
    "Branch Protection Audit",
    "Fast CI - Operational Guardrails",
}

# Workflows com cancel-in-progress governado — cancelled indica supersessão, não gap.
CONCURRENCY_MESH_SUPPRESSED_WORKFLOWS = frozenset(
    {
        "Operational Runtime Mesh Hub",
        "Unified Operational Event Bus",
        "Operational Alert Intelligence",
        "Workflow Reliability Analytics",
        "Operational Data Lake & Historical Intelligence",
        "Operational Executive Dashboard Generator",
        "Governed Auto Remediation Engine",
        "Operational Stability Score",
        "CI Incident Intelligence",
    }
)

EVIDENCE_GATE_WORKFLOW_NAMES = {
    "PR Evidence Gate",
    "PR Governed CI Validation",
}

TRANSIENT_CONCLUSIONS = {"cancelled", "timed_out", "action_required"}
HARD_FAILURE_CONCLUSIONS = {"failure"}
SECURITY_KEYWORDS = ("security", "secret", "token", "permission", "branch protection", "governance")

DEFAULT_CACHED_ARTIFACT = Path("artifacts/runtime-health-validator/runtime-health-validator.json")
EVIDENCE_GATE_ARTIFACT = Path("artifacts/pr-evidence-gate/pr-evidence-gate.json")


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
    run_attempt: int = 1

    @property
    def health(self) -> str:
        if self.status != "completed":
            return "pending"
        if self.conclusion == "success":
            return "green"
        if self.conclusion in TRANSIENT_CONCLUSIONS:
            return "yellow"
        if self.conclusion in HARD_FAILURE_CONCLUSIONS:
            return "red"
        return "unknown"

    @property
    def severity(self) -> str:
        lowered = self.name.lower()
        if self.health == "red" and any(keyword in lowered for keyword in SECURITY_KEYWORDS):
            return "critical"
        if self.health == "red":
            return "high"
        if self.health == "yellow":
            return "medium"
        if self.health == "pending":
            return "low"
        return "none"


def github_request(method: str, url: str, token: str, payload: dict[str, Any] | None = None) -> Any:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - GitHub API URL is controlled.
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API error {exc.code} for {method} {url}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"GitHub API connection error for {method} {url}: {exc}") from exc


def repo_api(repo: str, path: str) -> str:
    return f"https://api.github.com/repos/{repo}/{path.lstrip('/')}"


def fetch_recent_runs(repo: str, token: str, branch: str, limit: int) -> list[WorkflowRun]:
    data = github_request("GET", repo_api(repo, f"actions/runs?branch={branch}&per_page={limit}"), token)
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
            run_attempt=int(item.get("run_attempt") or 1),
        )
        for item in data.get("workflow_runs", [])
    ]


def load_cached_report(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def load_local_artifact(path: Path) -> dict[str, Any] | None:
    return load_cached_report(path)


def probe_health_endpoint(url: str, timeout: int = 8) -> tuple[str, str]:
    request = Request(url, method="GET", headers={"User-Agent": "ReqSys-Runtime-Health-Validator/1.2"})
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - controlled Fly.io health URL.
            if 200 <= response.status < 300:
                return "green", "live"
            return "yellow", "live"
    except (HTTPError, URLError, TimeoutError):
        return "red", "live"


def ci_github_status(runs: list[WorkflowRun]) -> str:
    if any(run.health == "red" for run in runs):
        return "red"
    if any(run.health in {"yellow", "pending"} for run in runs):
        return "yellow"
    if runs:
        return "green"
    return "unknown"


def evidence_gate_status(runs: list[WorkflowRun], artifact_root: Path) -> tuple[str, str]:
    gate_runs = [run for run in runs if run.name in EVIDENCE_GATE_WORKFLOW_NAMES]
    if gate_runs:
        worst = max(gate_runs, key=lambda run: {"green": 0, "yellow": 1, "pending": 2, "red": 3, "unknown": 1}.get(run.health, 1))
        return worst.health, "live"

    artifact = load_local_artifact(artifact_root / EVIDENCE_GATE_ARTIFACT)
    if artifact:
        status = str(artifact.get("status") or artifact.get("gate", {}).get("status") or "unknown")
        normalized = {
            "passed": "green",
            "success": "green",
            "warning": "yellow",
            "failed": "red",
            "failure": "red",
        }.get(status.lower(), status)
        return normalized if normalized in STATUS_SCORE else "unknown", "artifact"

    return "unknown", "fallback"


def security_gates_status(runs: list[WorkflowRun]) -> str:
    security_runs = [
        run for run in runs if any(keyword in run.name.lower() for keyword in SECURITY_KEYWORDS)
    ]
    if not security_runs:
        return "green"
    if any(run.health == "red" for run in security_runs):
        return "red"
    if any(run.health in {"yellow", "pending"} for run in security_runs):
        return "yellow"
    return "green"


def build_health_matrix(
    runs: list[WorkflowRun],
    *,
    probe_env: bool,
    artifact_root: Path,
) -> list[dict[str, Any]]:
    matrix: list[dict[str, Any]] = []

    ci_status = ci_github_status(runs)
    matrix.append({
        "id": "ci_github",
        "label": "CI GitHub Actions",
        "status": ci_status,
        "score": STATUS_SCORE.get(ci_status, 40),
        "source": "live" if runs else "fallback",
        "detail": f"{sum(1 for run in runs if run.health == 'green')} verde(s) de {len(runs)} runs",
    })

    for env, endpoint in ENVIRONMENT_ENDPOINTS.items():
        row_id = f"fly_{env}"
        if probe_env:
            status, source = probe_health_endpoint(endpoint)
        else:
            status, source = "declared", "declared"
        matrix.append({
            "id": row_id,
            "label": f"Fly.io {env.upper()}",
            "status": status,
            "score": STATUS_SCORE.get(status, 40),
            "source": source,
            "detail": endpoint,
        })

    evidence_status, evidence_source = evidence_gate_status(runs, artifact_root)
    matrix.append({
        "id": "evidence_gate",
        "label": "Evidence Gate",
        "status": evidence_status,
        "score": STATUS_SCORE.get(evidence_status, 40),
        "source": evidence_source,
        "detail": "PR Evidence Gate / artifact local",
    })

    sec_status = security_gates_status(runs)
    matrix.append({
        "id": "security_gates",
        "label": "Security & Governance Gates",
        "status": sec_status,
        "score": STATUS_SCORE.get(sec_status, 40),
        "source": "live" if runs else "fallback",
        "detail": "workflows com keywords de seguranca/governanca",
    })

    return matrix


def compute_runtime_score(matrix: list[dict[str, Any]]) -> int:
    if not matrix:
        return 40
    total_weight = sum(HEALTH_MATRIX_WEIGHTS.get(row["id"], 0.0) for row in matrix)
    if total_weight <= 0:
        return 40
    weighted = sum(
        row.get("score", STATUS_SCORE.get(row.get("status", "unknown"), 40))
        * HEALTH_MATRIX_WEIGHTS.get(row["id"], 0.0)
        for row in matrix
    )
    return max(0, min(100, int(round(weighted / total_weight))))


def build_quarantine(
    state: str,
    runs: list[WorkflowRun],
    backlog: list[dict[str, Any]],
    matrix: list[dict[str, Any]],
) -> dict[str, Any]:
    security_row = next((row for row in matrix if row["id"] == "security_gates"), None)
    critical_gaps = [item for item in backlog if item.get("priority") == "P0"]
    security_failures = [
        run for run in runs
        if run.health == "red" and any(keyword in run.name.lower() for keyword in SECURITY_KEYWORDS)
    ]

    reasons: list[str] = []
    if security_row and security_row.get("status") == "red":
        reasons.append("security_gates_red")
    if critical_gaps:
        reasons.append("critical_operational_gaps")
    if security_failures:
        reasons.append("security_workflow_failure")

    active = bool(reasons) or (state == "red" and security_failures)
    return {
        "active": active,
        "reason": reasons[0] if reasons else None,
        "reasons": reasons,
        "blocked_actions": ["deploy", "promote"] if active else [],
        "policy": "AOP-SEC-QUARANTINE-001",
    }


def evaluate_governed_retry(run: WorkflowRun) -> tuple[bool, str]:
    if is_blocklisted(run.name):
        return False, "workflow_blocklisted"
    if run.name not in ALLOWLISTED_REMEDIATION_WORKFLOWS:
        return False, "workflow_not_allowlisted"
    if run.run_attempt >= MAX_RERUN_ATTEMPTS:
        return False, "max_rerun_attempts_reached"
    if run.health != "yellow":
        return False, "non_transient_or_non_allowlisted_state"
    return True, "transient_allowlisted_failure"


def build_retry_policy(plan: list[dict[str, Any]], runs: list[WorkflowRun], mode: str) -> dict[str, Any]:
    run_by_id = {run.id: run for run in runs}
    eligible = [item for item in plan if item.get("allowed")]
    blocked_items = [item for item in plan if not item.get("allowed")]

    blocked_reasons = sorted({str(item.get("reason") or "blocked") for item in blocked_items})
    anti_loop_triggered = any(
        run_by_id.get(int(item.get("run_id") or 0), WorkflowRun(0, "", "completed", None, "", None, None, "", None, None)).run_attempt
        >= MAX_RERUN_ATTEMPTS
        for item in plan
        if item.get("run_id") is not None
    )

    allowed = mode == "execute" and bool(eligible) and not anti_loop_triggered
    return {
        "allowed": allowed,
        "policy": "AOP-CI-RETRY-001",
        "attempts": MAX_RERUN_ATTEMPTS,
        "cooldown_minutes": RETRY_COOLDOWN_MINUTES,
        "eligible_reruns": len(eligible),
        "blocked_reason": blocked_reasons[0] if blocked_reasons and not allowed else None,
        "blocked_reasons": blocked_reasons,
        "anti_loop": True,
        "anti_loop_triggered": anti_loop_triggered,
    }


def build_remediation_plan(runs: list[WorkflowRun]) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for run in runs:
        if (
            run.conclusion == "cancelled"
            and run.name in CONCURRENCY_MESH_SUPPRESSED_WORKFLOWS
        ):
            continue
        if run.health == "yellow":
            allowed, reason = evaluate_governed_retry(run)
            if allowed:
                plan.append(
                    {
                        "run_id": run.id,
                        "workflow": run.name,
                        "action": "rerun_failed_jobs",
                        "allowed": True,
                        "reason": reason,
                        "severity": run.severity,
                        "url": run.url,
                        "run_attempt": run.run_attempt,
                    }
                )
            else:
                plan.append(
                    {
                        "run_id": run.id,
                        "workflow": run.name,
                        "action": "manual_or_code_fix_required",
                        "allowed": False,
                        "reason": reason,
                        "severity": run.severity,
                        "url": run.url,
                        "run_attempt": run.run_attempt,
                    }
                )
        elif run.health == "red":
            plan.append(
                {
                    "run_id": run.id,
                    "workflow": run.name,
                    "action": "manual_or_code_fix_required",
                    "allowed": False,
                    "reason": "real_failure_not_auto_remediated",
                    "severity": run.severity,
                    "url": run.url,
                    "run_attempt": run.run_attempt,
                }
            )
    return plan


def execute_plan(repo: str, token: str, plan: list[dict[str, Any]], retry_policy: dict[str, Any]) -> list[dict[str, Any]]:
    if not retry_policy.get("allowed"):
        return []
    executed: list[dict[str, Any]] = []
    for item in plan:
        if not item.get("allowed"):
            continue
        github_request("POST", repo_api(repo, f"actions/runs/{item['run_id']}/rerun-failed-jobs"), token)
        executed.append({**item, "executed": True})
    return executed


def build_backlog(runs: list[WorkflowRun], plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    backlog: list[dict[str, Any]] = []
    for item in plan:
        if item.get("allowed"):
            backlog.append({
                "id": f"OPS-AUTO-{item['run_id']}",
                "type": "remediation",
                "priority": "P2" if item.get("severity") in {"medium", "low"} else "P1",
                "title": f"Executar remediação governada para {item['workflow']}",
                "evidence": item.get("url"),
                "suggested_action": item.get("action"),
            })
        else:
            backlog.append({
                "id": f"OPS-GAP-{item['run_id']}",
                "type": "gap",
                "priority": "P0" if item.get("severity") == "critical" else "P1",
                "title": f"Tratar falha não autocorrigível em {item['workflow']}",
                "evidence": item.get("url"),
                "suggested_action": "human_review_after_safe_auto_correction",
            })
    for run in runs:
        if run.health == "pending":
            backlog.append({
                "id": f"OPS-PENDING-{run.id}",
                "type": "monitoring",
                "priority": "P3",
                "title": f"Acompanhar workflow pendente {run.name}",
                "evidence": run.url,
                "suggested_action": "wait_for_ci_completion",
            })
    return backlog


def build_environment_sync() -> dict[str, Any]:
    return {
        "strategy": "dev_to_homolog_to_prod",
        "production_execution": "blocked_without_explicit_governed_promotion",
        "flyio_health_endpoints": ENVIRONMENT_ENDPOINTS,
        "required_evidence": ["health_check", "ci_green", "rollback_metadata", "change_ticket_for_prod"],
    }


def build_rollback_policy(state: str) -> dict[str, Any]:
    return {
        "status": "armed" if state in {"red", "yellow"} else "standby",
        "execution": "manual_approval_required",
        "automatic_destructive_actions": False,
        "safe_actions": ["rerun_failed_jobs_allowlisted", "publish_evidence", "open_backlog_gap"],
        "required_metadata": ["source_ref", "target_environment", "last_green_sha", "correlation_id"],
    }


def classify_maturity(state: str, runs: list[WorkflowRun], backlog: list[dict[str, Any]], runtime_score: int) -> dict[str, Any]:
    return {
        "level": MATURITY_LEVELS.get(state, "unknown"),
        "state": state,
        "score": runtime_score,
        "signals": {
            "total_runs": len(runs),
            "automated_backlog_items": len(backlog),
            "has_critical_gap": any(item.get("priority") == "P0" for item in backlog),
        },
    }


def build_report(
    repo: str,
    branch: str,
    runs: list[WorkflowRun],
    plan: list[dict[str, Any]],
    executed: list[dict[str, Any]],
    mode: str,
    *,
    probe_env: bool = False,
    artifact_root: Path | None = None,
    data_sources: list[dict[str, str]] | None = None,
    confidence: str = "high",
) -> dict[str, Any]:
    artifact_root = artifact_root or Path(".")
    red = [run for run in runs if run.health == "red"]
    yellow = [run for run in runs if run.health == "yellow"]
    pending = [run for run in runs if run.health == "pending"]
    state = "red" if red else "yellow" if yellow or pending else "green"
    backlog = build_backlog(runs, plan)
    health_matrix = build_health_matrix(runs, probe_env=probe_env, artifact_root=artifact_root)
    runtime_score = compute_runtime_score(health_matrix)
    retry_policy = build_retry_policy(plan, runs, mode)
    quarantine = build_quarantine(state, runs, backlog, health_matrix)
    executive_status = "Runtime operacional saudável" if state == "green" else "Runtime requer acompanhamento governado" if state == "yellow" else "Runtime com bloqueios operacionais"
    return {
        "schema_version": "1.2.0",
        "correlation_id": str(uuid4()),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repository": repo,
        "branch": branch,
        "mode": mode,
        "state": state,
        "confidence": confidence,
        "executive_status": executive_status,
        "runtime_score": runtime_score,
        "health_matrix": health_matrix,
        "quarantine": quarantine,
        "retry_policy": retry_policy,
        "data_sources": data_sources or [{"stage": "github_api", "status": "ok", "confidence": confidence}],
        "maturity": classify_maturity(state, runs, backlog, runtime_score),
        "summary": {
            "runs": len(runs),
            "green": sum(1 for run in runs if run.health == "green"),
            "yellow": len(yellow),
            "red": len(red),
            "pending": len(pending),
            "remediation_candidates": sum(1 for item in plan if item.get("allowed")),
            "blocked_remediations": sum(1 for item in plan if not item.get("allowed")),
            "executed_remediations": len(executed),
            "runtime_score": runtime_score,
            "quarantine_active": quarantine.get("active", False),
        },
        "runs": [asdict(run) | {"health": run.health, "severity": run.severity} for run in runs],
        "remediation_plan": plan,
        "executed_remediations": executed,
        "automatic_backlog": backlog,
        "regression_detection": {
            "enabled": True,
            "state": "regression_suspected" if red else "no_regression_detected",
            "failed_workflows": [run.name for run in red],
        },
        "environment_sync": build_environment_sync(),
        "rollback_policy": build_rollback_policy(state),
        "evidence_consolidation": {
            "artifact": "runtime-health-validator-evidence",
            "files": ["runtime-health-validator.json", "summary.md"],
            "dashboard_entrypoint": "summary.md",
        },
        "guardrails": {
            "merge": False,
            "deploy": quarantine.get("active", False),
            "production_change": quarantine.get("active", False),
            "branch_protection_change": False,
            "secrets_change": False,
            "anti_loop": True,
        },
    }


def build_baseline_report(repo: str, branch: str, mode: str) -> dict[str, Any]:
    return build_report(
        repo,
        branch,
        [],
        [],
        [],
        mode,
        probe_env=False,
        artifact_root=Path("."),
        data_sources=[
            {"stage": "github_api", "status": "unavailable", "confidence": "low"},
            {"stage": "cached_artifact", "status": "unavailable", "confidence": "low"},
            {"stage": "baseline", "status": "ok", "confidence": "low"},
        ],
        confidence="low",
    )


def fetch_runs_with_fallback(
    repo: str,
    token: str | None,
    branch: str,
    limit: int,
    cached_path: Path,
) -> tuple[list[WorkflowRun], list[dict[str, str]], str]:
    data_sources: list[dict[str, str]] = []

    if token:
        try:
            runs = fetch_recent_runs(repo, token, branch, limit)
            data_sources.append({"stage": "github_api", "status": "ok", "confidence": "high"})
            return runs, data_sources, "high"
        except RuntimeError as exc:
            data_sources.append({"stage": "github_api", "status": "error", "detail": str(exc), "confidence": "low"})
    else:
        data_sources.append({"stage": "github_api", "status": "skipped", "detail": "GITHUB_TOKEN missing", "confidence": "low"})

    cached = load_cached_report(cached_path)
    if cached and cached.get("runs"):
        runs = [
            WorkflowRun(
                id=int(item.get("id") or 0),
                name=item.get("name") or "workflow-desconhecido",
                status=item.get("status") or "unknown",
                conclusion=item.get("conclusion"),
                event=item.get("event") or "unknown",
                branch=item.get("branch"),
                sha=item.get("sha"),
                url=item.get("url") or "",
                created_at=item.get("created_at"),
                updated_at=item.get("updated_at"),
                run_attempt=int(item.get("run_attempt") or 1),
            )
            for item in cached.get("runs", [])
        ]
        data_sources.append({"stage": "cached_artifact", "status": "ok", "path": str(cached_path), "confidence": "medium"})
        return runs, data_sources, "medium"

    data_sources.append({"stage": "cached_artifact", "status": "unavailable", "confidence": "low"})
    data_sources.append({"stage": "baseline", "status": "ok", "confidence": "low"})
    return [], data_sources, "low"


def write_report(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "runtime-health-validator.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# Runtime Health Validator",
        "",
        f"- Correlation ID: `{report['correlation_id']}`",
        f"- Repository: `{report['repository']}`",
        f"- Branch: `{report['branch']}`",
        f"- Mode: `{report['mode']}`",
        f"- State: `{report['state']}`",
        f"- Confidence: `{report.get('confidence', 'high')}`",
        f"- Runtime score: `{report.get('runtime_score')}`",
        f"- Executive status: `{report['executive_status']}`",
        f"- Maturity: `{report['maturity']['level']}` (`{report['maturity']['score']}`)",
        f"- Generated at: `{report['generated_at']}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for key, value in report["summary"].items():
        lines.append(f"| `{key}` | `{value}` |")

    lines.extend(["", "## Health matrix", ""])
    for row in report.get("health_matrix", []):
        lines.append(
            f"- `{row['id']}` · status=`{row['status']}` · score=`{row['score']}` · source=`{row['source']}`"
        )

    quarantine = report.get("quarantine") or {}
    lines.extend([
        "",
        "## Quarantine",
        "",
        f"- Active: `{quarantine.get('active', False)}`",
        f"- Policy: `{quarantine.get('policy')}`",
        f"- Blocked actions: `{', '.join(quarantine.get('blocked_actions') or []) or 'none'}`",
    ])

    retry_policy = report.get("retry_policy") or {}
    lines.extend([
        "",
        "## Retry policy",
        "",
        f"- Allowed: `{retry_policy.get('allowed')}`",
        f"- Policy: `{retry_policy.get('policy')}`",
        f"- Attempts: `{retry_policy.get('attempts')}`",
        f"- Cooldown (min): `{retry_policy.get('cooldown_minutes')}`",
    ])

    lines.extend(["", "## Remediation plan", ""])
    if report["remediation_plan"]:
        for item in report["remediation_plan"]:
            lines.append(f"- `{item['action']}` · `{item['workflow']}` · allowed=`{item['allowed']}` · severity=`{item['severity']}` · [run]({item['url']})")
    else:
        lines.append("- None")
    lines.extend(["", "## Automatic backlog", ""])
    if report["automatic_backlog"]:
        for item in report["automatic_backlog"]:
            lines.append(f"- `{item['priority']}` · `{item['type']}` · {item['title']}")
    else:
        lines.append("- None")
    lines.extend(["", "## Environment sync", ""])
    for env, endpoint in report["environment_sync"]["flyio_health_endpoints"].items():
        lines.append(f"- `{env}`: `{endpoint}`")
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Runtime health validator and governed remediation executor.")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--branch", default="main")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--mode", choices=["report_only", "dry_run", "execute"], default="report_only")
    parser.add_argument("--output-dir", default="artifacts/runtime-health-validator")
    parser.add_argument("--probe-env", action="store_true", help="Probe Fly.io health endpoints (default: declared only).")
    parser.add_argument("--artifact-root", default=".", help="Root for local artifact fallback lookups.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.repo:
        print("--repo or GITHUB_REPOSITORY is required", file=sys.stderr)
        return 2

    output_dir = Path(args.output_dir)
    cached_path = output_dir / "runtime-health-validator.json"
    if not cached_path.exists():
        cached_path = DEFAULT_CACHED_ARTIFACT

    token = os.environ.get("GITHUB_TOKEN")
    runs, data_sources, confidence = fetch_runs_with_fallback(
        args.repo,
        token,
        args.branch,
        args.limit,
        cached_path,
    )

    if not runs and confidence == "low":
        report = build_baseline_report(args.repo, args.branch, args.mode)
        write_report(report, output_dir)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    plan = build_remediation_plan(runs)
    retry_policy = build_retry_policy(plan, runs, args.mode)
    executed: list[dict[str, Any]] = []
    if args.mode == "execute" and token and retry_policy.get("allowed"):
        executed = execute_plan(args.repo, token, plan, retry_policy)

    report = build_report(
        args.repo,
        args.branch,
        runs,
        plan,
        executed,
        args.mode,
        probe_env=args.probe_env,
        artifact_root=Path(args.artifact_root),
        data_sources=data_sources,
        confidence=confidence,
    )
    write_report(report, output_dir)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
