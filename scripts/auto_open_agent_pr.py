#!/usr/bin/env python3
"""Open or update a draft PR for Cloud Agent / cursor/* branches via GitHub REST API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


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

    def find_open_pr(self, head: str, base: str) -> dict[str, Any] | None:
        pulls = self._request("GET", f"/pulls?state=open&head={self.repository.split('/')[0]}:{head}&base={base}")
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


def resolve_token() -> str:
    for key in ("GH_PAT_ACTIONS", "GH_TOKEN", "GITHUB_TOKEN"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    raise RuntimeError("Token GitHub ausente (GH_PAT_ACTIONS/GH_TOKEN/GITHUB_TOKEN)")


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
    body = build_body(branch, args.base)
    client = GitHubClient(resolve_token(), repository)

    existing = client.find_open_pr(branch, args.base)
    if existing:
        number = int(existing["number"])
        client.update_pr(number, title=title, body=body)
        client.add_labels(number, ["padrao-ouro", "cloud-agent"])
        print(f"PR atualizado: {existing.get('html_url')}")
        return 0

    created = client.create_pr(title=title, body=body, head=branch, base=args.base, draft=True)
    number = int(created["number"])
    client.add_labels(number, ["padrao-ouro", "cloud-agent"])
    print(f"PR criado: {created.get('html_url')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
