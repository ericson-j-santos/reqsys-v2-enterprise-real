#!/usr/bin/env python3
"""PR CI Watcher seguro para ReqSys.

Responsabilidades P0:
- consultar runs de GitHub Actions associados a um commit SHA;
- classificar status operacional dos workflows;
- gerar artefato JSON/Markdown;
- opcionalmente comentar no PR;
- evitar falso verde quando não há evidência suficiente;
- não fazer merge automático;
- não alterar produção.
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
from typing import Any

API_VERSION = "2022-11-28"
DEFAULT_REPORT_DIR = Path("artifacts/pr-ci-watch")
BLOCKING_CONCLUSIONS = {"failure", "cancelled", "timed_out", "action_required"}
NON_BLOCKING_CONCLUSIONS = {"success", "neutral", "skipped"}
FAIL_SEVERITIES = {"critical", "warning"}


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

    @property
    def health(self) -> str:
        if self.status != "completed":
            return "running"
        if self.conclusion == "success":
            return "healthy"
        if self.conclusion in BLOCKING_CONCLUSIONS:
            return "unhealthy"
        if self.conclusion in NON_BLOCKING_CONCLUSIONS:
            return "non_blocking"
        return "unknown"

    @property
    def is_completed_success(self) -> bool:
        return self.status == "completed" and self.conclusion == "success"


def request_json(method: str, url: str, token: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": "reqsys-pr-ci-watch",
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


def fetch_runs(repo: str, sha: str, token: str, exclude_run_id: int | None = None) -> list[WorkflowRun]:
    url = f"https://api.github.com/repos/{repo}/actions/runs?head_sha={sha}&per_page=100"
    data = request_json("GET", url, token)
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
            )
        )
    return runs


def classify(runs: list[WorkflowRun]) -> dict[str, Any]:
    total = len(runs)
    healthy = sum(1 for run in runs if run.health == "healthy")
    running = sum(1 for run in runs if run.health == "running")
    unhealthy = sum(1 for run in runs if run.health == "unhealthy")
    non_blocking = sum(1 for run in runs if run.health == "non_blocking")
    unknown = sum(1 for run in runs if run.health == "unknown")
    completed = sum(1 for run in runs if run.status == "completed")
    blocking_total = total - non_blocking
    blocking_healthy = healthy
    score = round((blocking_healthy / blocking_total) * 100, 2) if blocking_total else 0.0

    if not runs:
        decision = "sem_evidencia_ci_para_o_sha"
        severity = "warning"
    elif unhealthy:
        decision = "corrigir_falhas_antes_de_liberar_revisao"
        severity = "critical"
    elif running:
        decision = "aguardar_finalizacao_dos_workflows"
        severity = "pending"
    elif unknown:
        decision = "investigar_status_desconhecido"
        severity = "warning"
    elif healthy:
        decision = "pronto_para_revisao"
        severity = "ok"
    else:
        decision = "sem_check_bloqueante_conclusivo"
        severity = "warning"

    return {
        "total": total,
        "completed": completed,
        "healthy": healthy,
        "running": running,
        "unhealthy": unhealthy,
        "non_blocking": non_blocking,
        "unknown": unknown,
        "score": score,
        "severity": severity,
        "decision": decision,
    }


def render_markdown(repo: str, pr_number: str, sha: str, runs: list[WorkflowRun], summary: dict[str, Any]) -> str:
    lines = [
        "# PR CI Watch",
        "",
        "| Campo | Valor |",
        "|---|---|",
        f"| Repositório | `{repo}` |",
        f"| PR | `{pr_number}` |",
        f"| SHA | `{sha}` |",
        f"| Severidade | `{summary['severity']}` |",
        f"| Score bloqueante | `{summary['score']}` |",
        f"| Decisão | `{summary['decision']}` |",
        f"| Gerado em UTC | `{datetime.now(timezone.utc).isoformat()}` |",
        "",
        "## Resumo operacional",
        "",
        "| Total | Completed | Healthy | Running | Unhealthy | Non blocking | Unknown |",
        "|---:|---:|---:|---:|---:|---:|---:|",
        (
            f"| {summary['total']} | {summary['completed']} | {summary['healthy']} | "
            f"{summary['running']} | {summary['unhealthy']} | {summary['non_blocking']} | {summary['unknown']} |"
        ),
        "",
        "## Workflows",
        "",
        "| Health | Workflow | Status | Conclusion | Event | Atualizado | Link |",
        "|---|---|---|---|---|---|---|",
    ]

    if not runs:
        lines.append("| `warning` | Nenhum workflow encontrado para o SHA | — | — | — | — | — |")
    for run in runs:
        link = f"[abrir]({run.html_url})" if run.html_url else "—"
        lines.append(
            f"| `{run.health}` | `{run.name}` | `{run.status}` | `{run.conclusion}` | "
            f"`{run.event}` | `{run.updated_at}` | {link} |"
        )

    lines.extend(
        [
            "",
            "## Política P0",
            "",
            "- Não faz merge automático.",
            "- Não altera produção.",
            "- Não altera status de draft automaticamente nesta versão.",
            "- Exclui a própria execução do watcher quando `GITHUB_RUN_ID` está disponível, evitando falso bloqueio por auto-observação.",
            "- Estado `pending` por workflows em execução é informativo e não bloqueia por si só.",
            "- Falha o job quando há workflow unhealthy, status desconhecido ou quando não existe evidência CI suficiente para o SHA.",
        ]
    )
    return "\n".join(lines) + "\n"


def post_comment(repo: str, pr_number: str, token: str, markdown: str) -> None:
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    request_json("POST", url, token, {"body": markdown})


def parse_optional_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--pr-number", required=True)
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    parser.add_argument("--comment", action="store_true")
    parser.add_argument("--exclude-run-id", default=os.environ.get("GITHUB_RUN_ID"))
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN ausente.", file=sys.stderr)
        return 1

    runs = fetch_runs(args.repo, args.sha, token, exclude_run_id=parse_optional_int(args.exclude_run_id))
    summary = classify(runs)
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "repo": args.repo,
        "pr_number": args.pr_number,
        "sha": args.sha,
        "summary": summary,
        "runs": [asdict(run) | {"health": run.health} for run in runs],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (report_dir / "pr-ci-watch.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    markdown = render_markdown(args.repo, args.pr_number, args.sha, runs, summary)
    (report_dir / "pr-ci-watch.md").write_text(markdown, encoding="utf-8")

    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as handle:
            handle.write(markdown)

    if args.comment:
        post_comment(args.repo, args.pr_number, token, markdown)

    if summary["severity"] in FAIL_SEVERITIES:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
