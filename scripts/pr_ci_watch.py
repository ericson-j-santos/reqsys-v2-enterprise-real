#!/usr/bin/env python3
"""PR CI Watcher seguro para ReqSys.

Responsabilidades P1:
- consultar runs de GitHub Actions associados a um commit SHA;
- classificar status operacional dos workflows;
- coletar jobs e steps falhos;
- classificar causa provável das falhas;
- gerar artefato JSON/Markdown;
- opcionalmente comentar no PR;
- não fazer merge automático;
- não alterar produção.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

API_VERSION = "2022-11-28"
DEFAULT_REPORT_DIR = Path("artifacts/pr-ci-watch")


@dataclass(frozen=True)
class WorkflowRun:
    id: int
    name: str
    status: str
    conclusion: str | None
    html_url: str | None

    @property
    def health(self) -> str:
        if self.status != "completed":
            return "running"
        if self.conclusion == "success":
            return "healthy"
        if self.conclusion in {"failure", "cancelled", "timed_out", "action_required"}:
            return "unhealthy"
        return "unknown"


@dataclass(frozen=True)
class FailedStep:
    name: str
    number: int | None
    conclusion: str | None


@dataclass(frozen=True)
class FailedJob:
    run_id: int
    run_name: str
    job_id: int
    job_name: str
    conclusion: str | None
    html_url: str | None
    failed_steps: list[FailedStep]
    probable_cause: str
    recommended_action: str


def request_json(method: str, url: str, token: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": API_VERSION,
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:  # noqa: S310 - GitHub API URL controlada
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"GitHub API falhou {exc.code}: {detail}") from exc


def fetch_runs(repo: str, sha: str, token: str) -> list[WorkflowRun]:
    url = f"https://api.github.com/repos/{repo}/actions/runs?head_sha={sha}&per_page=100"
    data = request_json("GET", url, token)
    return [
        WorkflowRun(
            id=int(item.get("id") or 0),
            name=str(item.get("name") or "workflow-desconhecido"),
            status=str(item.get("status") or "unknown"),
            conclusion=item.get("conclusion"),
            html_url=item.get("html_url"),
        )
        for item in data.get("workflow_runs", [])
    ]


def classify_probable_cause(run_name: str, job_name: str, failed_steps: list[FailedStep]) -> tuple[str, str]:
    haystack = " ".join([run_name, job_name, *[step.name for step in failed_steps]]).lower()

    rules: list[tuple[str, str, str]] = [
        (r"conflict|merge", "conflito_de_merge", "Atualizar branch contra main e resolver conflitos."),
        (r"governance|quality|guardrail|baseline|security", "gate_de_governanca", "Verificar arquivos de governança, baseline, LGPD e quality gates."),
        (r"ruff|lint|eslint|typecheck|py_compile", "qualidade_estatica", "Corrigir lint, typecheck ou compilação estática."),
        (r"test|pytest|unit", "teste_automatizado", "Abrir log do job e corrigir teste, fixture ou regressão funcional."),
        (r"artifact|upload", "artifact_ausente_ou_invalido", "Garantir geração de diretório/arquivos antes do upload-artifact."),
        (r"branch protection|ruleset|codeowners", "branch_protection", "Validar CODEOWNERS, ruleset e permissões obrigatórias."),
        (r"deploy|fly|runtime|health", "runtime_ou_deploy", "Validar health, status Fly.io e logs operacionais."),
    ]

    for pattern, cause, action in rules:
        if re.search(pattern, haystack):
            return cause, action

    return "falha_nao_classificada", "Abrir logs do job falho e classificar manualmente a causa raiz."


def fetch_failed_jobs(repo: str, runs: list[WorkflowRun], token: str) -> list[FailedJob]:
    failed_jobs: list[FailedJob] = []
    unhealthy_runs = [run for run in runs if run.health == "unhealthy"]

    for run in unhealthy_runs:
        url = f"https://api.github.com/repos/{repo}/actions/runs/{run.id}/jobs?per_page=100"
        data = request_json("GET", url, token)
        for job in data.get("jobs", []):
            conclusion = job.get("conclusion")
            if conclusion not in {"failure", "cancelled", "timed_out", "action_required"}:
                continue

            steps = [
                FailedStep(
                    name=str(step.get("name") or "step-desconhecido"),
                    number=step.get("number"),
                    conclusion=step.get("conclusion"),
                )
                for step in job.get("steps", [])
                if step.get("conclusion") in {"failure", "cancelled", "timed_out", "action_required"}
            ]
            job_name = str(job.get("name") or "job-desconhecido")
            cause, action = classify_probable_cause(run.name, job_name, steps)
            failed_jobs.append(
                FailedJob(
                    run_id=run.id,
                    run_name=run.name,
                    job_id=int(job.get("id") or 0),
                    job_name=job_name,
                    conclusion=conclusion,
                    html_url=job.get("html_url"),
                    failed_steps=steps,
                    probable_cause=cause,
                    recommended_action=action,
                )
            )

    return failed_jobs


def classify(runs: list[WorkflowRun], failed_jobs: list[FailedJob]) -> dict[str, Any]:
    total = len(runs)
    healthy = sum(1 for run in runs if run.health == "healthy")
    running = sum(1 for run in runs if run.health == "running")
    unhealthy = sum(1 for run in runs if run.health == "unhealthy")
    unknown = sum(1 for run in runs if run.health == "unknown")
    score = round((healthy / total) * 100, 2) if total else 0.0

    if not runs:
        decision = "aguardar_checks_ou_verificar_disparo_de_workflows"
    elif unhealthy:
        decision = "corrigir_falhas_antes_de_liberar_revisao"
    elif running:
        decision = "aguardar_finalizacao_dos_workflows"
    elif unknown:
        decision = "investigar_status_desconhecido"
    else:
        decision = "pronto_para_revisao"

    return {
        "total": total,
        "healthy": healthy,
        "running": running,
        "unhealthy": unhealthy,
        "unknown": unknown,
        "failed_jobs": len(failed_jobs),
        "score": score,
        "decision": decision,
    }


def render_markdown(
    repo: str,
    pr_number: str,
    sha: str,
    runs: list[WorkflowRun],
    failed_jobs: list[FailedJob],
    summary: dict[str, Any],
) -> str:
    lines = [
        "# PR CI Watch",
        "",
        "| Campo | Valor |",
        "|---|---|",
        f"| Repositório | `{repo}` |",
        f"| PR | `{pr_number}` |",
        f"| SHA | `{sha}` |",
        f"| Score | `{summary['score']}` |",
        f"| Jobs falhos | `{summary['failed_jobs']}` |",
        f"| Decisão | `{summary['decision']}` |",
        f"| Gerado em UTC | `{datetime.now(timezone.utc).isoformat()}` |",
        "",
        "## Workflows",
        "",
        "| Health | Workflow | Status | Conclusion | Link |",
        "|---|---|---|---|---|",
    ]

    if not runs:
        lines.append("| warning | Nenhum workflow encontrado para o SHA | — | — | — |")
    for run in runs:
        link = f"[abrir]({run.html_url})" if run.html_url else "—"
        lines.append(f"| `{run.health}` | `{run.name}` | `{run.status}` | `{run.conclusion}` | {link} |")

    lines.extend(["", "## Falhas classificadas", ""])
    if not failed_jobs:
        lines.append("Nenhum job falho encontrado.")
    else:
        lines.extend(
            [
                "| Workflow | Job | Steps falhos | Causa provável | Ação recomendada | Link |",
                "|---|---|---|---|---|---|",
            ]
        )
        for job in failed_jobs:
            steps = ", ".join(step.name for step in job.failed_steps) or "—"
            link = f"[abrir]({job.html_url})" if job.html_url else "—"
            lines.append(
                f"| `{job.run_name}` | `{job.job_name}` | `{steps}` | `{job.probable_cause}` | {job.recommended_action} | {link} |"
            )

    lines.extend(
        [
            "",
            "## Política P1",
            "",
            "- Não faz merge automático.",
            "- Não altera produção.",
            "- Não altera status de draft automaticamente.",
            "- Coleta jobs e steps falhos via API do GitHub.",
            "- Classifica causa provável sem expor logs extensos ou secrets.",
        ]
    )
    return "\n".join(lines) + "\n"


def post_comment(repo: str, pr_number: str, token: str, markdown: str) -> None:
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    request_json("POST", url, token, {"body": markdown})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--pr-number", required=True)
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    parser.add_argument("--comment", action="store_true")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN ausente.", file=sys.stderr)
        return 1

    runs = fetch_runs(args.repo, args.sha, token)
    failed_jobs = fetch_failed_jobs(args.repo, runs, token)
    summary = classify(runs, failed_jobs)
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "repo": args.repo,
        "pr_number": args.pr_number,
        "sha": args.sha,
        "summary": summary,
        "runs": [asdict(run) | {"health": run.health} for run in runs],
        "failed_jobs": [asdict(job) for job in failed_jobs],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (report_dir / "pr-ci-watch.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    markdown = render_markdown(args.repo, args.pr_number, args.sha, runs, failed_jobs, summary)
    (report_dir / "pr-ci-watch.md").write_text(markdown, encoding="utf-8")

    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as handle:
            handle.write(markdown)

    if args.comment:
        post_comment(args.repo, args.pr_number, token, markdown)

    if summary["decision"] == "corrigir_falhas_antes_de_liberar_revisao":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
