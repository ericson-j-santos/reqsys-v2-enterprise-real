#!/usr/bin/env python3
"""PR CI Watcher e ciclo de remediação governada do ReqSys.

Responsabilidades:
- observar somente os workflows obrigatórios de prontidão do PR;
- usar a execução mais recente de cada workflow, evitando falso vermelho por tentativas antigas;
- gerar evidência JSON/Markdown;
- marcar falhas reais como bloqueantes;
- reexecutar, no máximo uma vez, apenas falhas transitórias de workflows explicitamente permitidos;
- varrer PRs abertos periodicamente para evitar CI vermelho abandonado;
- manter um único comentário operacional por PR;
- nunca alterar código, segredos, produção ou executar merge automaticamente.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

API_VERSION = "2022-11-28"
DEFAULT_REPORT_DIR = Path("artifacts/pr-ci-watch")
COMMENT_MARKER = "<!-- reqsys-pr-ci-watch -->"

BLOCKING_CONCLUSIONS = {"failure", "timed_out", "action_required"}
CANCELLED_CONCLUSIONS = {"cancelled"}
NON_BLOCKING_CONCLUSIONS = {"success", "neutral", "skipped"}
FAIL_SEVERITIES = {"critical"}

REQUIRED_WORKFLOWS = (
    "CI Enterprise Fast",
    "CI — ReqSys v2 Enterprise",
    "Governance Quality Gates",
    "Governança Padrão Ouro",
    "Branch Protection Audit",
    "PR Conflict Guard",
    "Governed Merge Queue",
)

AUTO_RETRY_WORKFLOWS = {
    "CI Enterprise Fast",
    "CI — ReqSys v2 Enterprise",
}

MAX_AUTOMATIC_RUN_ATTEMPT = 1

TRANSIENT_STEP_KEYWORDS = (
    "checkout",
    "setup",
    "instalar",
    "install",
    "download",
    "upload",
    "cache",
    "restore",
    "network",
    "runner",
    "dependency",
    "dependenc",
)

DETERMINISTIC_STEP_KEYWORDS = (
    "test",
    "teste",
    "lint",
    "typecheck",
    "build",
    "guardrail",
    "contrato",
    "contract",
    "schema",
)

PROTECTED_STEP_KEYWORDS = (
    "security",
    "segurança",
    "secret",
    "segredo",
    "token",
    "permission",
    "permiss",
    "deploy",
    "production",
    "produção",
    "migration",
    "migração",
    "branch protection",
    "policy",
    "política",
)


@dataclass(frozen=True)
class WorkflowRun:
    id: int
    name: str
    status: str
    conclusion: str | None
    html_url: str | None
    event: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    run_attempt: int = 1

    @property
    def health(self) -> str:
        if self.status != "completed":
            return "running"
        if self.conclusion == "success":
            return "healthy"
        if self.conclusion in CANCELLED_CONCLUSIONS:
            return "cancelled"
        if self.conclusion in BLOCKING_CONCLUSIONS:
            return "unhealthy"
        if self.conclusion in NON_BLOCKING_CONCLUSIONS:
            return "non_blocking"
        return "unknown"


@dataclass(frozen=True)
class FailureDetail:
    job_name: str
    job_url: str | None
    failed_steps: tuple[str, ...]


def request_json(
    method: str,
    url: str,
    token: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any] | list[Any]:
    data = None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": "reqsys-pr-ci-watch",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:  # noqa: S310 - URL controlada
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"GitHub API falhou {exc.code}: {detail}") from exc


def fetch_runs(
    repo: str,
    sha: str,
    token: str,
    exclude_run_id: int | None = None,
) -> list[WorkflowRun]:
    url = f"https://api.github.com/repos/{repo}/actions/runs?head_sha={sha}&per_page=100"
    data = request_json("GET", url, token)
    if not isinstance(data, dict):
        raise RuntimeError("Resposta inesperada ao consultar workflow runs.")

    runs: list[WorkflowRun] = []
    for item in data.get("workflow_runs", []):
        run_id = int(item.get("id") or 0)
        if exclude_run_id and run_id == exclude_run_id:
            continue
        runs.append(
            WorkflowRun(
                id=run_id,
                name=str(item.get("name") or "workflow-desconhecido"),
                status=str(item.get("status") or "unknown"),
                conclusion=item.get("conclusion"),
                html_url=item.get("html_url"),
                event=item.get("event"),
                created_at=item.get("created_at"),
                updated_at=item.get("updated_at"),
                run_attempt=int(item.get("run_attempt") or 1),
            )
        )
    return runs


def fetch_failure_details(repo: str, run_id: int, token: str) -> list[FailureDetail]:
    url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/jobs?per_page=100"
    data = request_json("GET", url, token)
    if not isinstance(data, dict):
        raise RuntimeError("Resposta inesperada ao consultar jobs.")

    details: list[FailureDetail] = []
    for job in data.get("jobs", []):
        if job.get("conclusion") not in BLOCKING_CONCLUSIONS:
            continue
        failed_steps = tuple(
            str(step.get("name") or "etapa-desconhecida")
            for step in job.get("steps", [])
            if step.get("conclusion") in BLOCKING_CONCLUSIONS
        )
        details.append(
            FailureDetail(
                job_name=str(job.get("name") or "job-desconhecido"),
                job_url=job.get("html_url"),
                failed_steps=failed_steps,
            )
        )
    return details


def fetch_open_prs(repo: str, token: str) -> list[dict[str, Any]]:
    url = f"https://api.github.com/repos/{repo}/pulls?state=open&per_page=100&sort=updated&direction=asc"
    data = request_json("GET", url, token)
    if not isinstance(data, list):
        raise RuntimeError("Resposta inesperada ao consultar PRs abertos.")
    return [item for item in data if isinstance(item, dict)]


def latest_relevant_runs(
    runs: Iterable[WorkflowRun],
    required_workflows: Iterable[str] = REQUIRED_WORKFLOWS,
) -> list[WorkflowRun]:
    required = set(required_workflows)
    latest: dict[str, WorkflowRun] = {}

    def key(run: WorkflowRun) -> tuple[str, int]:
        return (run.updated_at or run.created_at or "", run.id)

    for run in runs:
        if run.name not in required:
            continue
        existing = latest.get(run.name)
        if existing is None or key(run) > key(existing):
            latest[run.name] = run

    return [latest[name] for name in required_workflows if name in latest]


def classify(
    runs: list[WorkflowRun],
    required_workflows: Iterable[str] = REQUIRED_WORKFLOWS,
) -> dict[str, Any]:
    required = tuple(required_workflows)
    latest = latest_relevant_runs(runs, required)
    by_name = {run.name: run for run in latest}
    missing = [name for name in required if name not in by_name]

    healthy = sum(1 for run in latest if run.health == "healthy")
    running = sum(1 for run in latest if run.health == "running")
    unhealthy = sum(1 for run in latest if run.health == "unhealthy")
    cancelled = sum(1 for run in latest if run.health == "cancelled")
    non_blocking = sum(1 for run in latest if run.health == "non_blocking")
    unknown = sum(1 for run in latest if run.health == "unknown")
    completed = sum(1 for run in latest if run.status == "completed")
    score = round((healthy / len(required)) * 100, 2) if required else 0.0

    if unhealthy:
        decision = "corrigir_falhas_reais_antes_de_liberar_revisao"
        severity = "critical"
    elif running or missing:
        decision = "aguardar_workflows_obrigatorios"
        severity = "pending"
    elif unknown or cancelled or non_blocking:
        decision = "investigar_workflow_obrigatorio_sem_sucesso"
        severity = "warning"
    elif healthy == len(required) and required:
        decision = "pronto_para_revisao"
        severity = "ok"
    else:
        decision = "sem_evidencia_ci_conclusiva"
        severity = "warning"

    return {
        "required": len(required),
        "observed": len(latest),
        "completed": completed,
        "healthy": healthy,
        "running": running,
        "unhealthy": unhealthy,
        "cancelled": cancelled,
        "non_blocking": non_blocking,
        "unknown": unknown,
        "missing": missing,
        "score": score,
        "severity": severity,
        "decision": decision,
    }


def _contains_any(value: str, keywords: Iterable[str]) -> bool:
    normalized = value.casefold()
    return any(keyword.casefold() in normalized for keyword in keywords)


def classify_failure_kind(details: list[FailureDetail]) -> str:
    names = [detail.job_name for detail in details]
    for detail in details:
        names.extend(detail.failed_steps)
    combined = " | ".join(names)

    if _contains_any(combined, PROTECTED_STEP_KEYWORDS):
        return "protected"
    if _contains_any(combined, DETERMINISTIC_STEP_KEYWORDS):
        return "deterministic"
    if _contains_any(combined, TRANSIENT_STEP_KEYWORDS):
        return "transient"
    return "unknown"


def decide_remediation(run: WorkflowRun, details: list[FailureDetail]) -> dict[str, Any]:
    if run.health != "unhealthy":
        return {"action": "none", "reason": "workflow_not_unhealthy", "failure_kind": "none"}
    if run.name not in AUTO_RETRY_WORKFLOWS:
        return {"action": "escalate", "reason": "workflow_not_in_retry_allowlist", "failure_kind": "protected"}
    if run.run_attempt > MAX_AUTOMATIC_RUN_ATTEMPT:
        return {"action": "escalate", "reason": "automatic_retry_limit_reached", "failure_kind": classify_failure_kind(details)}

    failure_kind = classify_failure_kind(details)
    if run.conclusion == "timed_out":
        return {"action": "rerun_failed_jobs", "reason": "timeout_retry_allowed", "failure_kind": "transient"}
    if failure_kind == "transient":
        return {"action": "rerun_failed_jobs", "reason": "transient_failure_allowed", "failure_kind": failure_kind}
    if failure_kind == "protected":
        return {"action": "escalate", "reason": "protected_failure_never_mutated", "failure_kind": failure_kind}
    if failure_kind == "deterministic":
        return {"action": "escalate", "reason": "deterministic_failure_requires_objective_code_fix", "failure_kind": failure_kind}
    return {"action": "escalate", "reason": "unknown_failure_fail_closed", "failure_kind": failure_kind}


def rerun_failed_jobs(repo: str, run_id: int, token: str) -> None:
    url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/rerun-failed-jobs"
    request_json("POST", url, token)


def attempt_remediation(
    repo: str,
    run: WorkflowRun,
    token: str,
    *,
    enabled: bool,
) -> dict[str, Any]:
    details = fetch_failure_details(repo, run.id, token) if run.health == "unhealthy" else []
    decision = decide_remediation(run, details)
    result: dict[str, Any] = {
        "workflow": run.name,
        "run_id": run.id,
        "run_attempt": run.run_attempt,
        "run_url": run.html_url,
        "enabled": enabled,
        "decision": decision,
        "failure_details": [asdict(item) for item in details],
        "executed": False,
    }
    if enabled and decision["action"] == "rerun_failed_jobs":
        rerun_failed_jobs(repo, run.id, token)
        result["executed"] = True
    return result


def render_failure_details(remediation: dict[str, Any] | None) -> list[str]:
    if not remediation:
        return []
    decision = remediation.get("decision") or {}
    lines = [
        "",
        "## Tratamento governado",
        "",
        "| Campo | Valor |",
        "|---|---|",
        f"| Workflow | `{remediation.get('workflow')}` |",
        f"| Run attempt | `{remediation.get('run_attempt')}` |",
        f"| Tipo da falha | `{decision.get('failure_kind')}` |",
        f"| Ação | `{decision.get('action')}` |",
        f"| Motivo | `{decision.get('reason')}` |",
        f"| Executada | `{remediation.get('executed')}` |",
    ]
    details = remediation.get("failure_details") or []
    if details:
        lines.extend(["", "### Evidência da falha", "", "| Job | Etapas com erro | Link |", "|---|---|---|"])
        for item in details:
            steps = ", ".join(item.get("failed_steps") or []) or "—"
            url = item.get("job_url")
            link = f"[abrir]({url})" if url else "—"
            lines.append(f"| `{item.get('job_name')}` | `{steps}` | {link} |")
    return lines


def render_markdown(
    repo: str,
    pr_number: str,
    sha: str,
    runs: list[WorkflowRun],
    summary: dict[str, Any],
    remediation: dict[str, Any] | None = None,
) -> str:
    latest = latest_relevant_runs(runs)
    lines = [
        COMMENT_MARKER,
        "# PR CI Watch",
        "",
        "| Campo | Valor |",
        "|---|---|",
        f"| Repositório | `{repo}` |",
        f"| PR | `{pr_number}` |",
        f"| SHA | `{sha}` |",
        f"| Severidade | `{summary['severity']}` |",
        f"| Cobertura obrigatória | `{summary['healthy']}/{summary['required']}` |",
        f"| Score | `{summary['score']}` |",
        f"| Decisão | `{summary['decision']}` |",
        f"| Gerado em UTC | `{datetime.now(timezone.utc).isoformat()}` |",
        "",
        "## Workflows obrigatórios",
        "",
        "| Health | Workflow | Status | Conclusion | Tentativa | Link |",
        "|---|---|---|---|---:|---|",
    ]

    by_name = {run.name: run for run in latest}
    for workflow in REQUIRED_WORKFLOWS:
        run = by_name.get(workflow)
        if run is None:
            lines.append(f"| `missing` | `{workflow}` | — | — | — | — |")
            continue
        link = f"[abrir]({run.html_url})" if run.html_url else "—"
        lines.append(
            f"| `{run.health}` | `{run.name}` | `{run.status}` | `{run.conclusion}` | "
            f"`{run.run_attempt}` | {link} |"
        )

    lines.extend(render_failure_details(remediation))
    lines.extend(
        [
            "",
            "## Política",
            "",
            "- Nunca faz merge automático.",
            "- Nunca altera código, segredos, banco ou produção.",
            "- Ignora workflows fora da lista obrigatória para evitar falso bloqueio por auto-observação.",
            "- Considera somente a execução mais recente de cada workflow obrigatório.",
            "- Reexecuta no máximo uma vez e somente falha transitória em workflow permitido.",
            "- Teste, lint, contrato, segurança, permissão, deploy e migração são fail-closed: exigem correção objetiva governada.",
        ]
    )
    return "\n".join(lines) + "\n"


def upsert_comment(repo: str, pr_number: str, token: str, markdown: str) -> None:
    comments_url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments?per_page=100"
    data = request_json("GET", comments_url, token)
    if not isinstance(data, list):
        raise RuntimeError("Resposta inesperada ao consultar comentários do PR.")

    existing_id: int | None = None
    for item in data:
        if isinstance(item, dict) and COMMENT_MARKER in str(item.get("body") or ""):
            existing_id = int(item.get("id") or 0)
            break

    if existing_id:
        request_json(
            "PATCH",
            f"https://api.github.com/repos/{repo}/issues/comments/{existing_id}",
            token,
            {"body": markdown},
        )
    else:
        request_json(
            "POST",
            f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments",
            token,
            {"body": markdown},
        )


def parse_optional_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def analyze_single_pr(
    repo: str,
    pr_number: str,
    sha: str,
    token: str,
    *,
    report_dir: Path,
    exclude_run_id: int | None,
    comment: bool,
    auto_remediate: bool,
    trigger_run_id: int | None,
) -> tuple[dict[str, Any], str]:
    runs = fetch_runs(repo, sha, token, exclude_run_id=exclude_run_id)
    summary = classify(runs)
    latest = latest_relevant_runs(runs)

    remediation: dict[str, Any] | None = None
    if summary["severity"] == "critical":
        candidates = [run for run in latest if run.health == "unhealthy"]
        if trigger_run_id:
            candidates.sort(key=lambda item: item.id != trigger_run_id)
        if candidates:
            remediation = attempt_remediation(
                repo,
                candidates[0],
                token,
                enabled=auto_remediate,
            )

    payload = {
        "repo": repo,
        "pr_number": pr_number,
        "sha": sha,
        "summary": summary,
        "runs": [asdict(run) | {"health": run.health} for run in latest],
        "remediation": remediation,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    markdown = render_markdown(repo, pr_number, sha, runs, summary, remediation)
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "pr-ci-watch.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (report_dir / "pr-ci-watch.md").write_text(markdown, encoding="utf-8")

    if comment and summary["severity"] in {"critical", "ok"}:
        upsert_comment(repo, pr_number, token, markdown)

    return payload, markdown


def render_sweep_markdown(repo: str, analyses: list[dict[str, Any]]) -> str:
    critical = sum(1 for item in analyses if item["summary"]["severity"] == "critical")
    pending = sum(1 for item in analyses if item["summary"]["severity"] == "pending")
    ok = sum(1 for item in analyses if item["summary"]["severity"] == "ok")
    retried = sum(1 for item in analyses if (item.get("remediation") or {}).get("executed"))

    lines = [
        "# PR CI Watch — varredura de PRs abertos",
        "",
        "| Campo | Valor |",
        "|---|---:|",
        f"| PRs avaliados | {len(analyses)} |",
        f"| Críticos | {critical} |",
        f"| Pendentes | {pending} |",
        f"| Saudáveis | {ok} |",
        f"| Reexecuções seguras solicitadas | {retried} |",
        "",
        "| PR | Severidade | Score | Decisão | Tratamento |",
        "|---:|---|---:|---|---|",
    ]
    for item in analyses:
        remediation = item.get("remediation") or {}
        decision = remediation.get("decision") or {}
        treatment = decision.get("action") or "none"
        pr_number = item["pr_number"]
        lines.append(
            f"| [#{pr_number}](https://github.com/{repo}/pull/{pr_number}) | "
            f"`{item['summary']['severity']}` | `{item['summary']['score']}` | "
            f"`{item['summary']['decision']}` | `{treatment}` |"
        )
    return "\n".join(lines) + "\n"


def sweep_open_prs(
    repo: str,
    token: str,
    *,
    report_dir: Path,
    exclude_run_id: int | None,
    comment: bool,
    auto_remediate: bool,
) -> tuple[list[dict[str, Any]], str]:
    prs = fetch_open_prs(repo, token)
    analyses: list[dict[str, Any]] = []

    for pr in prs:
        number = str(pr.get("number") or "")
        sha = str((pr.get("head") or {}).get("sha") or "")
        if not number or not sha:
            continue

        runs = fetch_runs(repo, sha, token, exclude_run_id=exclude_run_id)
        summary = classify(runs)
        latest = latest_relevant_runs(runs)
        remediation: dict[str, Any] | None = None

        if summary["severity"] == "critical":
            candidates = [run for run in latest if run.health == "unhealthy"]
            if candidates:
                remediation = attempt_remediation(
                    repo,
                    candidates[0],
                    token,
                    enabled=auto_remediate,
                )

        item = {
            "pr_number": number,
            "sha": sha,
            "pr_url": pr.get("html_url"),
            "updated_at": pr.get("updated_at"),
            "summary": summary,
            "runs": [asdict(run) | {"health": run.health} for run in latest],
            "remediation": remediation,
        }
        analyses.append(item)

        if comment and summary["severity"] == "critical":
            markdown = render_markdown(repo, number, sha, runs, summary, remediation)
            upsert_comment(repo, number, token, markdown)

    markdown = render_sweep_markdown(repo, analyses)
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "pr-ci-sweep.json").write_text(
        json.dumps(
            {
                "repo": repo,
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "analyses": analyses,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (report_dir / "pr-ci-sweep.md").write_text(markdown, encoding="utf-8")
    return analyses, markdown


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--sha")
    parser.add_argument("--pr-number")
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    parser.add_argument("--comment", action="store_true")
    parser.add_argument("--exclude-run-id", default=os.environ.get("GITHUB_RUN_ID"))
    parser.add_argument("--auto-remediate", action="store_true")
    parser.add_argument("--trigger-run-id")
    parser.add_argument("--sweep-open-prs", action="store_true")
    parser.add_argument(
        "--fail-on-unhealthy",
        action="store_true",
        help="Retorna exit code 1 quando houver CI obrigatório unhealthy.",
    )
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN ausente.", file=sys.stderr)
        return 1

    report_dir = Path(args.report_dir)
    exclude_run_id = parse_optional_int(args.exclude_run_id)

    if args.sweep_open_prs:
        analyses, markdown = sweep_open_prs(
            args.repo,
            token,
            report_dir=report_dir,
            exclude_run_id=exclude_run_id,
            comment=args.comment,
            auto_remediate=args.auto_remediate,
        )
        step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if step_summary:
            with open(step_summary, "a", encoding="utf-8") as handle:
                handle.write(markdown)
        if args.fail_on_unhealthy and any(
            item["summary"]["severity"] in FAIL_SEVERITIES for item in analyses
        ):
            return 1
        return 0

    if not args.sha or not args.pr_number:
        parser.error("--sha e --pr-number são obrigatórios fora de --sweep-open-prs.")

    payload, markdown = analyze_single_pr(
        args.repo,
        args.pr_number,
        args.sha,
        token,
        report_dir=report_dir,
        exclude_run_id=exclude_run_id,
        comment=args.comment,
        auto_remediate=args.auto_remediate,
        trigger_run_id=parse_optional_int(args.trigger_run_id),
    )

    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as handle:
            handle.write(markdown)

    if args.fail_on_unhealthy and payload["summary"]["severity"] in FAIL_SEVERITIES:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
