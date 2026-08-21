#!/usr/bin/env python3
"""Orquestra ciclo de vida de credenciais do ReqSys sem versionar valores secretos.

Objetivos:
- usar Azure Key Vault como fonte externa de verdade, autenticada por OIDC no CI;
- planejar rotação de forma determinística e fail-closed;
- executar self-rotation de Project Access Token do GitLab;
- substituir deploy tokens Fly por app, validando o novo token antes de revogar o anterior;
- gerar evidência sanitizada com correlation_id e sem valores de credenciais.

O modo padrão é ``plan``. Qualquer mutação exige:
1. ``--mode execute``;
2. ``REQSYS_CREDENTIAL_MUTATION_ENABLED=true``;
3. política válida;
4. evidência suficiente para uma troca segura.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "config" / "control-plane-lifecycle-policy.json"
DEFAULT_OUTPUT = ROOT / "audit" / "credential-control-plane-lifecycle.json"
SUPPORTED_PROVIDERS = {"gitlab", "fly"}
SUPPORTED_STRATEGIES = {
    "gitlab": {"gitlab_self_rotate"},
    "fly": {"fly_replace_deploy_token"},
}


class LifecycleError(RuntimeError):
    """Falha de política, evidência, autenticação ou rotação."""


@dataclass(frozen=True)
class SecretMetadata:
    name: str
    exists: bool
    enabled: bool | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    expires_at: datetime | None = None
    tags: dict[str, str] | None = None


@dataclass(frozen=True)
class RotationResult:
    credential_id: str
    provider: str
    status: str
    detail: str
    provider_token_id: str | None = None
    expires_at: datetime | None = None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    text = str(value).strip()
    if text.isdigit():
        return datetime.fromtimestamp(float(text), tz=timezone.utc)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso_z(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_policy(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise LifecycleError("Política de lifecycle deve possuir objeto JSON na raiz.")
    validate_policy(payload)
    return payload


def validate_policy(policy: dict[str, Any]) -> None:
    errors: list[str] = []
    if policy.get("contract") != "reqsys-credential-control-plane-lifecycle":
        errors.append("contract inválido")

    execution = policy.get("execution")
    if not isinstance(execution, dict):
        errors.append("execution ausente")
        execution = {}
    store = execution.get("secret_store")
    if not isinstance(store, dict):
        errors.append("execution.secret_store ausente")
        store = {}
    if store.get("provider") != "azure_key_vault":
        errors.append("secret_store.provider deve ser azure_key_vault")
    if store.get("authentication") != "github_oidc":
        errors.append("secret_store.authentication deve ser github_oidc")
    if store.get("allow_github_secret_fallback") is not False:
        errors.append("allow_github_secret_fallback deve ser false")
    if not str(store.get("vault_name_env") or "").strip():
        errors.append("secret_store.vault_name_env ausente")

    federation = execution.get("identity_federation")
    if not isinstance(federation, dict):
        errors.append("execution.identity_federation ausente")
        federation = {}
    github_actions = federation.get("github_actions")
    if not isinstance(github_actions, dict):
        errors.append("identity_federation.github_actions ausente")
        github_actions = {}
    if github_actions.get("mode") != "oidc":
        errors.append("identity_federation.github_actions.mode deve ser oidc")
    if github_actions.get("long_lived_github_token_required") is not False:
        errors.append("long_lived_github_token_required deve ser false")

    credentials = policy.get("managed_credentials")
    if not isinstance(credentials, list) or not credentials:
        errors.append("managed_credentials deve conter ao menos uma entrada")
        credentials = []

    seen: set[str] = set()
    for index, item in enumerate(credentials):
        prefix = f"managed_credentials[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} deve ser objeto")
            continue
        credential_id = str(item.get("credential_id") or "").strip()
        provider = str(item.get("provider") or "").strip()
        secret_name = str(item.get("secret_name") or "").strip()
        rotation = item.get("rotation") if isinstance(item.get("rotation"), dict) else {}
        target = item.get("target") if isinstance(item.get("target"), dict) else {}

        if not credential_id:
            errors.append(f"{prefix}.credential_id ausente")
        elif credential_id in seen:
            errors.append(f"credential_id duplicado: {credential_id}")
        else:
            seen.add(credential_id)
        if provider not in SUPPORTED_PROVIDERS:
            errors.append(f"{credential_id or prefix}: provider não suportado: {provider}")
        if not secret_name:
            errors.append(f"{credential_id or prefix}: secret_name ausente")
        if any(marker in item for marker in ("token", "value", "secret_value", "client_secret", "password")):
            errors.append(f"{credential_id or prefix}: valor secreto versionado é proibido")

        strategy = str(rotation.get("strategy") or "").strip()
        if provider in SUPPORTED_STRATEGIES and strategy not in SUPPORTED_STRATEGIES[provider]:
            errors.append(f"{credential_id or prefix}: strategy inválida para {provider}: {strategy}")

        interval = int(rotation.get("interval_days") or 0)
        warning = int(rotation.get("warning_days") or 0)
        expires = int(rotation.get("expires_in_days") or 0)
        if interval <= 0 or warning <= 0 or expires <= 0:
            errors.append(f"{credential_id or prefix}: interval_days/warning_days/expires_in_days devem ser > 0")
        if warning >= interval:
            errors.append(f"{credential_id or prefix}: warning_days deve ser menor que interval_days")
        if expires < interval:
            errors.append(f"{credential_id or prefix}: expires_in_days não pode ser menor que interval_days")

        if provider == "gitlab" and not str(target.get("project") or "").strip():
            errors.append(f"{credential_id or prefix}: target.project ausente")
        if provider == "fly":
            if not str(target.get("app") or "").strip():
                errors.append(f"{credential_id or prefix}: target.app ausente")
            if not str(item.get("issuer_secret_name") or "").strip():
                errors.append(f"{credential_id or prefix}: issuer_secret_name ausente")

    if errors:
        raise LifecycleError("Política inválida: " + "; ".join(errors))


class CommandRunner:
    def run(self, args: list[str], *, env: dict[str, str] | None = None) -> str:
        try:
            completed = subprocess.run(args, check=True, text=True, capture_output=True, env=env)
        except FileNotFoundError as exc:
            raise LifecycleError(f"Comando não encontrado: {args[0]}") from exc
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            safe = stderr[:800] if stderr else f"exit_code={exc.returncode}"
            raise LifecycleError(f"Falha em {args[0]}: {safe}") from exc
        return completed.stdout


class AzureKeyVaultStore:
    """Acessa Azure Key Vault via Azure CLI já autenticada por OIDC."""

    def __init__(self, vault_name: str, runner: CommandRunner | None = None):
        if not vault_name.strip():
            raise LifecycleError("Nome do Azure Key Vault não configurado.")
        self.vault_name = vault_name.strip()
        self.runner = runner or CommandRunner()

    def metadata(self, name: str) -> SecretMetadata:
        args = [
            "az", "keyvault", "secret", "show", "--vault-name", self.vault_name,
            "--name", name,
            "--query", "{enabled:attributes.enabled,created:attributes.created,updated:attributes.updated,expires:attributes.expires,tags:tags}",
            "-o", "json",
        ]
        try:
            output = self.runner.run(args)
        except LifecycleError as exc:
            text = str(exc).lower()
            if "secretnotfound" in text or "not found" in text:
                return SecretMetadata(name=name, exists=False)
            raise
        data = json.loads(output or "{}")
        tags = data.get("tags") if isinstance(data.get("tags"), dict) else {}
        return SecretMetadata(
            name=name,
            exists=True,
            enabled=data.get("enabled"),
            created_at=parse_datetime(data.get("created")),
            updated_at=parse_datetime(data.get("updated")),
            expires_at=parse_datetime(data.get("expires")),
            tags={str(k): str(v) for k, v in tags.items()},
        )

    def read(self, name: str) -> str:
        output = self.runner.run([
            "az", "keyvault", "secret", "show", "--vault-name", self.vault_name,
            "--name", name, "--query", "value", "-o", "tsv",
        ]).rstrip("\r\n")
        if not output:
            raise LifecycleError(f"Secret {name!r} vazio ou indisponível.")
        return output

    def write(self, name: str, value: str, *, expires_at: datetime, tags: dict[str, str]) -> None:
        args = [
            "az", "keyvault", "secret", "set", "--vault-name", self.vault_name,
            "--name", name, "--value", value, "--expires", iso_z(expires_at) or "",
            "--output", "none",
        ]
        if tags:
            args.extend(["--tags", *[f"{k}={v}" for k, v in sorted(tags.items())]])
        self.runner.run(args)


class GitLabAdapter:
    def __init__(self, *, base_url: str = "https://gitlab.com", runner: CommandRunner | None = None):
        self.base_url = base_url.rstrip("/")
        self.runner = runner or CommandRunner()

    def rotate_self(self, project: str, current_token: str, *, expires_at: datetime) -> tuple[str, str | None]:
        project_id = urllib.parse.quote(project, safe="")
        url = f"{self.base_url}/api/v4/projects/{project_id}/access_tokens/self/rotate"
        payload = urllib.parse.urlencode({"expires_at": expires_at.date().isoformat()}).encode("utf-8")
        request = urllib.request.Request(
            url, data=payload, method="POST",
            headers={"PRIVATE-TOKEN": current_token, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            safe_body = exc.read(500).decode("utf-8", errors="replace")
            raise LifecycleError(f"GitLab self-rotate falhou: HTTP {exc.code}: {safe_body}") from exc
        except urllib.error.URLError as exc:
            raise LifecycleError(f"GitLab indisponível durante self-rotate: {exc.reason}") from exc
        data = json.loads(body)
        token = str(data.get("token") or "")
        if not token:
            raise LifecycleError("GitLab não retornou o novo token após self-rotate.")
        token_id = str(data.get("id")) if data.get("id") is not None else None
        return token, token_id

    def validate_repository(self, project: str, token: str) -> None:
        basic = base64.b64encode(f"oauth2:{token}".encode("utf-8")).decode("ascii")
        env = os.environ.copy()
        env.update({
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": f"http.{self.base_url}/.extraheader",
            "GIT_CONFIG_VALUE_0": f"Authorization: Basic {basic}",
        })
        url = f"{self.base_url}/{project}.git"
        output = self.runner.run(["git", "ls-remote", url, "refs/heads/main"], env=env)
        if not output.strip():
            raise LifecycleError("Novo token GitLab não conseguiu resolver refs/heads/main.")


class FlyAdapter:
    def __init__(self, runner: CommandRunner | None = None):
        self.runner = runner or CommandRunner()

    @staticmethod
    def _env(token: str) -> dict[str, str]:
        env = os.environ.copy()
        env["FLY_API_TOKEN"] = token
        return env

    def create_deploy_token(self, *, app: str, issuer_token: str, name: str, expires_in_days: int) -> tuple[str, str | None]:
        output = self.runner.run([
            "flyctl", "tokens", "create", "deploy", "--app", app,
            "--expiry", f"{expires_in_days * 24}h", "--name", name, "--json",
        ], env=self._env(issuer_token))
        data = json.loads(output)
        token = str(data.get("token") or data.get("Token") or "")
        token_id_raw = data.get("id") if "id" in data else data.get("ID")
        token_id = str(token_id_raw) if token_id_raw not in (None, "") else None
        if not token:
            raise LifecycleError("Fly não retornou o novo deploy token em JSON.")
        return token, token_id

    def validate_app(self, *, app: str, token: str) -> None:
        output = self.runner.run(["flyctl", "status", "--app", app, "--json"], env=self._env(token))
        if not output.strip():
            raise LifecycleError(f"Novo deploy token Fly não validou acesso ao app {app}.")
        json.loads(output)

    def revoke(self, *, token_id: str, issuer_token: str) -> None:
        self.runner.run(["flyctl", "tokens", "revoke", token_id], env=self._env(issuer_token))


def _rotation_anchor(metadata: SecretMetadata) -> datetime | None:
    tags = metadata.tags or {}
    tagged = parse_datetime(tags.get("rotated_at"))
    return tagged or metadata.updated_at or metadata.created_at


def _plan_item(item: dict[str, Any], store: AzureKeyVaultStore, now: datetime) -> dict[str, Any]:
    credential_id = str(item["credential_id"])
    provider = str(item["provider"])
    secret_name = str(item["secret_name"])
    rotation = item["rotation"]
    enabled = item.get("enabled", True) is not False

    if not enabled:
        return {"credential_id": credential_id, "provider": provider, "status": "DISABLED", "action": "NONE", "reason": "policy_disabled"}

    metadata = store.metadata(secret_name)
    if not metadata.exists:
        if provider == "fly":
            issuer_name = str(item.get("issuer_secret_name") or "")
            issuer = store.metadata(issuer_name) if issuer_name else SecretMetadata("", False)
            if issuer.exists and issuer.enabled is not False:
                return {"credential_id": credential_id, "provider": provider, "status": "MISSING", "action": "CREATE", "reason": "managed_secret_missing_issuer_available"}
        return {"credential_id": credential_id, "provider": provider, "status": "BOOTSTRAP_REQUIRED", "action": "NONE", "reason": "managed_secret_missing"}

    if metadata.enabled is False:
        return {"credential_id": credential_id, "provider": provider, "status": "BLOCKED", "action": "NONE", "reason": "secret_disabled"}

    interval_days = int(rotation["interval_days"])
    warning_days = int(rotation["warning_days"])
    anchor = _rotation_anchor(metadata)
    due_by_age = anchor + timedelta(days=interval_days) if anchor else None
    due_at = metadata.expires_at if metadata.expires_at and (due_by_age is None or metadata.expires_at < due_by_age) else due_by_age

    if due_at is None:
        return {"credential_id": credential_id, "provider": provider, "status": "EVIDENCE_INCOMPLETE", "action": "NONE", "reason": "rotation_anchor_unavailable"}

    warning_at = due_at - timedelta(days=warning_days)
    tags = metadata.tags or {}

    if provider == "gitlab" and metadata.expires_at is not None and now >= metadata.expires_at:
        return {
            "credential_id": credential_id,
            "provider": provider,
            "status": "BOOTSTRAP_REQUIRED",
            "action": "NONE",
            "reason": "gitlab_token_expired_self_rotate_unavailable",
            "rotation_due_at": iso_z(due_at),
            "expires_at": iso_z(metadata.expires_at),
        }

    if provider == "fly" and now >= warning_at:
        issuer_name = str(item.get("issuer_secret_name") or "")
        issuer = store.metadata(issuer_name) if issuer_name else SecretMetadata("", False)
        if not issuer.exists or issuer.enabled is False:
            return {"credential_id": credential_id, "provider": provider, "status": "BLOCKED", "action": "NONE", "reason": "fly_issuer_unavailable", "rotation_due_at": iso_z(due_at)}
        if not tags.get("provider_token_id"):
            return {"credential_id": credential_id, "provider": provider, "status": "BLOCKED", "action": "NONE", "reason": "provider_token_id_missing_for_safe_revoke", "rotation_due_at": iso_z(due_at)}

    if now >= due_at:
        status, action = "EXPIRED", "ROTATE"
    elif now >= warning_at:
        status, action = "ROTATION_DUE", "ROTATE"
    else:
        status, action = "HEALTHY", "NONE"

    return {
        "credential_id": credential_id,
        "provider": provider,
        "status": status,
        "action": action,
        "reason": "policy_evaluation",
        "rotation_due_at": iso_z(due_at),
        "expires_at": iso_z(metadata.expires_at),
        "provider_token_id_present": bool(tags.get("provider_token_id")),
    }


def build_plan(
    policy: dict[str, Any],
    store: AzureKeyVaultStore,
    *,
    now: datetime | None = None,
    credential_ids: set[str] | None = None,
    providers: set[str] | None = None,
) -> dict[str, Any]:
    instant = now or utc_now()
    rows: list[dict[str, Any]] = []
    for item in policy["managed_credentials"]:
        cid = str(item["credential_id"])
        provider = str(item["provider"])
        if credential_ids and cid not in credential_ids:
            continue
        if providers and provider not in providers:
            continue
        rows.append(_plan_item(item, store, instant))

    actionable = sum(1 for row in rows if row["action"] in {"CREATE", "ROTATE"})
    blocked = sum(1 for row in rows if row["status"] in {"BLOCKED", "BOOTSTRAP_REQUIRED", "EVIDENCE_INCOMPLETE"})
    overall = "BLOCKED" if blocked else "ACTION_REQUIRED" if actionable else "HEALTHY"
    return {
        "status": overall,
        "generated_at": iso_z(instant),
        "summary": {"credentials_evaluated": len(rows), "actionable": actionable, "blocked": blocked},
        "credentials": rows,
    }


def execute_plan(
    policy: dict[str, Any],
    store: AzureKeyVaultStore,
    plan: dict[str, Any],
    *,
    now: datetime | None = None,
    gitlab: GitLabAdapter | None = None,
    fly: FlyAdapter | None = None,
) -> list[RotationResult]:
    if os.getenv("REQSYS_CREDENTIAL_MUTATION_ENABLED", "").strip().lower() != "true":
        raise LifecycleError("Mutação bloqueada: REQSYS_CREDENTIAL_MUTATION_ENABLED != true.")

    instant = now or utc_now()
    by_id = {str(item["credential_id"]): item for item in policy["managed_credentials"]}
    gitlab = gitlab or GitLabAdapter()
    fly = fly or FlyAdapter()
    results: list[RotationResult] = []

    for row in plan["credentials"]:
        action = row.get("action")
        if action not in {"CREATE", "ROTATE"}:
            continue
        cid = str(row["credential_id"])
        item = by_id[cid]
        provider = str(item["provider"])
        rotation = item["rotation"]
        expires_at = instant + timedelta(days=int(rotation["expires_in_days"]))

        if provider == "gitlab":
            if action != "ROTATE":
                raise LifecycleError(f"{cid}: GitLab exige bootstrap inicial antes de self-rotate.")
            current = store.read(str(item["secret_name"]))
            project = str(item["target"]["project"])
            new_token, token_id = gitlab.rotate_self(project, current, expires_at=expires_at)
            tags = {"credential_id": cid, "provider": "gitlab", "rotated_at": iso_z(instant) or ""}
            if token_id:
                tags["provider_token_id"] = token_id
            store.write(str(item["secret_name"]), new_token, expires_at=expires_at, tags=tags)
            gitlab.validate_repository(project, new_token)
            results.append(RotationResult(cid, provider, "ROTATED", "self_rotate_persisted_and_validated", token_id, expires_at))
            continue

        if provider == "fly":
            issuer = store.read(str(item["issuer_secret_name"]))
            metadata = store.metadata(str(item["secret_name"]))
            old_id = (metadata.tags or {}).get("provider_token_id") if metadata.exists else None
            if action == "ROTATE" and not old_id:
                raise LifecycleError(f"{cid}: rotação Fly bloqueada sem provider_token_id do token anterior.")
            app = str(item["target"]["app"])
            name = str(item.get("token_name") or f"reqsys-{app}-deploy")
            new_token, new_id = fly.create_deploy_token(app=app, issuer_token=issuer, name=name, expires_in_days=int(rotation["expires_in_days"]))
            fly.validate_app(app=app, token=new_token)
            if not new_id:
                raise LifecycleError(f"{cid}: Fly criou token sem ID; persistência bloqueada para garantir revogação futura.")
            tags = {
                "credential_id": cid,
                "provider": "fly",
                "provider_token_id": new_id,
                "fly_app": app,
                "rotated_at": iso_z(instant) or "",
            }
            store.write(str(item["secret_name"]), new_token, expires_at=expires_at, tags=tags)
            if old_id:
                fly.revoke(token_id=old_id, issuer_token=issuer)
            results.append(RotationResult(
                cid,
                provider,
                "CREATED" if action == "CREATE" else "ROTATED",
                "new_token_validated_persisted_old_revoked" if old_id else "new_token_validated_and_persisted",
                new_id,
                expires_at,
            ))
            continue

        raise LifecycleError(f"Provider sem adaptador: {provider}")

    return results


def _result_to_dict(result: RotationResult) -> dict[str, Any]:
    return {
        "credential_id": result.credential_id,
        "provider": result.provider,
        "status": result.status,
        "detail": result.detail,
        "provider_token_id": result.provider_token_id,
        "expires_at": iso_z(result.expires_at),
    }


def build_evidence(
    *,
    mode: str,
    correlation_id: str,
    plan: dict[str, Any] | None,
    results: Iterable[RotationResult] = (),
    error: str | None = None,
) -> dict[str, Any]:
    safe_error = (error or "")[:1000] or None
    result_rows = [_result_to_dict(item) for item in results]
    if error:
        status = "FAIL"
    elif result_rows:
        status = "PASS"
    elif plan is not None:
        status = "PASS" if plan.get("status") in {"VALID", "HEALTHY", "ACTION_REQUIRED"} else "BLOCKED"
    else:
        status = "UNKNOWN"
    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-credential-control-plane-lifecycle-evidence",
        "generated_at": iso_z(utc_now()),
        "correlation_id": correlation_id,
        "mode": mode,
        "status": status,
        "security": {
            "secret_values_exposed": False,
            "secret_values_persisted_in_evidence": False,
            "github_secret_fallback_used": False,
        },
        "plan": plan,
        "results": result_rows,
        "error": safe_error,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--mode", choices=("validate", "plan", "execute"), default="plan")
    parser.add_argument("--credential-id", action="append", default=[])
    parser.add_argument("--provider", action="append", choices=sorted(SUPPORTED_PROVIDERS), default=[])
    parser.add_argument("--correlation-id", default=os.getenv("CORRELATION_ID") or f"credential-lifecycle-{uuid.uuid4()}")
    args = parser.parse_args()

    plan: dict[str, Any] | None = None
    results: list[RotationResult] = []
    try:
        policy = load_policy(args.policy)
        if args.mode == "validate":
            evidence = build_evidence(mode=args.mode, correlation_id=args.correlation_id, plan={"status": "VALID"})
        else:
            store_cfg = policy["execution"]["secret_store"]
            vault_env = str(store_cfg["vault_name_env"])
            vault_name = os.getenv(vault_env, "").strip()
            if not vault_name:
                raise LifecycleError(f"{vault_env} não configurado; acesso ao secret store bloqueado.")
            store = AzureKeyVaultStore(vault_name)
            plan = build_plan(
                policy,
                store,
                credential_ids=set(args.credential_id) or None,
                providers=set(args.provider) or None,
            )
            if args.mode == "execute":
                if plan["status"] == "BLOCKED":
                    raise LifecycleError("Plano contém credenciais bloqueadas; nenhuma mutação executada.")
                results = execute_plan(policy, store, plan)
            evidence = build_evidence(mode=args.mode, correlation_id=args.correlation_id, plan=plan, results=results)
    except (LifecycleError, json.JSONDecodeError, OSError, ValueError) as exc:
        evidence = build_evidence(
            mode=args.mode,
            correlation_id=args.correlation_id,
            plan=plan,
            results=results,
            error=str(exc),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "FAIL", "correlation_id": args.correlation_id, "output": str(args.output)}, ensure_ascii=False))
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = plan.get("summary") if isinstance(plan, dict) else None
    print(json.dumps({
        "status": evidence["status"],
        "mode": args.mode,
        "correlation_id": args.correlation_id,
        "output": str(args.output),
        "summary": summary,
        "rotations": len(results),
    }, ensure_ascii=False))
    return 0 if evidence["status"] == "PASS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
