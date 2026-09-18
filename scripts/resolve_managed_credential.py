#!/usr/bin/env python3
"""Resolve uma credencial gerenciada do Azure Key Vault para um job confiável.

O valor secreto nunca é persistido em artifact/log. O script valida o vínculo
credential_id -> consumer declarado na política, estado/expiração no Key Vault,
mascara o valor no GitHub Actions e o exporta apenas para GITHUB_ENV.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "config" / "control-plane-lifecycle-policy.json"
DEFAULT_EVIDENCE = ROOT / "audit" / "credential-consumer-cutover.json"
ENV_NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")


class ResolutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class SecretMetadata:
    enabled: bool
    expires_at: datetime | None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ResolutionError("Expiração da credencial no Key Vault é inválida.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_policy(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResolutionError(f"Não foi possível ler a política: {path}") from exc
    if payload.get("contract") != "reqsys-credential-control-plane-lifecycle":
        raise ResolutionError("Contrato da política de credenciais é inválido.")
    store = ((payload.get("execution") or {}).get("secret_store") or {})
    if store.get("provider") != "azure_key_vault" or store.get("allow_github_secret_fallback") is not False:
        raise ResolutionError("Política deve usar Azure Key Vault sem fallback para GitHub Secret.")
    return payload


def select_credential(policy: dict[str, Any], credential_id: str, consumer: str) -> dict[str, Any]:
    matches = [
        item for item in policy.get("managed_credentials", [])
        if isinstance(item, dict) and item.get("credential_id") == credential_id
    ]
    if len(matches) != 1:
        raise ResolutionError(f"credential_id não encontrado ou duplicado: {credential_id}")
    item = matches[0]
    if item.get("enabled") is not True:
        raise ResolutionError(f"Credencial gerenciada está desabilitada: {credential_id}")
    consumers = item.get("consumers") or []
    if consumer not in consumers:
        raise ResolutionError(f"Consumer não autorizado para {credential_id}: {consumer}")
    secret_name = str(item.get("secret_name") or "").strip()
    if not secret_name:
        raise ResolutionError(f"secret_name ausente para {credential_id}")
    return item


def run_az(args: list[str]) -> str:
    try:
        completed = subprocess.run(
            ["az", *args], check=True, capture_output=True, text=True, timeout=45
        )
    except FileNotFoundError as exc:
        raise ResolutionError("Azure CLI não está disponível no runner.") from exc
    except subprocess.TimeoutExpired as exc:
        raise ResolutionError("Timeout ao consultar Azure Key Vault.") from exc
    except subprocess.CalledProcessError as exc:
        raise ResolutionError(f"Azure Key Vault recusou a operação (exit={exc.returncode}).") from exc
    return completed.stdout.rstrip("\r\n")


def read_secret_metadata(vault_name: str, secret_name: str) -> SecretMetadata:
    raw = run_az([
        "keyvault", "secret", "show",
        "--vault-name", vault_name,
        "--name", secret_name,
        "--query", "{enabled:attributes.enabled,expires:attributes.expires}",
        "-o", "json",
    ])
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise ResolutionError("Metadata do Key Vault não retornou JSON válido.") from exc
    return SecretMetadata(
        enabled=data.get("enabled") is not False,
        expires_at=parse_datetime(data.get("expires")) if data.get("expires") else None,
    )


def read_secret_value(vault_name: str, secret_name: str) -> str:
    value = run_az([
        "keyvault", "secret", "show",
        "--vault-name", vault_name,
        "--name", secret_name,
        "--query", "value",
        "-o", "tsv",
    ])
    if not value:
        raise ResolutionError("Key Vault retornou valor secreto vazio.")
    if "\n" in value or "\r" in value:
        raise ResolutionError("Valor secreto multilinha não é aceito para credenciais do Control Plane.")
    return value


def validate_metadata(metadata: SecretMetadata, *, now: datetime) -> None:
    if not metadata.enabled:
        raise ResolutionError("Versão atual da credencial está desabilitada no Key Vault.")
    if metadata.expires_at is not None and metadata.expires_at <= now:
        raise ResolutionError("Versão atual da credencial está expirada no Key Vault.")


def export_to_github_env(env_name: str, value: str, github_env: Path) -> None:
    if not ENV_NAME_RE.fullmatch(env_name):
        raise ResolutionError(f"Nome de variável de ambiente inválido: {env_name}")
    print(f"::add-mask::{value}")
    with github_env.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(f"{env_name}={value}\n")


def write_evidence(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--credential-id", required=True)
    parser.add_argument("--consumer", required=True)
    parser.add_argument("--export-env", required=True)
    parser.add_argument("--vault-name", default=os.environ.get("REQSYS_KEY_VAULT_NAME", ""))
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    evidence: dict[str, Any] = {
        "schema_version": "1.0.0",
        "status": "BLOCKED",
        "source": "azure_key_vault",
        "credential_id": args.credential_id,
        "consumer": args.consumer,
        "export_env": args.export_env,
        "resolved_at": utc_now().isoformat().replace("+00:00", "Z"),
        "secret_value_exposed": False,
        "legacy_github_secret_fallback": False,
    }
    try:
        vault_name = str(args.vault_name or "").strip()
        if not vault_name:
            raise ResolutionError("REQSYS_KEY_VAULT_NAME não configurado.")
        policy = load_policy(args.policy)
        item = select_credential(policy, args.credential_id, args.consumer)
        secret_name = str(item["secret_name"])
        metadata = read_secret_metadata(vault_name, secret_name)
        validate_metadata(metadata, now=utc_now())
        value = read_secret_value(vault_name, secret_name)
        github_env_raw = os.environ.get("GITHUB_ENV", "").strip()
        if not github_env_raw:
            raise ResolutionError("GITHUB_ENV não está disponível.")
        export_to_github_env(args.export_env, value, Path(github_env_raw))
        evidence.update({
            "status": "PASS",
            "provider": item.get("provider"),
            "secret_name": secret_name,
            "expires_at": metadata.expires_at.isoformat().replace("+00:00", "Z") if metadata.expires_at else None,
            "value_sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
        })
        write_evidence(args.evidence, evidence)
        print(json.dumps({
            "status": "PASS",
            "credential_id": args.credential_id,
            "consumer": args.consumer,
            "source": "azure_key_vault",
            "legacy_fallback": False,
        }, ensure_ascii=False))
        return 0
    except ResolutionError as exc:
        evidence["reason"] = str(exc)
        write_evidence(args.evidence, evidence)
        print(f"::error::{exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
