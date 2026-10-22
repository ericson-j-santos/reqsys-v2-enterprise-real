#!/usr/bin/env python3
"""DEV-only Azure spending-limit gate and narrow TODO producer secret recovery.

Only callable after the owner command is authenticated by the existing Actions
Gateway and re-verified from the GitHub issue-comment API on the main branch.
No secret values, raw CLI responses, credentials or token URLs are logged.

``spendingLimit=On`` is only an Azure overage hard-stop. It is never treated as
proof that a Key Vault operation has literal zero cost.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import stat
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPOSITORY = "ericson-j-santos/reqsys-v2-enterprise-real"
OWNER = "ericson-j-santos"
WORKFLOW_PATH = ".github/workflows/todo-global-hourly-cycle.yml"
WORKFLOW_REF = f"{REPOSITORY}/{WORKFLOW_PATH}@refs/heads/main"
AUTHORIZATION_ISSUE = 1705
COMMAND = "/reqsys run todo-producer-keyvault-dev"
OPERATION = "producer-credit-gated"
DISPATCH_ACTOR = "github-actions[bot]"
VAULT = "kv-reqsys-ccp"
RESOURCE_GROUP = "rg-reqsys-ccp"
SECRET = "reqsys-pc24x7-todo-runtime-producer-token"
HARD_STOP_DECISION = "AZURE_SPENDING_LIMIT_ON_CONFIRMED"
DATA_PLANE_BLOCKED_DECISION = "KEYVAULT_DATA_PLANE_BLOCKED"
SHA = re.compile(r"^[0-9a-f]{40}$")
GUID = re.compile(r"^[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$")
RUNTIME_TOKEN = re.compile(r"^(?:[A-Za-z0-9_-]{43}|[A-Za-z0-9_-]{64})$")


class Blocked(RuntimeError):
    pass


def require(condition: object, code: str) -> None:
    if not condition:
        raise Blocked(code)


def workflow_identity_valid(env: dict[str, str]) -> bool:
    """Bind privileged phases to this exact workflow file and checked-out SHA."""
    workflow_sha = env.get("GITHUB_WORKFLOW_SHA", "")
    return bool(
        env.get("GITHUB_WORKFLOW_REF") == WORKFLOW_REF
        and SHA.fullmatch(workflow_sha) is not None
        and workflow_sha == env.get("GITHUB_SHA")
        and re.fullmatch(r"[1-9][0-9]{0,9}", env.get("GITHUB_RUN_ATTEMPT", ""))
    )


def validate_context(env: dict[str, str], event: dict) -> dict[str, str]:
    """Re-attest immutable action context in both phases; never trust CLI inputs."""
    require(env.get("GITHUB_ACTIONS") == "true"
            and env.get("GITHUB_REPOSITORY") == REPOSITORY
            and env.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
            and env.get("GITHUB_ACTOR") == DISPATCH_ACTOR
            and env.get("GITHUB_REF") == "refs/heads/main"
            and SHA.fullmatch(env.get("GITHUB_SHA", "")) is not None
            and re.fullmatch(r"[1-9][0-9]{0,19}", env.get("GITHUB_RUN_ID", "")) is not None
            and workflow_identity_valid(env),
            "github_context_invalid")
    inputs = event.get("inputs") or {}
    comment_id = inputs.get("authorization_comment_id")
    require(isinstance(event, dict)
            and event.get("repository", {}).get("full_name") == REPOSITORY
            and event.get("sender", {}).get("login") == DISPATCH_ACTOR
            and inputs.get("operation") == OPERATION
            and isinstance(comment_id, str)
            and re.fullmatch(r"[1-9][0-9]{0,19}", comment_id) is not None,
            "github_authorization_invalid")
    subscription = env.get("CCP_AZURE_SUBSCRIPTION_ID", "")
    tenant = env.get("CCP_AZURE_TENANT_ID", "")
    require(GUID.fullmatch(subscription) is not None
            and GUID.fullmatch(tenant) is not None
            and env.get("REQSYS_KEY_VAULT_NAME") == VAULT,
            "dev_scope_configuration_invalid")
    return {"subscription": subscription.lower(), "tenant": tenant.lower(),
            "sha": env["GITHUB_SHA"], "run_id": env["GITHUB_RUN_ID"],
            "authorization_comment_id": comment_id}

def validate_cycle_cost_context(env: dict[str, str], event: dict) -> dict[str, str]:
    """Attest the scheduled or owner-dispatched cycle before any Azure read."""
    event_name = env.get("GITHUB_EVENT_NAME", "")
    require(env.get("GITHUB_ACTIONS") == "true"
            and env.get("GITHUB_REPOSITORY") == REPOSITORY
            and env.get("GITHUB_REF") == "refs/heads/main"
            and SHA.fullmatch(env.get("GITHUB_SHA", "")) is not None
            and re.fullmatch(r"[1-9][0-9]{0,19}", env.get("GITHUB_RUN_ID", "")) is not None
            and workflow_identity_valid(env)
            and event_name in {"schedule", "workflow_dispatch"},
            "cycle_cost_context_invalid")
    require(isinstance(event, dict)
            and isinstance(event.get("repository"), dict)
            and event["repository"].get("full_name") == REPOSITORY,
            "cycle_cost_event_invalid")
    if event_name == "workflow_dispatch":
        sender = (event.get("sender") or {}).get("login")
        require((event.get("inputs") or {}).get("operation") == "cycle"
                and sender == OWNER
                and env.get("GITHUB_ACTOR") == OWNER,
                "cycle_cost_event_invalid")
    else:
        require(not event.get("inputs"), "cycle_cost_event_invalid")
    subscription = env.get("CCP_AZURE_SUBSCRIPTION_ID", "")
    tenant = env.get("CCP_AZURE_TENANT_ID", "")
    require(GUID.fullmatch(subscription) is not None
            and GUID.fullmatch(tenant) is not None
            and env.get("REQSYS_KEY_VAULT_NAME") == VAULT,
            "dev_scope_configuration_invalid")
    return {"subscription": subscription.lower(), "tenant": tenant.lower(),
            "sha": env["GITHUB_SHA"], "run_id": env["GITHUB_RUN_ID"],
            "run_attempt": env["GITHUB_RUN_ATTEMPT"]}


def validate_runtime_context(env: dict[str, str], event: dict) -> dict[str, str]:
    """Bind the manual runtime path to this workflow, SHA and DEV scope."""
    actor = env.get("GITHUB_ACTOR", "")
    require(env.get("GITHUB_ACTIONS") == "true"
            and env.get("GITHUB_REPOSITORY") == REPOSITORY
            and env.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
            and env.get("GITHUB_REF") == "refs/heads/main"
            and SHA.fullmatch(env.get("GITHUB_SHA", "")) is not None
            and re.fullmatch(r"[1-9][0-9]{0,19}", env.get("GITHUB_RUN_ID", "")) is not None
            and workflow_identity_valid(env),
            "runtime_context_invalid")
    require(isinstance(event, dict)
            and event.get("repository", {}).get("full_name") == REPOSITORY
            and (event.get("inputs") or {}).get("operation") == "reconcile-runtime"
            and actor == OWNER
            and (event.get("sender") or {}).get("login") == OWNER,
            "runtime_event_invalid")
    subscription = env.get("CCP_AZURE_SUBSCRIPTION_ID", "")
    tenant = env.get("CCP_AZURE_TENANT_ID", "")
    require(GUID.fullmatch(subscription) is not None
            and GUID.fullmatch(tenant) is not None
            and env.get("REQSYS_KEY_VAULT_NAME") == VAULT,
            "dev_scope_configuration_invalid")
    return {"subscription": subscription.lower(), "tenant": tenant.lower(),
            "sha": env["GITHUB_SHA"], "run_id": env["GITHUB_RUN_ID"],
            "run_attempt": env["GITHUB_RUN_ATTEMPT"]}


def validate_comment_record(value: dict, comment_id: str, now: datetime) -> None:
    """Validate authoritative owner comment, not user supplied dispatch inputs."""
    expected_issue = f"https://api.github.com/repos/{REPOSITORY}/issues/{AUTHORIZATION_ISSUE}"
    require(isinstance(value, dict)
            and str(value.get("id")) == comment_id
            and value.get("issue_url") == expected_issue
            and value.get("user", {}).get("login") == OWNER
            and value.get("body") == COMMAND, "owner_comment_mismatch")
    try:
        created = datetime.fromisoformat(value["created_at"].replace("Z", "+00:00"))
        age = (now - created).total_seconds()
    except (TypeError, ValueError, KeyError):
        raise Blocked("owner_comment_time_invalid") from None
    require(created.tzinfo is not None and -60 <= age <= 5400,
            "owner_comment_expired")


def verify_owner_comment(ctx: dict[str, str], env: dict[str, str]) -> None:
    """Read one exact GitHub issue comment with a read-only token; never print it."""
    token = env.get("GH_TOKEN", "")
    require(20 < len(token) < 16384 and not any(ch in token for ch in "\r\n"),
            "github_read_token_unavailable")
    url = ("https://api.github.com/repos/" + REPOSITORY
           + "/issues/comments/" + ctx["authorization_comment_id"])
    request = Request(url, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "User-Agent": "ReqSysTodoProducerCreditGate/1.0",
    })
    try:
        with urlopen(request, timeout=12) as response:
            data = response.read(32769)
        require(len(data) <= 32768, "github_comment_response_invalid")
        item = json.loads(data)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        raise Blocked("github_owner_comment_read_unavailable") from None
    validate_comment_record(item, ctx["authorization_comment_id"],
                            datetime.now(timezone.utc))


def cli(arguments: list[str]) -> tuple[int, str, str]:
    """Bounded non-shell Azure CLI call. Keep stdout and stderr private."""
    try:
        result = subprocess.run(["az", *arguments], check=False, capture_output=True,
                                text=True, timeout=45)
    except (OSError, subprocess.TimeoutExpired):
        raise Blocked("azure_cli_unavailable") from None
    require(len(result.stdout) <= 262144 and len(result.stderr) <= 32768,
            "azure_cli_response_too_large")
    return result.returncode, result.stdout, result.stderr


def read_arm(path: str, blocker: str) -> dict:
    require(path.startswith("https://management.azure.com/subscriptions/")
            and all(token not in path for token in ("\r", "\n", "#")),
            "arm_target_invalid")
    status, out, _error = cli(["rest", "--method", "get", "--url", path,
                               "--only-show-errors", "--output", "json"])
    require(status == 0, blocker)
    try:
        data = json.loads(out)
    except (TypeError, ValueError):
        raise Blocked(blocker) from None
    require(isinstance(data, dict), blocker)
    return data


def assess_subscription(value: dict, sub: str) -> None:
    require(isinstance(value, dict) and str(value.get("subscriptionId", "")).lower() == sub,
            "subscription_identity_mismatch")
    require(value.get("state") == "Enabled", "subscription_not_enabled")
    policy = value.get("subscriptionPolicies")
    require(isinstance(policy, dict)
            and isinstance(policy.get("quotaId"), str)
            and bool(policy.get("quotaId").strip()),
            "subscription_credit_policy_unverified")
    require(policy.get("spendingLimit") == "On",
            "cost_unknown_no_azure_hard_stop")


def assess_vault(value: dict, subscription: str, tenant: str) -> None:
    expected_id = (
        f"/subscriptions/{subscription}/resourceGroups/{RESOURCE_GROUP}"
        f"/providers/Microsoft.KeyVault/vaults/{VAULT}"
    )
    require(isinstance(value, dict)
            and str(value.get("id", "")).lower() == expected_id.lower()
            and value.get("name") == VAULT, "dev_vault_identity_mismatch")
    properties = value.get("properties")
    require(isinstance(properties, dict)
            and str(properties.get("tenantId", "")).lower() == tenant
            and properties.get("provisioningState") == "Succeeded"
            and properties.get("vaultUri", "").rstrip("/").lower()
            == f"https://{VAULT}.vault.azure.net", "dev_vault_not_qualified")


def cost_preflight(ctx: dict[str, str]) -> dict:
    """Observe Azure hard-stop state; do not infer literal transaction cost."""
    sub = ctx["subscription"]
    subscription = read_arm(
        f"https://management.azure.com/subscriptions/{sub}?api-version=2022-12-01",
        "subscription_arm_read_unavailable",
    )
    assess_subscription(subscription, sub)
    vault = read_arm(
        f"https://management.azure.com/subscriptions/{sub}/resourceGroups/"
        f"{RESOURCE_GROUP}/providers/Microsoft.KeyVault/vaults/"
        f"{VAULT}?api-version=2023-07-01",
        "vault_arm_read_unavailable",
    )
    assess_vault(vault, sub, ctx["tenant"])
    return {"schema_version": 2, "decision": HARD_STOP_DECISION,
            "run_id": ctx["run_id"], "head_sha": ctx["sha"],
            "subscription_state": "Enabled", "spending_limit": "On",
            "overage_hard_stop_present": True,
            "literal_zero_cost_verified": False,
            "keyvault_data_plane_allowed": False,
            "existing_vault_verified": True, "vault": VAULT,
            "keyvault_data_plane_attempted": False,
            "production_touched": False,
            "evaluated_at": datetime.now(timezone.utc).isoformat()}


def require_literal_zero(proof: dict) -> None:
    """Fail closed unless an authoritative, non-user-controlled proof exists."""
    require(isinstance(proof, dict)
            and proof.get("decision") == HARD_STOP_DECISION
            and proof.get("overage_hard_stop_present") is True
            and proof.get("literal_zero_cost_verified") is True
            and proof.get("keyvault_data_plane_allowed") is True,
            "literal_zero_cost_unproven")


def receipt_path(path: Path, env: dict[str, str]) -> Path:
    root = Path(env["RUNNER_TEMP"]).resolve(strict=True)
    require(path.parent.resolve() == root and path.name.startswith("todo-producer-")
            and path.suffix == ".json", "receipt_path_invalid")
    return path


def write_receipt(path: Path, data: dict) -> None:
    raw = (json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n").encode()
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.write(descriptor, raw)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def read_receipt(path: Path, ctx: dict[str, str]) -> None:
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600
            and info.st_uid == os.getuid() and info.st_size <= 4096,
            "cost_receipt_not_trusted")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        raise Blocked("cost_receipt_not_trusted") from None
    require(isinstance(doc, dict)
            and doc.get("schema_version") == 2
            and doc.get("decision") == HARD_STOP_DECISION
            and doc.get("run_id") == ctx["run_id"]
            and doc.get("head_sha") == ctx["sha"]
            and doc.get("vault") == VAULT
            and doc.get("spending_limit") == "On"
            and doc.get("overage_hard_stop_present") is True
            and doc.get("literal_zero_cost_verified") is True
            and doc.get("keyvault_data_plane_allowed") is True
            and doc.get("existing_vault_verified") is True,
            "cost_receipt_not_trusted")


def validate_runtime_token(value: str) -> str:
    """Enforce the exact token contract immediately before any sensitive sink."""
    require(isinstance(value, str)
            and not any(character in value for character in ("\r", "\n", "\x00"))
            and RUNTIME_TOKEN.fullmatch(value) is not None,
            "keyvault_secret_value_invalid")
    return value


def canonical_runtime_token(stdout: str) -> str:
    """Remove one Azure CLI record terminator, then validate the token itself."""
    require(isinstance(stdout, str) and 0 < len(stdout) <= 65,
            "keyvault_secret_value_invalid")
    value = stdout[:-1] if stdout.endswith("\n") else stdout
    return validate_runtime_token(value)


def read_runtime_token() -> str:
    """Read one existing value without ever placing it in a shell variable."""
    rc, stdout, _stderr = cli([
        "keyvault", "secret", "show", "--vault-name", VAULT,
        "--name", SECRET, "--query", "value", "--output", "tsv",
        "--only-show-errors",
    ])
    require(rc == 0, "keyvault_secret_read_blocked")
    return canonical_runtime_token(stdout)


def export_runtime_token(token: str, env: dict[str, str]) -> None:
    """Validate again before registering a mask or appending to GITHUB_ENV."""
    canonical = validate_runtime_token(token)
    root = Path(env["RUNNER_TEMP"]).resolve(strict=True)
    destination = Path(env["GITHUB_ENV"])
    info = destination.lstat()
    resolved = destination.resolve(strict=True)
    require(root in resolved.parents
            and stat.S_ISREG(info.st_mode)
            and info.st_uid == os.getuid(),
            "github_env_not_trusted")
    flags = os.O_WRONLY | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(destination, flags)
    try:
        opened = os.fstat(descriptor)
        require(stat.S_ISREG(opened.st_mode)
                and opened.st_ino == info.st_ino
                and opened.st_dev == info.st_dev,
                "github_env_not_trusted")
        print(f"::add-mask::{canonical}")
        encoded = f"TODO_GLOBAL_RUNTIME_TOKEN={canonical}\n".encode("ascii")
        require(os.write(descriptor, encoded) == len(encoded),
                "github_env_write_failed")
    finally:
        os.close(descriptor)


def missing_secret_error(stderr: str) -> bool:
    # 403 and unexpected failures may NEVER be interpreted as absence.
    return bool(re.search(r"\b(?:SecretNotFound|DeletedSecretNotFound)\b",
                          stderr, flags=re.IGNORECASE))


def metadata_lookup(*, deleted: bool = False) -> dict | None:
    action = "show-deleted" if deleted else "show"
    rc, stdout, stderr = cli(
        ["keyvault", "secret", action, "--vault-name", VAULT, "--name", SECRET,
         "--query", "{id:id,enabled:attributes.enabled}",
         "--only-show-errors", "--output", "json"])
    if rc != 0:
        if missing_secret_error(stderr):
            return None
        raise Blocked("keyvault_secret_metadata_unavailable")
    try:
        data = json.loads(stdout)
    except (ValueError, TypeError):
        raise Blocked("keyvault_secret_metadata_invalid") from None
    require(isinstance(data, dict), "keyvault_secret_metadata_invalid")
    expected = f"https://{VAULT}.vault.azure.net/"
    identifier = data.get("id", "")
    prefix = "deletedsecrets" if deleted else "secrets"
    require(isinstance(identifier, str)
            and identifier.lower().startswith((expected + prefix + "/" + SECRET).lower())
            and (len(identifier) == len(expected + prefix + "/" + SECRET)
                 or identifier[len(expected + prefix + "/" + SECRET)] == "/"),
            "keyvault_secret_identity_invalid")
    if not deleted:
        require(data.get("enabled") is True, "keyvault_secret_disabled")
    return data


def recover_or_provision(ctx: dict[str, str], proof: Path) -> dict:
    read_receipt(proof, ctx)
    # A receipt is never enough: re-attest immediately before the first data-plane call.
    fresh = cost_preflight(ctx)
    require_literal_zero(fresh)
    active = metadata_lookup()
    if active is not None:
        state = "ACTIVE_ALREADY_PRESENT"
    else:
        deleted = metadata_lookup(deleted=True)
        if deleted is not None:
            rc, _stdout, _stderr = cli(
                ["keyvault", "secret", "recover", "--vault-name", VAULT,
                 "--name", SECRET, "--only-show-errors", "--output", "none"])
            require(rc == 0, "keyvault_secret_recover_blocked")
            state = "RECOVERED_RUNTIME_BINDING_UNVERIFIED"
        else:
            # A second read reduces races with existing producers; never overwrite
            # a secret observed as active. Azure create is not an atomic CAS.
            if metadata_lookup() is not None:
                state = "ACTIVE_ALREADY_PRESENT"
            else:
                base = Path(os.environ["RUNNER_TEMP"])
                with tempfile.TemporaryDirectory(prefix="todo-producer-private-", dir=base) as tmp:
                    value_file = Path(tmp) / "producer-token"
                    descriptor = os.open(value_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                    try:
                        token = secrets.token_urlsafe(48).encode("utf-8")
                        os.write(descriptor, token)
                        os.fsync(descriptor)
                    finally:
                        os.close(descriptor)
                    rc, _stdout, _stderr = cli([
                        "keyvault", "secret", "set", "--vault-name", VAULT,
                        "--name", SECRET, "--file", str(value_file),
                        "--encoding", "utf-8",
                        "--tags", "environment=dev",
                        "consumer=github-actions-and-runtime",
                        "scope=todo_runtime:producer",
                        "--only-show-errors", "--output", "none",
                    ])
                    require(rc == 0, "keyvault_secret_provision_blocked")
                state = "PROVISIONED_RUNTIME_BINDING_PENDING"
    require(metadata_lookup() is not None, "keyvault_secret_readback_failed")
    return {
        "schema_version": 2, "decision": HARD_STOP_DECISION,
        "literal_zero_cost_verified": True,
        "result": state, "run_id": ctx["run_id"], "head_sha": ctx["sha"],
        "metadata_readback": True, "secret_value_exposed": False,
        "runtime_binding_verified": False,
        "no_atomic_creation_guarantee": state == "PROVISIONED_RUNTIME_BINDING_PENDING",
        "deploy_executed": False, "production_touched": False,
        "rbac_mutated": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=[
        "cost", "secret", "cycle-secret", "runtime-cost", "export-token",
    ])
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    try:
        context_file = Path(os.environ["GITHUB_EVENT_PATH"])
        require(context_file.stat().st_size <= 262144, "github_event_too_large")
        event = json.loads(context_file.read_text(encoding="utf-8"))
        if args.phase == "cycle-secret":
            ctx = validate_cycle_cost_context(os.environ, event)
            proof = cost_preflight(ctx)
            require_literal_zero(proof)
            token = read_runtime_token()
            export_runtime_token(token, os.environ)
            print(json.dumps({"decision": proof["decision"],
                              "spending_limit": proof["spending_limit"],
                              "literal_zero_cost_verified": True,
                              "secret_read": True,
                              "secret_value_exposed": False}, sort_keys=True))
            return 0
        if args.phase == "export-token":
            ctx = validate_runtime_context(os.environ, event)
            proof = cost_preflight(ctx)
            require_literal_zero(proof)
            token = read_runtime_token()
            export_runtime_token(token, os.environ)
            print(json.dumps({"decision": "TOKEN_EXPORTED",
                              "token_contract_valid": True,
                              "secret_value_exposed": False}, sort_keys=True))
            return 0
        if args.phase == "runtime-cost":
            ctx = validate_runtime_context(os.environ, event)
            proof = cost_preflight(ctx)
            require_literal_zero(proof)
            print(json.dumps({"decision": proof["decision"],
                              "literal_zero_cost_verified": True,
                              "secret_touched": False}, sort_keys=True))
            return 0
        ctx = validate_context(os.environ, event)
        verify_owner_comment(ctx, os.environ)
        require(args.receipt is not None, "receipt_required")
        path = receipt_path(args.receipt, os.environ)
        if args.phase == "cost":
            proof = cost_preflight(ctx)
            require_literal_zero(proof)
            write_receipt(path, proof)
            print(json.dumps({"decision": proof["decision"],
                              "subscription_state": proof["subscription_state"],
                              "spending_limit": proof["spending_limit"],
                              "literal_zero_cost_verified": True,
                              "existing_vault_verified": True, "secret_touched": False},
                             sort_keys=True))
        else:
            result = recover_or_provision(ctx, path)
            print(json.dumps(result, sort_keys=True))
        return 0
    except Blocked as exc:
        reason = str(exc)
        if reason == "literal_zero_cost_unproven":
            payload = {
                "decision": DATA_PLANE_BLOCKED_DECISION,
                "hard_stop_decision": HARD_STOP_DECISION,
                "literal_zero_cost_verified": False,
                "reason": reason,
                "secret_value_exposed": False,
            }
        else:
            payload = {
                "decision": "COST_UNKNOWN_BLOCKED"
                if args.phase in ("cost", "cycle-secret", "runtime-cost", "export-token")
                else "BLOCKED",
                "reason": reason,
                "secret_value_exposed": False,
            }
        print(json.dumps(payload, sort_keys=True))
        return 2
    except (KeyError, OSError, ValueError, TypeError):
        print(json.dumps({"decision": "BLOCKED", "reason": "guard_internal_error",
                          "secret_value_exposed": False}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
