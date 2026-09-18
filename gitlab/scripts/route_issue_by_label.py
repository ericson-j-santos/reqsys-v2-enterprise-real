#!/usr/bin/env python3
"""Roteia issues abertas do GitLab para a branch de dominio multi-IA correta.

Le a tabela de dominios documentada em gitlab/docs/GITLAB_OPERATING_MODEL.md
(label ia:* -> prefixo de branch). Para cada issue aberta com uma dessas
labels e ainda nao roteada: cria a branch de dominio a partir do branch
padrao (se nao existir), adiciona a label `ia:roteado` e comenta na issue
com o link da branch. Idempotente e seguro por padrao (dry-run sem --apply);
nunca falha silenciosamente nem imprime o token.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RoutingError(RuntimeError):
    """Raised when issue routing cannot continue safely."""


DOMINIOS = [
    {"label": "ia:coordinator", "prefixo": "coord", "dominio": "coordinator"},
    {"label": "ia:runtime", "prefixo": "runtime", "dominio": "runtime"},
    {"label": "ia:observability", "prefixo": "observability", "dominio": "observability"},
    {"label": "ia:ux", "prefixo": "ux", "dominio": "ux"},
    {"label": "ia:governance-ci", "prefixo": "governance", "dominio": "governance-ci"},
    {"label": "ia:autonomous", "prefixo": "agents", "dominio": "autonomous"},
    {"label": "ia:docs", "prefixo": "docs", "dominio": "docs"},
]
LABEL_ROTEADO = "ia:roteado"


@dataclass(frozen=True)
class Config:
    api_url: str
    project_id: str
    token: str
    default_branch: str
    timeout_seconds: int
    dry_run: bool

    @classmethod
    def from_environment(cls, dry_run: bool) -> "Config":
        api_url = os.getenv("CI_API_V4_URL", "https://gitlab.com/api/v4").rstrip("/")
        project_id = os.getenv("CI_PROJECT_ID", "")
        token = os.getenv("GITLAB_PROVISIONING_TOKEN", "")
        default_branch = os.getenv("CI_DEFAULT_BRANCH", "main")

        missing = [
            name
            for name, value in {
                "CI_PROJECT_ID": project_id,
                "GITLAB_PROVISIONING_TOKEN": token,
                "CI_DEFAULT_BRANCH": default_branch,
            }.items()
            if not value
        ]
        if missing:
            raise RoutingError("Missing mandatory configuration: " + ", ".join(sorted(missing)))
        return cls(
            api_url=api_url,
            project_id=project_id,
            token=token,
            default_branch=default_branch,
            timeout_seconds=20,
            dry_run=dry_run,
        )


class GitLabClient:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.project = urllib.parse.quote(config.project_id, safe="")

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        allow_status: set[int] | None = None,
    ) -> tuple[int, Any]:
        url = f"{self.config.api_url}/{path.lstrip('/')}"
        body = None
        headers = {
            "PRIVATE-TOKEN": self.config.token,
            "Accept": "application/json",
            "User-Agent": "reqsys-gitlab-issue-router/1.0",
        }
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
                return response.status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            if allow_status and exc.code in allow_status:
                try:
                    return exc.code, json.loads(raw) if raw else {}
                except json.JSONDecodeError:
                    return exc.code, {"message": raw[:500]}
            raise RoutingError(f"GitLab API returned HTTP {exc.code} for {method} {url}: {raw[:500]}") from exc
        except urllib.error.URLError as exc:
            raise RoutingError(f"GitLab API unavailable for {url}: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise RoutingError(f"GitLab API returned invalid JSON for {url}") from exc

    def project_path(self, suffix: str = "") -> str:
        return f"projects/{self.project}{suffix}"


def resolver_dominio(labels: list[str]) -> dict[str, str] | None:
    label_set = set(labels)
    for item in DOMINIOS:
        if item["label"] in label_set:
            return item
    return None


def slugify(titulo: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", titulo.strip().lower())
    slug = slug.strip("-")
    return slug[:40] or "sem-titulo"


def nome_branch(prefixo: str, issue_iid: int, titulo: str) -> str:
    return f"{prefixo}/issue-{issue_iid}-{slugify(titulo)}"


def decidir_acao(*, ja_roteada: bool, tem_dominio: bool, branch_ja_existe: bool) -> str:
    if ja_roteada:
        return "ignorado_ja_roteado"
    if not tem_dominio:
        return "ignorado_sem_dominio"
    if branch_ja_existe:
        return "vincular_branch_existente"
    return "criar_branch"


def branch_existe(client: GitLabClient, config: Config, branch: str) -> bool:
    encoded = urllib.parse.quote(branch, safe="")
    status, _ = client.request("GET", client.project_path(f"/repository/branches/{encoded}"), allow_status={404})
    return status == 200


def listar_issues_roteaveis(client: GitLabClient) -> list[dict[str, Any]]:
    _, issues = client.request("GET", client.project_path("/issues?state=opened&per_page=100"))
    if not isinstance(issues, list):
        return []
    labels_conhecidas = {item["label"] for item in DOMINIOS}
    return [
        issue
        for issue in issues
        if isinstance(issue, dict) and labels_conhecidas.intersection(issue.get("labels") or [])
    ]


def rotear_issue(client: GitLabClient, config: Config, issue: dict[str, Any]) -> dict[str, Any]:
    labels = [str(item) for item in (issue.get("labels") or [])]
    iid = int(issue["iid"])
    ja_roteada = LABEL_ROTEADO in labels
    dominio = resolver_dominio(labels)

    if ja_roteada or dominio is None:
        acao = decidir_acao(ja_roteada=ja_roteada, tem_dominio=dominio is not None, branch_ja_existe=False)
        return {"issue_iid": iid, "acao": acao}

    branch = nome_branch(dominio["prefixo"], iid, str(issue.get("title") or ""))
    existe = False if config.dry_run else branch_existe(client, config, branch)
    acao = decidir_acao(ja_roteada=False, tem_dominio=True, branch_ja_existe=existe)
    resultado = {"issue_iid": iid, "acao": acao, "dominio": dominio["dominio"], "branch": branch}

    if config.dry_run or acao == "vincular_branch_existente":
        return resultado

    client.request("POST", client.project_path("/repository/branches"), {"branch": branch, "ref": config.default_branch})
    client.request("PUT", client.project_path(f"/issues/{iid}"), {"add_labels": LABEL_ROTEADO})
    client.request(
        "POST",
        client.project_path(f"/issues/{iid}/notes"),
        {"body": f"Roteado automaticamente para a branch `{branch}` (domínio `{dominio['dominio']}`)."},
    )
    return resultado


def build_report(config: Config, resultados: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_id": config.project_id,
        "dry_run": config.dry_run,
        "issues_avaliadas": len(resultados),
        "resultados": resultados,
    }


def write_report(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "gitlab-issue-routing.json"
    md_path = output_dir / "gitlab-issue-routing.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# GitLab Multi-IA Issue Routing",
        "",
        f"Generated at: {report['generated_at']}",
        f"Dry run: `{report['dry_run']}`",
        f"Issues avaliadas: {report['issues_avaliadas']}",
        "",
        "| Issue | Ação | Domínio | Branch |",
        "|---|---|---|---|",
    ]
    for item in report["resultados"]:
        lines.append(
            f"| #{item['issue_iid']} | `{item['acao']}` | {item.get('dominio', '-')} | {item.get('branch', '-')} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Apply changes; default is dry-run")
    parser.add_argument("--output-dir", default="audit")
    args = parser.parse_args()
    try:
        config = Config.from_environment(dry_run=not args.apply)
        client = GitLabClient(config)
        issues = listar_issues_roteaveis(client)
        resultados = [rotear_issue(client, config, issue) for issue in issues]
        report = build_report(config, resultados)
        write_report(report, Path(args.output_dir))
        print(json.dumps({"dry_run": report["dry_run"], "issues_avaliadas": report["issues_avaliadas"]}))
        return 0
    except RoutingError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
