#!/usr/bin/env python3
"""Open or update a draft PR for Cloud Agent / cursor/* branches via GitHub REST API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode


PRE_PR_WORKFLOW = "pre-pr-readiness.yml"


def build_body(branch: str, base: str, head_sha: str | None = None) -> str:
    repo = os.environ.get("GITHUB_REPOSITORY", "ericson-j-santos/reqsys-v2-enterprise-real")
    head_sha = (
        head_sha
        or os.environ.get("READY_FOR_PR_HEAD_SHA")
        or os.environ.get("GITHUB_SHA")
        or "local"
    ).strip()
    run_id = os.environ.get("GITHUB_RUN_ID", "local")
    return f"""## Resumo

PR aberto automaticamente pelo workflow **Padrão Ouro Delivery Automation** para a branch `{branch}`.

## Escopo

- Ciclo 0: runtime `/api/runtime/*`, baseline de artifacts operacionais
- Ciclo 1: CI Intelligence P1 (Pareto + histórico)
- Ciclo 2: cards de governança + pipeline-governanca no CI
- Ciclo 3: Estatísticas v2 fase 2 + hook pós-workflow evidence

## Metadados operacionais

- Branch: `{branch}`
- Base: `{base}`
- SHA: `{head_sha}`
- Run: `{run_id}`
- Repositório: `{repo}`

increment-type: consolidate

## Evidências esperadas

- CI — ReqSys v2 Enterprise (verde)
- Pipeline Governança + Evidence Snapshot
- ReqSys Fly Runtime P0 (smoke público após deploy)
"""


def append_readiness_body(body: str, evidence: dict[str, Any]) -> str:
    return (
        body.rstrip()
        + "\n\n## READY_FOR_PR\n\n"
        + f"- Status: `passed`\n"
        + f"- Head SHA: `{evidence['head_sha']}`\n"
        + f"- Base SHA: `{evidence['base_sha']}`\n"
        + f"- Run: `{evidence['run_id']}`\n"
        + f"- Run URL: {evidence['run_url']}\n"
    )


def branch_metadata_slug(branch: str) -> str:
    return branch.replace("/", "-")


def load_branch_pr_metadata(branch: str) -> dict[str, str] | None:
    path = Path(".github/pr-metadata") / f"{branch_metadata_slug(branch)}.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    title = str(payload.get("title") or "").strip()
    body = str(payload.get("body") or "").strip()
    if not title and not body:
        return None
    return {"title": title, "body": body}


class ReadyForPrBlocked(RuntimeError):
    def __init__(self, reason: str, evidence: dict[str, Any] | None = None) -> None:
        super().__init__(reason)
        self.evidence = evidence or {"status": "blocked", "reason": reason}


class GitHubClient:
    def __init__(self, token: str, repository: str) -> None:
        self.token = token
        self.repository = repository

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        url = f"https://api.github.com/repos/{self.repository}{path}"
        data = None
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "reqsys-padrao-ouro-delivery-automation",
        }
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else None
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GitHub API {method} {path} failed ({exc.code}): {detail}") from exc

    def find_existing_pr(self, head: str, base: str) -> dict[str, Any] | None:
        owner = self.repository.split("/")[0]
        for state in ("open", "closed"):
            query = urlencode(
                {
                    "state": state,
                    "head": f"{owner}:{head}",
                    "base": base,
                    "sort": "updated",
                    "direction": "desc",
                    "per_page": "5",
                }
            )
            pulls = self._request("GET", f"/pulls?{query}")
            if isinstance(pulls, list) and pulls:
                return pulls[0]
        return None

    def list_pre_pr_readiness_runs(self, head_sha: str) -> list[dict[str, Any]]:
        query = urlencode({"head_sha": head_sha, "event": "push", "per_page": "20"})
        payload = self._request("GET", f"/actions/workflows/{PRE_PR_WORKFLOW}/runs?{query}")
        if not isinstance(payload, dict):
            return []
        runs = payload.get("workflow_runs")
        return [item for item in runs if isinstance(item, dict)] if isinstance(runs, list) else []

    def get_branch_sha(self, branch: str) -> str:
        payload = self._request("GET", f"/branches/{quote(branch, safe='')}")
        if not isinstance(payload, dict):
            raise RuntimeError(f"Resposta inválida ao consultar branch base: {branch}")
        commit = payload.get("commit")
        if not isinstance(commit, dict) or not str(commit.get("sha") or "").strip():
            raise RuntimeError(f"SHA ausente ao consultar branch base: {branch}")
        return str(commit["sha"])

    def compare(self, base_sha: str, head_sha: str) -> dict[str, Any]:
        payload = self._request("GET", f"/compare/{base_sha}...{head_sha}")
        if not isinstance(payload, dict):
            raise RuntimeError("Resposta inválida ao comparar base e HEAD")
        return payload

    def create_pr(self, *, title: str, body: str, head: str, base: str, draft: bool = True) -> dict[str, Any]:
        return self._request(
            "POST",
            "/pulls",
            {"title": title, "body": body, "head": head, "base": base, "draft": draft},
        )

    def update_pr(self, number: int, *, title: str, body: str) -> dict[str, Any]:
        return self._request("PATCH", f"/pulls/{number}", {"title": title, "body": body})

    def add_labels(self, number: int, labels: list[str]) -> None:
        self._request("POST", f"/issues/{number}/labels", {"labels": labels})


def write_readiness_artifact(evidence: dict[str, Any]) -> Path:
    out_dir = Path(os.environ.get("PR_REQUEST_ARTIFACT_DIR", "artifacts/auto-pr-request"))
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "ready-for-pr-verification.json"
    path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def wait_for_ready_for_pr(
    client: GitHubClient,
    *,
    head_sha: str,
    base: str,
    wait_seconds: float = 600.0,
    poll_seconds: float = 5.0,
) -> dict[str, Any]:
    if not head_sha:
        raise ReadyForPrBlocked("GITHUB_SHA ausente; não é possível vincular READY_FOR_PR ao HEAD atual")

    started = time.monotonic()
    last_run: dict[str, Any] | None = None
    while True:
        runs = [run for run in client.list_pre_pr_readiness_runs(head_sha) if str(run.get("head_sha") or "") == head_sha]
        if runs:
            last_run = runs[0]
            status = str(last_run.get("status") or "")
            conclusion = str(last_run.get("conclusion") or "")
            if status == "completed":
                if conclusion != "success":
                    evidence = {
                        "status": "blocked",
                        "reason": "ready_for_pr_run_not_successful",
                        "head_sha": head_sha,
                        "run_id": last_run.get("id"),
                        "run_url": last_run.get("html_url"),
                        "run_status": status,
                        "run_conclusion": conclusion,
                    }
                    raise ReadyForPrBlocked(
                        f"Pre-PR Readiness Gate não passou para o HEAD atual ({conclusion or 'sem conclusão'})",
                        evidence,
                    )
                break

        elapsed = time.monotonic() - started
        if elapsed >= wait_seconds:
            evidence = {
                "status": "blocked",
                "reason": "ready_for_pr_run_missing_or_pending",
                "head_sha": head_sha,
                "run_id": last_run.get("id") if last_run else None,
                "run_url": last_run.get("html_url") if last_run else None,
                "run_status": last_run.get("status") if last_run else "missing",
                "run_conclusion": last_run.get("conclusion") if last_run else None,
                "wait_seconds": wait_seconds,
            }
            raise ReadyForPrBlocked(
                "Pre-PR Readiness Gate verde não foi encontrado para o HEAD atual dentro do limite",
                evidence,
            )
        time.sleep(max(0.05, min(poll_seconds, wait_seconds - elapsed)))

    base_sha = client.get_branch_sha(base)
    comparison = client.compare(base_sha, head_sha)
    behind_by = int(comparison.get("behind_by") or 0)
    ahead_by = int(comparison.get("ahead_by") or 0)
    compare_status = str(comparison.get("status") or "")
    evidence = {
        "status": "passed",
        "head_sha": head_sha,
        "base": base,
        "base_sha": base_sha,
        "behind_by": behind_by,
        "ahead_by": ahead_by,
        "compare_status": compare_status,
        "run_id": last_run.get("id") if last_run else None,
        "run_url": last_run.get("html_url") if last_run else None,
        "run_status": last_run.get("status") if last_run else None,
        "run_conclusion": last_run.get("conclusion") if last_run else None,
    }
    if behind_by != 0 or compare_status != "ahead" or ahead_by <= 0:
        evidence["status"] = "blocked"
        evidence["reason"] = "base_not_ancestor_of_head"
        raise ReadyForPrBlocked(
            f"Branch não está estritamente à frente da base atual {base}; reconciliar antes de abrir PR",
            evidence,
        )
    return evidence


def write_pr_request_artifact(
    *,
    branch: str,
    base: str,
    title: str,
    body: str,
    error: str | None = None,
    status: str = "requested",
    pr_number: int | None = None,
    pr_url: str | None = None,
    draft: bool = True,
) -> Path:
    out_dir = Path(os.environ.get("PR_REQUEST_ARTIFACT_DIR", "artifacts/auto-pr-request"))
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0.0",
        "status": status,
        "branch": branch,
        "base": base,
        "title": title,
        "body": body,
        "draft": draft,
        "labels": ["padrao-ouro", "cloud-agent"],
        "pr_number": pr_number,
        "pr_url": pr_url,
        "error": error,
        "required_secret": "GH_PAT_ACTIONS",
        "repo_setting": "Allow GitHub Actions to create and approve pull requests",
    }
    path = out_dir / "auto-pr-request.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def resolve_token() -> str:
    # GH_TOKEN/GITHUB_TOKEN do workflow têm escopo explícito (pull-requests: write).
    for key in ("GH_TOKEN", "GITHUB_TOKEN", "GH_PAT_ACTIONS"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    raise RuntimeError("Token GitHub ausente (GH_TOKEN/GITHUB_TOKEN/GH_PAT_ACTIONS)")


def add_labels_best_effort(client: GitHubClient, number: int, labels: list[str]) -> None:
    try:
        client.add_labels(number, labels)
    except RuntimeError as exc:
        print(f"::warning::Não foi possível aplicar labels no PR #{number}: {exc}", file=sys.stderr)


def is_permission_error(exc: Exception) -> bool:
    message = str(exc)
    return " failed (401):" in message or " failed (403):" in message


def skip_existing_pr(
    *,
    branch: str,
    base: str,
    title: str,
    body: str,
    existing: dict[str, Any],
) -> int:
    number = int(existing["number"])
    pr_url = str(existing.get("html_url") or "")
    state = str(existing.get("state") or "closed")
    status = "skipped_merged" if existing.get("merged_at") else f"skipped_{state}"
    write_pr_request_artifact(
        branch=branch,
        base=base,
        title=title,
        body=body,
        status=status,
        pr_number=number,
        pr_url=pr_url,
    )
    print(f"PR já existente ({state}): {pr_url}")
    return 0


def create_pr_best_effort(
    client: GitHubClient,
    *,
    branch: str,
    base: str,
    title: str,
    body: str,
    draft: bool = True,
) -> int:
    try:
        created = client.create_pr(title=title, body=body, head=branch, base=base, draft=draft)
        number = int(created["number"])
        add_labels_best_effort(client, number, ["padrao-ouro", "cloud-agent"])
        write_pr_request_artifact(
            branch=branch,
            base=base,
            title=title,
            body=body,
            status="created",
            pr_number=number,
            pr_url=str(created.get("html_url") or ""),
            draft=draft,
        )
        print(f"PR criado: {created.get('html_url')}")
        return 0
    except RuntimeError as exc:
        if not is_permission_error(exc):
            raise
        write_pr_request_artifact(
            branch=branch,
            base=base,
            title=title,
            body=body,
            status="skipped_permission",
            error=str(exc),
            draft=draft,
        )
        print(
            "::warning::Criação de PR ignorada por permissão insuficiente do token.",
            file=sys.stderr,
        )
        return 0


def sync_existing_pr(
    client: GitHubClient,
    existing: dict[str, Any],
    *,
    branch: str,
    base: str,
    title: str,
    body: str,
) -> int:
    number = int(existing["number"])
    pr_url = str(existing.get("html_url") or "")
    try:
        client.update_pr(number, title=title, body=body)
        add_labels_best_effort(client, number, ["padrao-ouro", "cloud-agent"])
        write_pr_request_artifact(
            branch=branch,
            base=base,
            title=title,
            body=body,
            status="updated",
            pr_number=number,
            pr_url=pr_url,
        )
        print(f"PR atualizado: {pr_url}")
        return 0
    except RuntimeError as exc:
        if not is_permission_error(exc):
            raise
        write_pr_request_artifact(
            branch=branch,
            base=base,
            title=title,
            body=body,
            status="skipped_permission",
            pr_number=number,
            pr_url=pr_url,
            error=str(exc),
        )
        print(
            f"::warning::PR #{number} já existe; atualização ignorada por permissão insuficiente do token.",
            file=sys.stderr,
        )
        print(f"PR existente preservado: {pr_url}")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Open or update draft PR for agent branches.")
    parser.add_argument("--base", default=os.environ.get("PR_BASE_BRANCH", "main"))
    parser.add_argument("--branch", default=os.environ.get("GITHUB_REF_NAME", ""))
    parser.add_argument("--title", default=os.environ.get("PR_TITLE", ""))
    parser.add_argument("--head-sha", default=os.environ.get("READY_FOR_PR_HEAD_SHA", ""))
    parser.add_argument("--body-file", type=Path, default=None)
    parser.add_argument("--ready", action="store_true", help="Cria PR não-draft somente após READY_FOR_PR=passed.")
    args = parser.parse_args()

    branch = args.branch.strip()
    if not branch:
        print("Branch ausente (GITHUB_REF_NAME).", file=sys.stderr)
        return 2

    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not repository:
        print("GITHUB_REPOSITORY ausente.", file=sys.stderr)
        return 2

    explicit_title = args.title.strip()
    title = explicit_title or f"feat: Padrão Ouro — {branch}"
    metadata = load_branch_pr_metadata(branch)
    if metadata and not explicit_title:
        title = metadata.get("title") or title
    if args.body_file:
        if not args.body_file.is_file():
            print(f"Arquivo de corpo ausente: {args.body_file}", file=sys.stderr)
            return 2
        body = args.body_file.read_text(encoding="utf-8").strip()
    elif metadata:
        body = metadata.get("body") or build_body(branch, args.base, args.head_sha)
    else:
        body = build_body(branch, args.base, args.head_sha)

    try:
        client = GitHubClient(resolve_token(), repository)
        existing = client.find_existing_pr(branch, args.base)
        if existing:
            if str(existing.get("state")) == "open":
                return sync_existing_pr(
                    client,
                    existing,
                    branch=branch,
                    base=args.base,
                    title=title,
                    body=body,
                )
            return skip_existing_pr(
                branch=branch,
                base=args.base,
                title=title,
                body=body,
                existing=existing,
            )

        head_sha = args.head_sha.strip() or os.environ.get("GITHUB_SHA", "").strip()
        try:
            readiness = wait_for_ready_for_pr(
                client,
                head_sha=head_sha,
                base=args.base,
                wait_seconds=float(os.environ.get("READY_FOR_PR_WAIT_SECONDS", "600")),
                poll_seconds=float(os.environ.get("READY_FOR_PR_POLL_SECONDS", "5")),
            )
        except ReadyForPrBlocked as exc:
            write_readiness_artifact(exc.evidence)
            write_pr_request_artifact(
                branch=branch,
                base=args.base,
                title=title,
                body=body,
                status="blocked_readiness",
                error=str(exc),
            )
            print(f"READY_FOR_PR bloqueou abertura do PR: {exc}", file=sys.stderr)
            return 3

        write_readiness_artifact(readiness)
        body = append_readiness_body(body, readiness)
        return create_pr_best_effort(
            client,
            branch=branch,
            base=args.base,
            title=title,
            body=body,
            draft=not args.ready,
        )
    except Exception as exc:  # noqa: BLE001 - report failure with artifact for automation retry
        artifact = write_pr_request_artifact(branch=branch, base=args.base, title=title, body=body, error=str(exc))
        print(f"Falha ao abrir PR automaticamente; artifact salvo em {artifact}", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
