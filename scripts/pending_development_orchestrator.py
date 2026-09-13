#!/usr/bin/env python3
"""Pending Development Orchestrator for ReqSys.

Discovers explicitly automatable pending work and routes it through existing
ReqSys governance instead of implementing a second delivery pipeline.

Routes:
- CI/transient failures -> Actions Auto Operator;
- issue-backed development -> GitHub Copilot coding agent;
- deterministic CI failures on eligible PRs -> @copilot on the same PR;
- sensitive/high-risk work -> human gate (report-only).

Execution is fail-closed. Copilot routes require COPILOT_AGENT_TOKEN, which
must be provisioned as a repository secret and is never logged.
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
from uuid import uuid4

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.coordenador_status_consolidator import evaluate_increment_intent  # noqa: E402
from scripts.governed_pr_increment_gate import infer_increment_from_pr  # noqa: E402

AUTO_MARKER = "<!-- pending-development-orchestrator:auto -->"
AUTO_LABEL = "orchestrator:auto"
AUTO_FIX_LABEL = "orchestrator:auto-fix"
HUMAN_GATE_LABEL = "orchestrator:human-gate"
COPILOT_ASSIGNEE = "copilot-swe-agent[bot]"
MAX_COPILOT_FIX_ATTEMPTS = 2
TERMINAL_SUCCESS = {"success", "neutral", "skipped"}
TRANSIENT_CONCLUSIONS = {"cancelled", "timed_out"}

SENSITIVE_HINTS = {
    "production",
    "produção",
    "producao",
    "prod deploy",
    "deploy prod",
    "secret",
    "segredo",
    "token",
    "password",
    "senha",
    "key vault",
    "entra permission",
    "permissão administrativa",
    "permissao administrativa",
    "branch protection",
    "force-push",
    "force push",
    "drop table",
    "truncate",
    "delete database",
    "excluir banco",
    "purge",
    "merge automático",
    "merge automatico",
}

CI_HINTS = {
    "ci",
    "workflow",
    "github actions",
    "check",
    "pipeline",
}

FAILURE_HINTS = {
    "falha",
    "falhou",
    "erro",
    "error",
    "failed",
    "quebrado",
    "broken",
    "timeout",
}


@dataclass(frozen=True)
class Decision:
    kind: str
    number: int
    title: str
    route: str
    status: str
    reason: str
    risk: str
    increment_type: str | None = None
    gate_reason: str | None = None
    action_executed: bool = False
    url: str = ""
    head_sha: str | None = None


class GitHubApiError(RuntimeError):
    pass


class GitHubClient:
    def __init__(self, repo: str, github_token: str, copilot_token: str = "") -> None:
        self.repo = repo
        self.github_token = github_token
        self.copilot_token = copilot_token
        self.api_base = f"https://api.github.com/repos/{repo}"

    def request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        selected_token = token if token is not None else self.github_token
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.api_base}/{path.lstrip('/')}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {selected_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:  # noqa: S310 - GitHub API only.
                body = response.read().decode("utf-8")
                return json.loads(body) if body else {}
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise GitHubApiError(
                f"GitHub API error {exc.code} for {method} {path}: {body[:500]}"
            ) from exc
        except URLError as exc:
            raise GitHubApiError(f"GitHub API connection error for {method} {path}: {exc}") from exc

    def paginate(self, path: str, *, token: str | None = None, limit_pages: int = 5) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        separator = "&" if "?" in path else "?"
        for page in range(1, limit_pages + 1):
            payload = self.request("GET", f"{path}{separator}per_page=100&page={page}", token=token)
            if not isinstance(payload, list):
                raise GitHubApiError(f"Resposta inesperada em {path}: esperado array")
            items.extend(payload)
            if len(payload) < 100:
                break
        return items

    def list_open_issues(self) -> list[dict[str, Any]]:
        return self.paginate("issues?state=open")

    def get_issue(self, number: int) -> dict[str, Any]:
        payload = self.request("GET", f"issues/{number}")
        if not isinstance(payload, dict):
            raise GitHubApiError(f"Issue #{number}: resposta inesperada")
        return payload

    def list_open_pulls(self) -> list[dict[str, Any]]:
        return self.paginate("pulls?state=open&sort=updated&direction=desc")

    def list_pr_runs(self, head_sha: str) -> list[dict[str, Any]]:
        query = urlencode({"head_sha": head_sha, "event": "pull_request", "per_page": 100})
        payload = self.request("GET", f"actions/runs?{query}")
        return list(payload.get("workflow_runs") or []) if isinstance(payload, dict) else []

    def list_comments(self, number: int, *, use_copilot_token: bool = False) -> list[dict[str, Any]]:
        token = self.copilot_token if use_copilot_token and self.copilot_token else None
        return self.paginate(f"issues/{number}/comments", token=token, limit_pages=2)

    def dispatch_auto_operator(self, base_branch: str) -> None:
        self.request(
            "POST",
            "actions/workflows/actions-auto-operator.yml/dispatches",
            payload={"ref": base_branch, "inputs": {"mode": "execute", "branch": base_branch}},
        )

    def assign_copilot(self, number: int, base_branch: str, instructions: str) -> None:
        if not self.copilot_token:
            raise GitHubApiError("COPILOT_AGENT_TOKEN ausente")
        self.request(
            "POST",
            f"issues/{number}/assignees",
            token=self.copilot_token,
            payload={
                "assignees": [COPILOT_ASSIGNEE],
                "agent_assignment": {
                    "target_repo": self.repo,
                    "base_branch": base_branch,
                    "custom_instructions": instructions,
                    "custom_agent": "",
                    "model": "",
                },
            },
        )

    def ask_copilot_to_fix_pr(self, number: int, head_sha: str, failing_runs: list[dict[str, Any]]) -> None:
        if not self.copilot_token:
            raise GitHubApiError("COPILOT_AGENT_TOKEN ausente")
        marker = copilot_fix_marker(head_sha)
        failures = ", ".join(sorted({str(item.get("name") or "workflow") for item in failing_runs}))
        body = (
            f"{marker}\n"
            "@copilot Corrija a causa raiz dos checks de CI que falharam neste PR, mantendo a correção no mesmo PR. "
            "Aplique a menor alteração possível, preserve o escopo existente, execute os testes aplicáveis e não faça merge, "
            "deploy de produção, alteração de segredos, permissões administrativas ou branch protection. "
            f"HEAD observado: `{head_sha}`. Workflows com falha: {failures or 'não identificados'}."
        )
        self.request(
            "POST",
            f"issues/{number}/comments",
            token=self.copilot_token,
            payload={"body": body},
        )


def _label_names(item: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for label in item.get("labels") or []:
        if isinstance(label, str):
            result.add(label.strip().lower())
        elif isinstance(label, dict) and label.get("name"):
            result.add(str(label["name"]).strip().lower())
    return result


def _assignee_names(item: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for assignee in item.get("assignees") or []:
        if isinstance(assignee, dict) and assignee.get("login"):
            result.add(str(assignee["login"]).lower())
    return result


def _combined_text(item: dict[str, Any]) -> str:
    labels = " ".join(sorted(_label_names(item)))
    return f"{item.get('title') or ''}\n{item.get('body') or ''}\n{labels}".lower()


def is_issue_candidate(issue: dict[str, Any], *, explicitly_selected: bool = False) -> bool:
    if issue.get("pull_request"):
        return False
    if explicitly_selected:
        return True
    title = str(issue.get("title") or "")
    body = str(issue.get("body") or "")
    labels = _label_names(issue)
    return AUTO_MARKER in body or AUTO_LABEL in labels or title.upper().startswith("[AUTO-NEXT]")


def classify_risk(item: dict[str, Any]) -> tuple[str, str]:
    labels = _label_names(item)
    if HUMAN_GATE_LABEL in labels:
        return "high", "explicit_human_gate_label"
    text = _combined_text(item)
    matched = sorted(hint for hint in SENSITIVE_HINTS if hint in text)
    if matched:
        return "high", f"sensitive_hint:{matched[0]}"
    return "standard", "no_sensitive_hint"


def looks_like_ci_failure(item: dict[str, Any]) -> bool:
    text = _combined_text(item)
    return any(hint in text for hint in CI_HINTS) and any(hint in text for hint in FAILURE_HINTS)


def infer_increment(item: dict[str, Any], head_ref: str = "") -> dict[str, Any]:
    return infer_increment_from_pr(
        title=str(item.get("title") or ""),
        body=str(item.get("body") or ""),
        labels=sorted(_label_names(item)),
        head_ref=head_ref,
    )


def evaluate_gate(status_report: dict[str, Any], item: dict[str, Any], head_ref: str = "") -> dict[str, Any]:
    inferred = infer_increment(item, head_ref=head_ref)
    increment_type = str(inferred["increment_type"])
    reference = str(inferred.get("reference") or "")
    allowed, reason, detail = evaluate_increment_intent(status_report, increment_type, reference)
    return {
        "allowed": allowed,
        "reason": reason,
        "detail": detail,
        "increment_type": increment_type,
        "reference": reference or None,
        "inference_source": inferred.get("inference_source"),
    }


def copilot_fix_marker(head_sha: str) -> str:
    return f"<!-- pending-development-orchestrator:copilot-fix:{head_sha} -->"


def latest_runs_by_name(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for run in runs:
        name = str(run.get("name") or "")
        existing = latest.get(name)
        if existing is None or str(run.get("created_at") or "") > str(existing.get("created_at") or ""):
            latest[name] = run
    return list(latest.values())


def failing_runs_for_pr(runs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    failures: list[dict[str, Any]] = []
    transient: list[dict[str, Any]] = []
    for run in latest_runs_by_name(runs):
        if run.get("status") != "completed":
            continue
        conclusion = str(run.get("conclusion") or "")
        if conclusion in TERMINAL_SUCCESS:
            continue
        if conclusion in TRANSIENT_CONCLUSIONS:
            transient.append(run)
        else:
            failures.append(run)
    return failures, transient


def pr_is_candidate(pr: dict[str, Any]) -> bool:
    labels = _label_names(pr)
    head_ref = str((pr.get("head") or {}).get("ref") or "")
    return AUTO_FIX_LABEL in labels or head_ref.startswith("copilot/")


def _issue_url(item: dict[str, Any]) -> str:
    return str(item.get("html_url") or "")


def process_issue(
    client: GitHubClient,
    issue: dict[str, Any],
    status_report: dict[str, Any],
    *,
    execute: bool,
    base_branch: str,
    dispatched_routes: set[str],
) -> Decision:
    number = int(issue["number"])
    title = str(issue.get("title") or "")
    risk, risk_reason = classify_risk(issue)
    gate = evaluate_gate(status_report, issue)
    if risk == "high":
        return Decision("issue", number, title, "human_gate", "blocked", risk_reason, risk, gate["increment_type"], gate["reason"], url=_issue_url(issue))
    if not gate["allowed"]:
        return Decision("issue", number, title, "operational_gate", "blocked", str(gate["detail"]), risk, gate["increment_type"], gate["reason"], url=_issue_url(issue))

    if looks_like_ci_failure(issue):
        route = "actions_auto_operator"
        if not execute:
            return Decision("issue", number, title, route, "planned", "ci_failure_detected", risk, gate["increment_type"], gate["reason"], url=_issue_url(issue))
        if route in dispatched_routes:
            return Decision("issue", number, title, route, "already_dispatched", "deduplicated_in_current_run", risk, gate["increment_type"], gate["reason"], url=_issue_url(issue))
        client.dispatch_auto_operator(base_branch)
        dispatched_routes.add(route)
        return Decision("issue", number, title, route, "dispatched", "ci_failure_detected", risk, gate["increment_type"], gate["reason"], True, url=_issue_url(issue))

    route = "copilot_issue_agent"
    if COPILOT_ASSIGNEE.lower() in _assignee_names(issue):
        return Decision("issue", number, title, route, "already_dispatched", "copilot_already_assigned", risk, gate["increment_type"], gate["reason"], url=_issue_url(issue))
    if not execute:
        return Decision("issue", number, title, route, "planned", "eligible_issue_backed_development", risk, gate["increment_type"], gate["reason"], url=_issue_url(issue))
    if not client.copilot_token:
        return Decision("issue", number, title, route, "blocked", "missing_copilot_agent_token", risk, gate["increment_type"], gate["reason"], url=_issue_url(issue))

    instructions = (
        "Siga AGENTS.md e as regras operacionais do ReqSys. Preserve o escopo da issue, faça a menor implementação real, "
        "inclua testes automatizados e validação ponta a ponta aplicável, use branch isolada e não faça merge, deploy de produção, "
        "mudança de segredos, permissões administrativas ou branch protection. Antes da PR, respeite o Pre-PR Readiness Gate."
    )
    client.assign_copilot(number, base_branch, instructions)
    return Decision("issue", number, title, route, "dispatched", "eligible_issue_backed_development", risk, gate["increment_type"], gate["reason"], True, url=_issue_url(issue))


def process_pr(
    client: GitHubClient,
    pr: dict[str, Any],
    status_report: dict[str, Any],
    *,
    execute: bool,
    base_branch: str,
    dispatched_routes: set[str],
) -> Decision | None:
    number = int(pr["number"])
    title = str(pr.get("title") or "")
    head = pr.get("head") or {}
    head_sha = str(head.get("sha") or "")
    head_ref = str(head.get("ref") or "")
    risk, risk_reason = classify_risk(pr)
    gate = evaluate_gate(status_report, pr, head_ref=head_ref)

    runs = client.list_pr_runs(head_sha)
    failures, transient = failing_runs_for_pr(runs)
    if not failures and not transient:
        return None
    if risk == "high":
        return Decision("pull_request", number, title, "human_gate", "blocked", risk_reason, risk, gate["increment_type"], gate["reason"], url=_issue_url(pr), head_sha=head_sha)
    if not gate["allowed"]:
        return Decision("pull_request", number, title, "operational_gate", "blocked", str(gate["detail"]), risk, gate["increment_type"], gate["reason"], url=_issue_url(pr), head_sha=head_sha)

    if not failures and transient:
        route = "actions_auto_operator"
        if not execute:
            return Decision("pull_request", number, title, route, "planned", "transient_pr_failure", risk, gate["increment_type"], gate["reason"], url=_issue_url(pr), head_sha=head_sha)
        if route not in dispatched_routes:
            client.dispatch_auto_operator(base_branch)
            dispatched_routes.add(route)
            return Decision("pull_request", number, title, route, "dispatched", "transient_pr_failure", risk, gate["increment_type"], gate["reason"], True, url=_issue_url(pr), head_sha=head_sha)
        return Decision("pull_request", number, title, route, "already_dispatched", "deduplicated_in_current_run", risk, gate["increment_type"], gate["reason"], url=_issue_url(pr), head_sha=head_sha)

    route = "copilot_same_pr_fix"
    marker = copilot_fix_marker(head_sha)
    comments = client.list_comments(number, use_copilot_token=bool(client.copilot_token))
    matching = [comment for comment in comments if marker in str(comment.get("body") or "")]
    prior_attempts = sum(
        1
        for comment in comments
        if "<!-- pending-development-orchestrator:copilot-fix:" in str(comment.get("body") or "")
    )
    if matching:
        return Decision("pull_request", number, title, route, "already_dispatched", "same_head_already_requested", risk, gate["increment_type"], gate["reason"], url=_issue_url(pr), head_sha=head_sha)
    if prior_attempts >= MAX_COPILOT_FIX_ATTEMPTS:
        return Decision("pull_request", number, title, "human_gate", "blocked", "max_copilot_fix_attempts_reached", "high", gate["increment_type"], gate["reason"], url=_issue_url(pr), head_sha=head_sha)
    if not execute:
        return Decision("pull_request", number, title, route, "planned", "deterministic_pr_failure", risk, gate["increment_type"], gate["reason"], url=_issue_url(pr), head_sha=head_sha)
    if not client.copilot_token:
        return Decision("pull_request", number, title, route, "blocked", "missing_copilot_agent_token", risk, gate["increment_type"], gate["reason"], url=_issue_url(pr), head_sha=head_sha)

    client.ask_copilot_to_fix_pr(number, head_sha, failures)
    return Decision("pull_request", number, title, route, "dispatched", "deterministic_pr_failure", risk, gate["increment_type"], gate["reason"], True, url=_issue_url(pr), head_sha=head_sha)


def build_report(
    repo: str,
    base_branch: str,
    mode: str,
    correlation_id: str,
    decisions: list[Decision],
) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "correlation_id": correlation_id,
        "repository": repo,
        "base_branch": base_branch,
        "mode": mode,
        "summary": {
            "evaluated": len(decisions),
            "dispatched": sum(1 for item in decisions if item.action_executed),
            "blocked": sum(1 for item in decisions if item.status == "blocked"),
            "already_dispatched": sum(1 for item in decisions if item.status == "already_dispatched"),
            "planned": sum(1 for item in decisions if item.status == "planned"),
        },
        "decisions": [asdict(item) for item in decisions],
        "guardrails": [
            "explicit_issue_marker_or_label",
            "copilot_prs_or_explicit_auto_fix_label_only",
            "existing_agent_increment_gate",
            "high_risk_human_gate",
            "copilot_token_never_logged",
            "same_pr_fix_for_deterministic_ci",
            "transient_ci_reuses_actions_auto_operator",
            "maximum_two_copilot_fix_attempts_per_pr",
            "no_merge_no_prod_deploy_no_secret_or_admin_change",
        ],
    }


def write_report(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "pending-development-orchestrator.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    summary = report["summary"]
    lines = [
        "# Pending Development Orchestrator",
        "",
        f"- Correlation ID: `{report['correlation_id']}`",
        f"- Mode: `{report['mode']}`",
        f"- Repository: `{report['repository']}`",
        f"- Base branch: `{report['base_branch']}`",
        f"- Evaluated: `{summary['evaluated']}`",
        f"- Dispatched: `{summary['dispatched']}`",
        f"- Blocked: `{summary['blocked']}`",
        f"- Already dispatched: `{summary['already_dispatched']}`",
        "",
        "| Kind | Item | Route | Status | Reason |",
        "|---|---|---|---|---|",
    ]
    for item in report["decisions"]:
        ref = f"#{item['number']}"
        lines.append(
            f"| {item['kind']} | {ref} | `{item['route']}` | `{item['status']}` | {item['reason']} |"
        )
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Orquestrador governado de desenvolvimento pendente.")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--base-branch", default="main")
    parser.add_argument("--mode", choices=("audit", "execute"), default="audit")
    parser.add_argument("--status-json", required=True)
    parser.add_argument("--max-items", type=int, default=5)
    parser.add_argument("--issue-number", type=int, default=0)
    parser.add_argument("--output-dir", default="artifacts/pending-development-orchestrator")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    github_token = os.environ.get("GITHUB_TOKEN", "")
    copilot_token = os.environ.get("COPILOT_AGENT_TOKEN", "")
    if not args.repo:
        print("--repo ou GITHUB_REPOSITORY é obrigatório", file=sys.stderr)
        return 2
    if not github_token:
        print("GITHUB_TOKEN é obrigatório", file=sys.stderr)
        return 2

    status_path = Path(args.status_json)
    if not status_path.exists():
        print(f"Status consolidado não encontrado: {status_path}", file=sys.stderr)
        return 2
    status_report = json.loads(status_path.read_text(encoding="utf-8"))

    correlation_id = os.environ.get("GITHUB_RUN_ID") or str(uuid4())
    client = GitHubClient(args.repo, github_token, copilot_token)
    execute = args.mode == "execute"
    decisions: list[Decision] = []
    dispatched_routes: set[str] = set()

    try:
        if args.issue_number:
            issue = client.get_issue(args.issue_number)
            if issue.get("pull_request"):
                pulls = [pr for pr in client.list_open_pulls() if int(pr.get("number") or 0) == args.issue_number]
                if not pulls:
                    raise GitHubApiError(f"PR #{args.issue_number} não está aberto")
                decision = process_pr(
                    client,
                    pulls[0],
                    status_report,
                    execute=execute,
                    base_branch=args.base_branch,
                    dispatched_routes=dispatched_routes,
                )
                if decision:
                    decisions.append(decision)
            elif is_issue_candidate(issue, explicitly_selected=True):
                decisions.append(
                    process_issue(
                        client,
                        issue,
                        status_report,
                        execute=execute,
                        base_branch=args.base_branch,
                        dispatched_routes=dispatched_routes,
                    )
                )
        else:
            issues = [item for item in client.list_open_issues() if is_issue_candidate(item)]
            for issue in issues[: max(0, args.max_items)]:
                decisions.append(
                    process_issue(
                        client,
                        issue,
                        status_report,
                        execute=execute,
                        base_branch=args.base_branch,
                        dispatched_routes=dispatched_routes,
                    )
                )

            remaining = max(0, args.max_items - len(decisions))
            if remaining:
                pulls = [pr for pr in client.list_open_pulls() if pr_is_candidate(pr)]
                for pr in pulls[:remaining]:
                    decision = process_pr(
                        client,
                        pr,
                        status_report,
                        execute=execute,
                        base_branch=args.base_branch,
                        dispatched_routes=dispatched_routes,
                    )
                    if decision:
                        decisions.append(decision)
    except (GitHubApiError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    report = build_report(args.repo, args.base_branch, args.mode, correlation_id, decisions)
    write_report(report, Path(args.output_dir))
    print(json.dumps(report, indent=2, ensure_ascii=False))

    missing_token_block = any(
        item.status == "blocked" and item.reason == "missing_copilot_agent_token" for item in decisions
    )
    return 2 if execute and missing_token_block else 0


if __name__ == "__main__":
    raise SystemExit(main())
