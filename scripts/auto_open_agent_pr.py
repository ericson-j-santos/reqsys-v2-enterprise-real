#!/usr/bin/env python3
"""Open or update a draft PR for Cloud Agent / cursor/* branches."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=check, text=True, capture_output=True)


def gh_json(args: list[str]) -> list[dict] | dict:
    proc = run(["gh", *args])
    return json.loads(proc.stdout or "null")


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

    title = args.title.strip() or f"feat: Padrão Ouro — {branch}"
    body = build_body(branch, args.base)

    existing = gh_json(["pr", "list", "--head", branch, "--base", args.base, "--json", "number,url"])
    if isinstance(existing, list) and existing:
        number = existing[0]["number"]
        url = existing[0]["url"]
        run(["gh", "pr", "edit", str(number), "--title", title, "--body", body])
        run(["gh", "pr", "edit", str(number), "--add-label", "padrao-ouro"], check=False)
        run(["gh", "pr", "edit", str(number), "--add-label", "cloud-agent"], check=False)
        print(f"PR atualizado: {url}")
        return 0

    proc = run(
        [
            "gh",
            "pr",
            "create",
            "--base",
            args.base,
            "--head",
            branch,
            "--title",
            title,
            "--body",
            body,
            "--draft",
        ]
    )
    print(proc.stdout.strip())
    number = gh_json(["pr", "list", "--head", branch, "--base", args.base, "--json", "number"])
    if isinstance(number, list) and number:
        run(["gh", "pr", "edit", str(number[0]["number"]), "--add-label", "padrao-ouro"], check=False)
        run(["gh", "pr", "edit", str(number[0]["number"]), "--add-label", "cloud-agent"], check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
