#!/usr/bin/env python3
"""Open or update a draft PR for Cloud Agent / cursor/* branches via GitHub REST API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlencode


def build_body(branch: str, base: str) -> str:
    repo = os.environ.get("GITHUB_REPOSITORY", "ericson-j-santos/reqsys-v2-enterprise-real")
    head_sha = os.environ.get("GITHUB_SHA", "local")
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
        "draft": True,
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
) -> int:
    try:
        created = client.create_pr(title=title, body=body, head=branch, base=base, draft=True)
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
    args = parser.parse_args()

    branch = args.branch.strip()
    if not branch:
        print("Branch ausente (GITHUB_REF_NAME).", file=sys.stderr)
        return 2

    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not repository:
        print("GITHUB_REPOSITORY ausente.", file=sys.stderr)
        return 2

    title = args.title.strip() or f"feat: Padrão Ouro — {branch}"
    metadata = load_branch_pr_metadata(branch)
    if metadata:
        title = metadata.get("title") or title
        body = metadata.get("body") or build_body(branch, args.base)
    else:
        body = build_body(branch, args.base)

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

        return create_pr_best_effort(
            client,
            branch=branch,
            base=args.base,
            title=title,
            body=body,
        )
    except Exception as exc:  # noqa: BLE001 - report failure with artifact for automation retry
        artifact = write_pr_request_artifact(branch=branch, base=args.base, title=title, body=body, error=str(exc))
        print(f"Falha ao abrir PR automaticamente; artifact salvo em {artifact}", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
