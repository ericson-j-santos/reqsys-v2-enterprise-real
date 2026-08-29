#!/usr/bin/env python3
"""Ciclo governado de tratamento de CI para pull requests.

Objetivos:
- localizar PRs abertos com workflows concluídos em falha;
- classificar falha transitória versus determinística/alto risco;
- reexecutar somente falhas transitórias explicitamente permitidas;
- limitar tentativas e impedir loops;
- registrar envelhecimento e estado operacional em relatório/labels.

O script não altera regra de negócio, segredos, banco, segurança nem faz merge.
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
from urllib.parse import urlencode
from urllib.request import Request, urlopen

LABEL_COLORS = {
    "ci:falhou": "d73a4a",
    "ci:em-tratamento": "fbca04",
    "ci:recuperado": "0e8a16",
    "ci:intervencao-necessaria": "b60205",
    "ci:falha-transitoria": "1d76db",
    "ci:parado": "e99695",
}
MANAGED_LABELS = set(LABEL_COLORS)


@dataclass(frozen=True)
class PullRequest:
    number: int
    title: str
    html_url: str
    head_sha: str
    head_ref: str


@dataclass(frozen=True)
class WorkflowRun:
    id: int
    name: str
    conclusion: str
    run_attempt: int
    html_url: str
    updated_at: str


@dataclass(frozen=True)
class RemediationDecision:
    pr_number: int
    pr_url: str
    head_sha: str
    workflow_name: str
    run_id: int
    run_url: str
    conclusion: str
    age_minutes: int
    state: str
    action: str
    reason: str
    rerun_executed: bool


def github_request(method: str, url: str, token: str, payload: Any | None = None) -> Any:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(
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
        with urlopen(req, timeout=30) as response:  # noqa: S310 - GitHub URL controlada.
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {exc.code} em {method} {url}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Falha de conexão com GitHub em {method} {url}: {exc}") from exc


def api(repo: str, path: str) -> str:
    return f"https://api.github.com/repos/{repo}/{path.lstrip('/')}"


def load_policy(path: Path) -> dict[str, Any]:
    policy = json.loads(path.read_text(encoding="utf-8"))
    required = {"max_rerun_attempts", "age_thresholds_minutes", "transient_conclusions", "rerun_allowlist", "never_auto_remediate_keywords", "labels"}
    missing = required - set(policy)
    if missing:
        raise ValueError(f"Política incompleta: {sorted(missing)}")
    return policy


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def age_minutes(updated_at: str, now: datetime | None = None) -> int:
    current = now or datetime.now(timezone.utc)
    return max(0, int((current - parse_timestamp(updated_at)).total_seconds() // 60))


def fetch_open_prs(repo: str, token: str) -> list[PullRequest]:
    payload = github_request("GET", api(repo, "pulls?state=open&per_page=100"), token)
    return [
        PullRequest(
            number=int(item["number"]),
            title=item.get("title") or "",
            html_url=item.get("html_url") or "",
            head_sha=item["head"]["sha"],
            head_ref=item["head"]["ref"],
        )
        for item in payload
        if item.get("head", {}).get("repo", {}).get("full_name") == repo
    ]


def fetch_runs_for_sha(repo: str, token: str, sha: str) -> list[WorkflowRun]:
    query = urlencode({"head_sha": sha, "event": "pull_request", "status": "completed", "per_page": 100})
    payload = github_request("GET", api(repo, f"actions/runs?{query}"), token)
    runs: list[WorkflowRun] = []
    for item in payload.get("workflow_runs", []):
        conclusion = item.get("conclusion") or "unknown"
        runs.append(
            WorkflowRun(
                id=int(item["id"]),
                name=item.get("name") or "",
                conclusion=conclusion,
                run_attempt=int(item.get("run_attempt") or 1),
                html_url=item.get("html_url") or "",
                updated_at=item.get("updated_at") or item.get("created_at") or datetime.now(timezone.utc).isoformat(),
            )
        )
    return runs


def latest_by_workflow(runs: list[WorkflowRun]) -> list[WorkflowRun]:
    latest: dict[str, WorkflowRun] = {}
    for run in sorted(runs, key=lambda item: (item.updated_at, item.id), reverse=True):
        latest.setdefault(run.name, run)
    return list(latest.values())


def classify(run: WorkflowRun, policy: dict[str, Any], *, now: datetime | None = None) -> tuple[str, str, str, int]:
    age = age_minutes(run.updated_at, now)
    lowered = run.name.lower()
    blocked = any(keyword.lower() in lowered for keyword in policy["never_auto_remediate_keywords"])
    allowlisted = run.name in set(policy["rerun_allowlist"])
    transient = run.conclusion in set(policy["transient_conclusions"])
    max_attempts = int(policy["max_rerun_attempts"])

    if run.conclusion in {"success", "neutral", "skipped"}:
        return "CI_OK", "none", "workflow_ok", age
    if blocked:
        return "INTERVENCAO_NECESSARIA", "escalate", "workflow_high_risk", age
    if run.run_attempt >= max_attempts:
        return "INTERVENCAO_NECESSARIA", "escalate", "max_attempts_reached", age
    if transient and allowlisted:
        return "CORRECAO_AUTOMATICA", "rerun_failed_jobs", "transient_allowlisted", age
    if transient:
        return "INTERVENCAO_NECESSARIA", "escalate", "transient_not_allowlisted", age
    return "INTERVENCAO_NECESSARIA", "escalate", "deterministic_or_unknown", age


def desired_labels(decisions: list[RemediationDecision], policy: dict[str, Any]) -> set[str]:
    if not decisions:
        return {policy["labels"]["recovered"]}
    labels = {policy["labels"]["failed"]}
    if any(item.action == "rerun_failed_jobs" for item in decisions):
        labels |= {policy["labels"]["handling"], policy["labels"]["transient"]}
    if any(item.action == "escalate" for item in decisions):
        labels.add(policy["labels"]["human"])
    stalled = int(policy["age_thresholds_minutes"]["stalled"])
    if any(item.age_minutes >= stalled for item in decisions):
        labels.add(policy["labels"]["stalled"])
    return labels


def ensure_labels(repo: str, token: str) -> None:
    for name, color in LABEL_COLORS.items():
        try:
            github_request("POST", api(repo, "labels"), token, {"name": name, "color": color})
        except RuntimeError as exc:
            if "422" not in str(exc):
                raise


def replace_managed_labels(repo: str, token: str, pr_number: int, desired: set[str]) -> None:
    issue = github_request("GET", api(repo, f"issues/{pr_number}"), token)
    current = {label["name"] for label in issue.get("labels", [])}
    next_labels = sorted((current - MANAGED_LABELS) | desired)
    github_request("POST", api(repo, f"issues/{pr_number}/labels"), token, {"labels": next_labels})


def rerun_failed_jobs(repo: str, token: str, run_id: int) -> None:
    github_request("POST", api(repo, f"actions/runs/{run_id}/rerun-failed-jobs"), token)


def build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# PR CI Remediation",
        "",
        f"Gerado em: `{report['generated_at']}`",
        f"Modo execução: `{report['execute']}`",
        f"PRs analisados: `{report['prs_scanned']}`",
        f"PRs com falha: `{report['prs_with_failures']}`",
        f"Reexecuções disparadas: `{report['reruns_executed']}`",
        f"Intervenções necessárias: `{report['human_interventions']}`",
        "",
        "## Decisões",
        "",
    ]
    if not report["decisions"]:
        lines.append("- Nenhuma falha ativa encontrada.")
    for item in report["decisions"]:
        lines.append(
            f"- PR #{item['pr_number']} — `{item['workflow_name']}` — `{item['state']}` — "
            f"ação `{item['action']}` — idade `{item['age_minutes']} min` — {item['run_url']}"
        )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ciclo governado de tratamento de CI em PRs.")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--policy", default=".github/ci-remediation.json")
    parser.add_argument("--output-dir", default="artifacts/pr-ci-remediation")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--skip-labels", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    if not token or not args.repo:
        print("GITHUB_TOKEN e --repo/GITHUB_REPOSITORY são obrigatórios", file=sys.stderr)
        return 2

    policy = load_policy(Path(args.policy))
    prs = fetch_open_prs(args.repo, token)
    all_decisions: list[RemediationDecision] = []
    reruns = 0
    interventions = 0

    if args.execute and not args.skip_labels:
        ensure_labels(args.repo, token)

    for pr in prs:
        failed_runs = [
            run for run in latest_by_workflow(fetch_runs_for_sha(args.repo, token, pr.head_sha))
            if run.conclusion not in {"success", "neutral", "skipped"}
        ]
        pr_decisions: list[RemediationDecision] = []
        for run in failed_runs:
            state, action, reason, age = classify(run, policy)
            executed = False
            if args.execute and action == "rerun_failed_jobs":
                rerun_failed_jobs(args.repo, token, run.id)
                executed = True
                reruns += 1
            if action == "escalate":
                interventions += 1
            pr_decisions.append(
                RemediationDecision(
                    pr_number=pr.number,
                    pr_url=pr.html_url,
                    head_sha=pr.head_sha,
                    workflow_name=run.name,
                    run_id=run.id,
                    run_url=run.html_url,
                    conclusion=run.conclusion,
                    age_minutes=age,
                    state=state,
                    action=action,
                    reason=reason,
                    rerun_executed=executed,
                )
            )
        all_decisions.extend(pr_decisions)
        if args.execute and not args.skip_labels:
            replace_managed_labels(args.repo, token, pr.number, desired_labels(pr_decisions, policy))

    report = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "execute": bool(args.execute),
        "prs_scanned": len(prs),
        "prs_with_failures": len({item.pr_number for item in all_decisions}),
        "reruns_executed": reruns,
        "human_interventions": interventions,
        "decisions": [asdict(item) for item in all_decisions],
    }
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output / "summary.md").write_text(build_markdown(report), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
