#!/usr/bin/env python3
"""Repository Health Watchdog.

Verifica sinais operacionais críticos do repositório ReqSys sem alterar estado remoto.
Saídas:
- JSON com evidências auditáveis.
- Markdown executivo para artifact do GitHub Actions.

Escopo intencionalmente read-only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    severity: str
    evidence: dict[str, Any]
    recommendation: str


def _normalize_title(title: str) -> str:
    normalized = re.sub(r"\s+", " ", title.strip().lower())
    normalized = re.sub(r"^draft:\s*", "", normalized)
    return normalized


def _api_get(repo: str, path: str, token: str | None) -> Any:
    url = f"https://api.github.com/repos/{repo}{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "reqsys-repository-health-watchdog",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API error {exc.code} for {path}: {body[:500]}") from exc


def check_main_smoke(
    repo: str,
    token: str | None,
    workflow_name: str,
    artifact_name: str,
    max_age_hours: int,
) -> CheckResult:
    runs_payload = _api_get(repo, "/actions/runs?branch=main&per_page=50", token)
    runs = runs_payload.get("workflow_runs", [])
    matching = [run for run in runs if run.get("name") == workflow_name]

    if not matching:
        return CheckResult(
            name="main_smoke_ci",
            status="failed",
            severity="critical",
            evidence={"workflow_name": workflow_name, "matching_runs": 0},
            recommendation="Executar workflow_dispatch do Main Smoke CI e investigar gatilho de push na main.",
        )

    latest = matching[0]
    run_id = latest.get("id")
    conclusion = latest.get("conclusion")
    status = latest.get("status")
    created_at = latest.get("created_at")
    html_url = latest.get("html_url")
    head_sha = latest.get("head_sha")

    artifacts_payload = _api_get(repo, f"/actions/runs/{run_id}/artifacts?per_page=100", token)
    artifacts = artifacts_payload.get("artifacts", [])
    artifact = next((item for item in artifacts if item.get("name") == artifact_name), None)

    age_warning = False
    if created_at:
        # Formato GitHub: 2026-06-23T16:02:27Z
        try:
            created_epoch = time.mktime(time.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ"))
            age_hours = max(0.0, (time.time() - created_epoch) / 3600)
            age_warning = age_hours > max_age_hours
        except ValueError:
            age_hours = None
    else:
        age_hours = None

    ok = status == "completed" and conclusion == "success" and artifact is not None and not age_warning
    severity = "info" if ok else "critical"
    result_status = "passed" if ok else "failed"
    recommendation = "Manter como evidência pós-merge da main."
    if not ok:
        recommendation = "Corrigir Main Smoke CI, garantir conclusão success e artifact main-smoke-ci-evidence recente."

    return CheckResult(
        name="main_smoke_ci",
        status=result_status,
        severity=severity,
        evidence={
            "workflow_name": workflow_name,
            "run_id": run_id,
            "html_url": html_url,
            "status": status,
            "conclusion": conclusion,
            "head_sha": head_sha,
            "created_at": created_at,
            "age_hours": age_hours,
            "max_age_hours": max_age_hours,
            "artifact_name": artifact_name,
            "artifact_found": artifact is not None,
            "artifact_id": artifact.get("id") if artifact else None,
        },
        recommendation=recommendation,
    )


def check_duplicate_prs(repo: str, token: str | None) -> CheckResult:
    pulls = _api_get(repo, "/pulls?state=open&per_page=100", token)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pr in pulls:
        grouped[_normalize_title(pr.get("title", ""))].append(
            {
                "number": pr.get("number"),
                "title": pr.get("title"),
                "draft": pr.get("draft"),
                "html_url": pr.get("html_url"),
                "updated_at": pr.get("updated_at"),
            }
        )

    duplicates = [items for items in grouped.values() if len(items) > 1]
    flat_duplicates = [item for group in duplicates for item in group]
    status = "passed" if not duplicates else "warning"
    severity = "info" if not duplicates else "medium"

    return CheckResult(
        name="duplicate_open_prs",
        status=status,
        severity=severity,
        evidence={
            "open_pr_count": len(pulls),
            "duplicate_groups": duplicates,
            "duplicate_pr_numbers": [item["number"] for item in flat_duplicates],
        },
        recommendation=(
            "Sem duplicidade por título."
            if not duplicates
            else "Fechar PRs duplicados/obsoletos e manter apenas o PR mais recente ou mais completo por tema."
        ),
    )


def check_risky_open_prs(repo: str, token: str | None) -> CheckResult:
    pulls = _api_get(repo, "/pulls?state=open&per_page=100", token)
    risky_terms = ("workflow", "actions", "deploy", "fly", "security", "runtime", "promotion", "governance")
    risky = []
    for pr in pulls:
        title = pr.get("title", "").lower()
        body = (pr.get("body") or "").lower()
        if any(term in title or term in body for term in risky_terms):
            risky.append(
                {
                    "number": pr.get("number"),
                    "title": pr.get("title"),
                    "draft": pr.get("draft"),
                    "html_url": pr.get("html_url"),
                }
            )

    return CheckResult(
        name="risky_open_prs",
        status="warning" if risky else "passed",
        severity="medium" if risky else "info",
        evidence={"risky_open_prs": risky, "count": len(risky)},
        recommendation=(
            "Exigir revisão governada, CI verde e artifact para PRs de workflows, deploy, runtime ou segurança."
            if risky
            else "Nenhum PR aberto de risco elevado identificado por heurística."
        ),
    )


def write_outputs(results: list[CheckResult], output_dir: Path, repo: str) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    critical_failures = [item for item in results if item.severity == "critical" and item.status != "passed"]
    warnings = [item for item in results if item.status == "warning"]

    payload = {
        "repo": repo,
        "generated_at_epoch": int(time.time()),
        "overall_status": "failed" if critical_failures else "warning" if warnings else "passed",
        "critical_failure_count": len(critical_failures),
        "warning_count": len(warnings),
        "results": [asdict(item) for item in results],
    }

    (output_dir / "repository-health-report.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    lines = [
        "# Repository Health Watchdog",
        "",
        f"Repositório: `{repo}`",
        f"Status geral: **{payload['overall_status']}**",
        "",
        "| Check | Status | Severidade | Recomendação |",
        "|---|---|---|---|",
    ]
    for result in results:
        lines.append(
            f"| {result.name} | {result.status} | {result.severity} | {result.recommendation} |"
        )
    lines.extend(
        [
            "",
            "## Política operacional",
            "",
            "Este monitor é somente leitura. Não fecha PR, não aprova, não faz merge, não executa deploy e não altera produção.",
        ]
    )
    (output_dir / "repository-health-summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 1 if critical_failures else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ReqSys Repository Health Watchdog")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"))
    parser.add_argument("--output-dir", default="artifacts/repository-health-watchdog")
    parser.add_argument("--main-workflow-name", default="Main Smoke CI")
    parser.add_argument("--required-artifact", default="main-smoke-ci-evidence")
    parser.add_argument("--max-age-hours", type=int, default=24)
    parser.add_argument("--fail-on-critical", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.repo:
        print("ERRO: --repo ou GITHUB_REPOSITORY é obrigatório", file=sys.stderr)
        return 2

    results = [
        check_main_smoke(
            args.repo,
            args.token,
            args.main_workflow_name,
            args.required_artifact,
            args.max_age_hours,
        ),
        check_duplicate_prs(args.repo, args.token),
        check_risky_open_prs(args.repo, args.token),
    ]
    exit_code = write_outputs(results, Path(args.output_dir), args.repo)
    if args.fail_on_critical:
        return exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
