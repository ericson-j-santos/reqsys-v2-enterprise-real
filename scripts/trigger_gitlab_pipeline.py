#!/usr/bin/env python3
"""Dispara uma pipeline real no projeto GitLab espelho do ReqSys via API REST.

Nunca imprime o token. Le de env var (--token-env, default GITLAB_TOKEN) ou de
um arquivo (--token-file) para nao deixar o valor no historico do shell.

Uso:
    export GITLAB_TOKEN="glpat-..."
    python scripts/trigger_gitlab_pipeline.py --ref main

    # ou, sem exportar:
    python scripts/trigger_gitlab_pipeline.py --ref main --token-file ~/.gitlab-token
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_PROJECT_PATH = "ericson-j-santos/reqsys-v2-enterprise-real"
DEFAULT_API_BASE = "https://gitlab.com/api/v4"


def resolver_token(args: argparse.Namespace) -> str:
    if args.token_file:
        token = open(args.token_file, encoding="utf-8").read().strip()
        if token:
            return token
    token = os.getenv(args.token_env, "").strip()
    if not token:
        raise SystemExit(
            f"Token nao encontrado. Defina a env var {args.token_env} ou use --token-file."
        )
    return token


def disparar_pipeline(*, api_base: str, project_path: str, ref: str, token: str) -> dict:
    project_id = urllib.parse.quote(project_path, safe="")
    url = f"{api_base}/projects/{project_id}/pipeline"
    body = json.dumps({"ref": ref}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "PRIVATE-TOKEN": token,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"GitLab respondeu HTTP {exc.code}: {detail}") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="main", help="Branch/tag a disparar (default: main)")
    parser.add_argument("--project-path", default=DEFAULT_PROJECT_PATH)
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--token-env", default="GITLAB_TOKEN")
    parser.add_argument("--token-file", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = resolver_token(args)
    pipeline = disparar_pipeline(
        api_base=args.api_base,
        project_path=args.project_path,
        ref=args.ref,
        token=token,
    )
    print(json.dumps({
        "id": pipeline.get("id"),
        "status": pipeline.get("status"),
        "ref": pipeline.get("ref"),
        "web_url": pipeline.get("web_url"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
