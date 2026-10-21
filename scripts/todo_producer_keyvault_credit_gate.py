#!/usr/bin/env python3
"""DEV-only Azure spending-limit gate and narrow TODO producer secret recovery.

Only callable after a fixed owner issue-comment event, on the default branch.
No secret values, raw CLI responses, credentials or token URLs are logged.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPOSITORY = "ericson-j-santos/reqsys-v2-enterprise-real"
OWNER = "ericson-j-santos"
ISSUE_NUMBER = 2973
COMMAND = "/reqsys recover-todo-producer-keyvault-dev"
VAULT = "kv-reqsys-ccp"
RESOURCE_GROUP = "rg-reqsys-ccp"
SECRET = "reqsys-pc24x7-todo-runtime-producer-token"
SHA = re.compile(r"^[0-9a-f]{40}$")
GUID = re.compile(r"^[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$")


class Blocked(RuntimeError):
    pass


def require(condition: object, code: str) -> None:
    if not condition:
        raise Blocked(code)


def validate_context(env: dict[str, str], event: dict) -> dict[str, str]:
    """Re-attest immutable action context in both phases; never trust CLI inputs."""
    require(env.get("GITHUB_ACTIONS") == "true"
            and env.get("GITHUB_REPOSITORY") == REPOSITORY
            and env.get("GITHUB_EVENT_NAME") == "issue_comment"
            and env.get("GITHUB_REF") == "refs/heads/main"
            and SHA.fullmatch(env.get("GITHUB_SHA", "")) is not None
            and re.fullmatch(r"[1-9][0-9]{0,19}", env.get("GITHUB_RUN_ID", "")) is not None,
            "github_context_invalid")
    require(isinstance(event, dict)
            and event.get("repository", {}).get("full_name") == REPOSITORY
            and event.get("issue", {}).get("number") == ISSUE_NUMBER
            and event.get("issue", {}).get("pull_request") is None
            and event.get("comment", {}).get("body") == COMMAND
            and event.get("comment", {}).get("user", {}).get("login") == OWNER
            and event.get("sender", {}).get("login") == OWNER,
            "github_authorization_invalid")
    subscription = env.get("CCP_AZURE_SUBSCRIPTION_ID", "")
    tenant = env.get("CCP_AZURE_TENANT_ID", "")
    require(GUID.fullmatch(subscription) is not None
            and GUID.fullmatch(tenant) is not None
            and env.get("REQSYS_KEY_VAULT_NAME") == VAULT,
            "dev_scope_configuration_invalid")
    return {"subscription": subscription.lower(), "tenant": tenant.lower(),
            "sha": env["GITHUB_SHA"], "run_id": env["GITHUB_RUN_ID"]}


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
    return {"schema_version": 1, "decision": "COST_ZERO_CONFIRMED",
            "run_id": ctx["run_id"], "head_sha": ctx["sha"],
            "subscription_state": "Enabled", "spending_limit": "On",
            "existing_vault_verified": True, "vault": VAULT,
            "keyvault_data_plane_attempted": False,
            "production_touched": False,
            "evaluated_at": datetime.now(timezone.utc).isoformat()}


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
            and doc.get("decision") == "COST_ZERO_CONFIRMED"
            and doc.get("run_id") == ctx["run_id"]
            and doc.get("head_sha") == ctx["sha"]
            and doc.get("vault") == VAULT
            and doc.get("spending_limit") == "On"
            and doc.get("existing_vault_verified") is True,
            "cost_receipt_not_trusted")


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
    # Fresh ARM policy and vault readback: a prior receipt cannot bypass costs.
    fresh = cost_preflight(ctx)
    require(fresh["decision"] == "COST_ZERO_CONFIRMED",
            "cost_preflight_changed")
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
        "schema_version": 1, "decision": "COST_ZERO_CONFIRMED",
        "result": state, "run_id": ctx["run_id"], "head_sha": ctx["sha"],
        "metadata_readback": True, "secret_value_exposed": False,
        "runtime_binding_verified": False,
        "no_atomic_creation_guarantee": state == "PROVISIONED_RUNTIME_BINDING_PENDING",
        "deploy_executed": False, "production_touched": False,
        "rbac_mutated": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["cost", "secret"])
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        context_file = Path(os.environ["GITHUB_EVENT_PATH"])
        require(context_file.stat().st_size <= 262144, "github_event_too_large")
        event = json.loads(context_file.read_text(encoding="utf-8"))
        ctx = validate_context(os.environ, event)
        path = receipt_path(args.receipt, os.environ)
        if args.phase == "cost":
            proof = cost_preflight(ctx)
            write_receipt(path, proof)
            print(json.dumps({"decision": proof["decision"],
                              "subscription_state": proof["subscription_state"],
                              "spending_limit": proof["spending_limit"],
                              "existing_vault_verified": True, "secret_touched": False},
                             sort_keys=True))
        else:
            result = recover_or_provision(ctx, path)
            print(json.dumps(result, sort_keys=True))
        return 0
    except Blocked as exc:
        print(json.dumps({"decision": "COST_UNKNOWN_BLOCKED" if args.phase == "cost" else "BLOCKED",
                          "reason": str(exc), "secret_value_exposed": False},
                         sort_keys=True))
        return 2
    except (KeyError, OSError, ValueError, TypeError):
        print(json.dumps({"decision": "BLOCKED", "reason": "guard_internal_error",
                          "secret_value_exposed": False}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
