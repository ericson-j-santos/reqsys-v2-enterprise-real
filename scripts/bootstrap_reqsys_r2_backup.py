#!/usr/bin/env python3
"""Bootstrap seguro do backup ReqSys em Cloudflare R2.

O script roda localmente, recebe credenciais por prompt sem eco, grava os
GitHub Actions secrets via `gh secret set`, dispara o backup DEV e captura
runs/artifacts. Nenhum valor secreto é escrito em arquivo ou exibido.
"""
from __future__ import annotations

import argparse
import getpass
import json
import re
import secrets
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from typing import Any

DEFAULT_REPOSITORY = "ericson-j-santos/reqsys-v2-enterprise-real"
BACKUP_WORKFLOW = "reqsys-free-tier-backup.yml"
PROVIDER_WORKFLOW = "reqsys-backup-provider-readiness.yml"
ROLLOUT_WORKFLOW = "reqsys-backup-rollout-readiness.yml"
REQUIRED_SECRET_NAMES = (
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET",
    "RESTIC_PASSWORD",
)


class BootstrapError(RuntimeError):
    pass


def run(
    command: list[str],
    *,
    stdin: str | None = None,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        input=stdin,
        text=True,
        check=False,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "comando sem saída").strip()
        raise BootstrapError(f"Falha em {command[0]}: {detail}")
    return result


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise BootstrapError(f"Ferramenta obrigatória ausente: {name}")


def prompt(label: str, *, secret: bool = False, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    reader = getpass.getpass if secret else input
    value = reader(f"{label}{suffix}: ").strip()
    value = value or (default or "")
    if not value:
        raise BootstrapError(f"Valor obrigatório não informado: {label}")
    return value


def validate_bucket(name: str) -> str:
    if not 3 <= len(name) <= 63 or not re.fullmatch(
        r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", name
    ):
        raise BootstrapError(
            "Bucket inválido: use 3–63 caracteres, somente letras minúsculas, "
            "números e hífens, sem hífen no início/fim."
        )
    return name


def gh_json(arguments: list[str]) -> Any:
    result = run(["gh", *arguments], capture=True)
    try:
        return json.loads(result.stdout or "null")
    except json.JSONDecodeError as exc:
        raise BootstrapError("Resposta JSON inválida do GitHub CLI") from exc


def workflow_exists(repository: str, workflow: str) -> bool:
    return run(
        ["gh", "workflow", "view", workflow, "--repo", repository],
        check=False,
        capture=True,
    ).returncode == 0


def ensure_bucket(bucket: str) -> None:
    info = run(
        ["npx", "--yes", "wrangler", "r2", "bucket", "info", bucket, "--json"],
        check=False,
        capture=True,
    )
    if info.returncode == 0:
        print(f"Bucket R2 verificado: {bucket}")
        return
    print("Bucket ainda não encontrado; o Wrangler poderá solicitar login no Cloudflare.")
    run(["npx", "--yes", "wrangler", "r2", "bucket", "create", bucket])
    run(["npx", "--yes", "wrangler", "r2", "bucket", "info", bucket, "--json"])
    print(f"Bucket R2 criado e verificado: {bucket}")


def set_actions_secret(repository: str, name: str, value: str) -> None:
    run(
        ["gh", "secret", "set", name, "--repo", repository, "--app", "actions"],
        stdin=value,
    )
    print(f"Secret configurado: {name}")


def verify_secret_names(repository: str) -> None:
    payload = gh_json(
        [
            "secret",
            "list",
            "--repo",
            repository,
            "--app",
            "actions",
            "--json",
            "name",
        ]
    )
    found = {item["name"] for item in payload if isinstance(item, dict)}
    missing = [name for name in REQUIRED_SECRET_NAMES if name not in found]
    if missing:
        raise BootstrapError(f"Secrets não materializados no GitHub: {', '.join(missing)}")


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def newest_dispatch_run(repository: str, workflow: str, not_before: datetime) -> dict[str, Any] | None:
    runs = gh_json(
        [
            "run",
            "list",
            "--repo",
            repository,
            "--workflow",
            workflow,
            "--event",
            "workflow_dispatch",
            "--limit",
            "20",
            "--json",
            "databaseId,createdAt,status,conclusion,url",
        ]
    )
    eligible = [
        item
        for item in runs
        if parse_timestamp(item["createdAt"]) >= not_before - timedelta(seconds=5)
    ]
    return max(eligible, key=lambda item: parse_timestamp(item["createdAt"]), default=None)


def trigger_workflow(
    repository: str,
    workflow: str,
    fields: dict[str, str],
    *,
    discovery_timeout: int,
) -> dict[str, Any]:
    started = datetime.now(UTC)
    command = ["gh", "workflow", "run", workflow, "--repo", repository]
    for key, value in fields.items():
        command.extend(["-f", f"{key}={value}"])
    run(command)

    deadline = time.monotonic() + discovery_timeout
    selected: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        selected = newest_dispatch_run(repository, workflow, started)
        if selected:
            break
        time.sleep(3)
    if not selected:
        raise BootstrapError(f"Run de {workflow} não foi localizado após o dispatch")

    run(
        [
            "gh",
            "run",
            "watch",
            str(selected["databaseId"]),
            "--repo",
            repository,
            "--exit-status",
        ]
    )
    refreshed = gh_json(
        [
            "run",
            "view",
            str(selected["databaseId"]),
            "--repo",
            repository,
            "--json",
            "databaseId,status,conclusion,url",
        ]
    )
    if refreshed.get("conclusion") != "success":
        raise BootstrapError(
            f"Workflow {workflow} terminou com {refreshed.get('conclusion')}: "
            f"{refreshed.get('url')}"
        )
    print(f"Workflow concluído: {refreshed['url']}")
    return refreshed


def artifact_names(repository: str, run_id: int) -> list[str]:
    payload = gh_json(
        [
            "api",
            f"repos/{repository}/actions/runs/{run_id}/artifacts",
        ]
    )
    return sorted(
        item["name"]
        for item in payload.get("artifacts", [])
        if not item.get("expired", False)
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Configura R2/Restic, executa backup DEV e captura artifacts."
    )
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY)
    parser.add_argument("--bucket", default="reqsys-backups")
    parser.add_argument("--skip-bucket-create", action="store_true")
    parser.add_argument("--discovery-timeout", type=int, default=120)
    args = parser.parse_args()

    for tool in ("gh", "npx"):
        require_tool(tool)
    run(["gh", "auth", "status"])

    bucket = validate_bucket(args.bucket)
    if not args.skip_bucket_create:
        ensure_bucket(bucket)

    print("\nNo Cloudflare R2, gere credenciais S3 com Object Read & Write, limitadas ao bucket.")
    account_id = prompt("R2 Account ID")
    access_key = prompt("R2 Access Key ID")
    secret_key = prompt("R2 Secret Access Key", secret=True)
    restic_password = secrets.token_urlsafe(48)

    values = {
        "R2_ACCOUNT_ID": account_id,
        "R2_ACCESS_KEY_ID": access_key,
        "R2_SECRET_ACCESS_KEY": secret_key,
        "R2_BUCKET": bucket,
        "RESTIC_PASSWORD": restic_password,
    }
    try:
        for name, value in values.items():
            set_actions_secret(args.repository, name, value)
        verify_secret_names(args.repository)
    finally:
        for name in list(values):
            values[name] = ""
        account_id = access_key = secret_key = restic_password = ""

    provider_run: dict[str, Any] | None = None
    if workflow_exists(args.repository, PROVIDER_WORKFLOW):
        provider_run = trigger_workflow(
            args.repository,
            PROVIDER_WORKFLOW,
            {"strict": "true"},
            discovery_timeout=args.discovery_timeout,
        )
    else:
        print("Provider readiness ainda não está na main; continuando com o backup DEV.")

    backup_run = trigger_workflow(
        args.repository,
        BACKUP_WORKFLOW,
        {
            "environment": "dev",
            "include_disabled": "false",
            "approve_prod": "",
        },
        discovery_timeout=args.discovery_timeout,
    )
    artifacts = artifact_names(args.repository, int(backup_run["databaseId"]))
    if "reqsys-backup-evidence-dev" not in artifacts:
        raise BootstrapError(
            "Backup terminou sem o artifact reqsys-backup-evidence-dev. "
            f"Artifacts encontrados: {', '.join(artifacts) or 'nenhum'}"
        )

    rollout_run: dict[str, Any] | None = None
    if workflow_exists(args.repository, ROLLOUT_WORKFLOW):
        rollout_run = trigger_workflow(
            args.repository,
            ROLLOUT_WORKFLOW,
            {
                "source_run_id": str(backup_run["databaseId"]),
                "strict": "true",
            },
            discovery_timeout=args.discovery_timeout,
        )
    else:
        print("Rollout readiness ainda não está na main; evidence DEV foi capturada.")

    result = {
        "repository": args.repository,
        "bucket": bucket,
        "provider_readiness_run": provider_run and provider_run.get("url"),
        "backup_dev_run": backup_run.get("url"),
        "backup_dev_artifacts": artifacts,
        "rollout_readiness_run": rollout_run and rollout_run.get("url"),
        "production_touched": False,
        "secret_values_persisted_locally": False,
    }
    print("\nRESULTADO SANITIZADO")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BootstrapError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        raise SystemExit(1)
