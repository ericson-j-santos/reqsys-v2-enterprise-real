#!/usr/bin/env python3
"""PR CI Watcher seguro para ReqSys.

Responsabilidades P0:
- consultar runs de GitHub Actions associados a um commit SHA;
- classificar status operacional dos workflows;
- gerar artefato JSON/Markdown;
- opcionalmente comentar no PR;
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


def classify(runs: list[WorkflowRun]) -> dict[str, Any]:
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
        "score": score,
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
        f"| Score | `{summary['score']}` |",
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

    lines.extend(
        [
            "",
            "## Política P0",
            "",
            "- Não faz merge automático.",
            "- Não altera produção.",
            "- Não altera status de draft automaticamente nesta versão.",
            "- Gera diagnóstico e evidência operacional.",
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

    if summary["decision"] == "corrigir_falhas_antes_de_liberar_revisao":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
