from __future__ import annotations

import importlib.util
import json
import stat
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "scripts/todo_producer_keyvault_credit_gate.py"
SPEC = importlib.util.spec_from_file_location("todo_producer_keyvault_credit_gate", SOURCE)
assert SPEC and SPEC.loader
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def context():
    env = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": guard.REPOSITORY,
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_ACTOR": guard.DISPATCH_ACTOR,
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_SHA": "a" * 40,
        "GITHUB_RUN_ID": "39600000001",
        "CCP_AZURE_SUBSCRIPTION_ID": "11111111-1111-4111-8111-111111111111",
        "CCP_AZURE_TENANT_ID": "22222222-2222-4222-8222-222222222222",
        "REQSYS_KEY_VAULT_NAME": guard.VAULT,
    }
    event = {
        "repository": {"full_name": guard.REPOSITORY},
        "inputs": {"operation": guard.OPERATION, "authorization_comment_id": "6319619092"},
        "sender": {"login": guard.DISPATCH_ACTOR},
    }
    return env, event


def subscription(state="Enabled", spending="On", quota="FreeTrial"):
    return {
        "subscriptionId": "11111111-1111-4111-8111-111111111111",
        "state": state,
        "subscriptionPolicies": {"spendingLimit": spending, "quotaId": quota},
    }


def vault():
    return {
        "id": "/subscriptions/11111111-1111-4111-8111-111111111111"
              "/resourceGroups/rg-reqsys-ccp/providers/Microsoft.KeyVault/vaults/kv-reqsys-ccp",
        "name": guard.VAULT,
        "properties": {
            "tenantId": "22222222-2222-4222-8222-222222222222",
            "vaultUri": "https://kv-reqsys-ccp.vault.azure.net/",
            "provisioningState": "Succeeded",
        },
    }


def active_metadata():
    return {
        "id": "https://kv-reqsys-ccp.vault.azure.net/secrets/"
              + guard.SECRET + "/001",
        "enabled": True,
    }


def test_context_restricts_owner_issue_main_and_dev():
    env, event = context()
    assert guard.validate_context(env, event)["sha"] == "a" * 40
    for change in ("wrong_actor", "wrong_issue", "wrong_command", "wrong_branch",
                   "wrong_repo", "pull_request", "wrong_vault"):
        env2, event2 = context()
        if change == "wrong_actor":
            event2["sender"]["login"] = "another-user"
        elif change == "wrong_issue":
            event2["inputs"]["operation"] = "cycle"
        elif change == "wrong_command":
            event2["inputs"]["authorization_comment_id"] = "evil"
        elif change == "wrong_branch":
            env2["GITHUB_REF"] = "refs/heads/feature"
        elif change == "wrong_repo":
            env2["GITHUB_REPOSITORY"] = "other/repo"
        elif change == "pull_request":
            env2["GITHUB_EVENT_NAME"] = "pull_request"
        else:
            env2["REQSYS_KEY_VAULT_NAME"] = "kv-other"
        with pytest.raises(guard.Blocked):
            guard.validate_context(env2, event2)


@pytest.mark.parametrize(
    "sub,code",
    [
        (subscription(spending="Off"), "cost_unknown_no_azure_hard_stop"),
        (subscription(spending="CurrentPeriodOff"), "cost_unknown_no_azure_hard_stop"),
        (subscription(spending=None), "cost_unknown_no_azure_hard_stop"),
        (subscription(state="Disabled"), "subscription_not_enabled"),
        (subscription(quota=""), "subscription_credit_policy_unverified"),
        ({"subscriptionId": "else", "state": "Enabled",
          "subscriptionPolicies": {"quotaId": "FreeTrial", "spendingLimit": "On"}},
         "subscription_identity_mismatch"),
    ],
)
def test_cost_gate_fails_closed_without_credit_hard_stop(sub, code):
    with pytest.raises(guard.Blocked, match=f"^{code}$"):
        guard.assess_subscription(sub, "11111111-1111-4111-8111-111111111111")


def test_cost_gate_on_and_qualified_existing_vault(monkeypatch):
    env, event = context()
    ctx = guard.validate_context(env, event)
    paths = []

    def read_arm(path, blocker):
        paths.append((path, blocker))
        return subscription() if "Microsoft.KeyVault" not in path else vault()

    monkeypatch.setattr(guard, "read_arm", read_arm)
    proof = guard.cost_preflight(ctx)
    assert proof["decision"] == "COST_ZERO_CONFIRMED"
    assert proof["spending_limit"] == "On"
    assert proof["keyvault_data_plane_attempted"] is False
    assert len(paths) == 2
    assert all(x[0].startswith("https://management.azure.com") for x in paths)


def test_cost_gate_fails_for_different_vault_or_tenant():
    valid = vault()
    guard.assess_vault(valid, "11111111-1111-4111-8111-111111111111",
                       "22222222-2222-4222-8222-222222222222")
    wrong_tenant = vault()
    wrong_tenant["properties"]["tenantId"] = "33333333-3333-4333-8333-333333333333"
    with pytest.raises(guard.Blocked, match="dev_vault_not_qualified"):
        guard.assess_vault(wrong_tenant,
                           "11111111-1111-4111-8111-111111111111",
                           "22222222-2222-4222-8222-222222222222")
    wrong_resource = vault()
    wrong_resource["id"] = "/subscriptions/other/resourceGroups/other"
    with pytest.raises(guard.Blocked, match="dev_vault_identity_mismatch"):
        guard.assess_vault(wrong_resource,
                           "11111111-1111-4111-8111-111111111111",
                           "22222222-2222-4222-8222-222222222222")


@pytest.mark.parametrize("stderr,expected", [
    ("ERROR: (SecretNotFound) Missing secret", True),
    ("ERROR: (DeletedSecretNotFound) Missing deleted secret", True),
    ("ERROR: (Forbidden) Access denied", False),
    ("ERROR: (VaultNotFound) Vault missing", False),
    ("ERROR: (SecretNotFoundFake) malicious text", False),
    ("HTTP 403", False),
])
def test_metadata_absence_classifier_does_not_hide_permissions(stderr, expected):
    assert guard.missing_secret_error(stderr) is expected


def test_metadata_lookup_never_returns_plaintext(monkeypatch):
    seen = []

    def cli(argv):
        seen.append(argv)
        return 0, json.dumps(active_metadata()), ""

    monkeypatch.setattr(guard, "cli", cli)
    assert guard.metadata_lookup() == active_metadata()
    assert seen[0][-2:] == ["--output", "json"]
    assert "--query" in seen[0]
    assert "value" not in " ".join(seen[0]).split("{" + "id:id" + "}")[0]


def test_metadata_lookup_forbidden_is_not_missing(monkeypatch):
    monkeypatch.setattr(guard, "cli", lambda args: (1, "", "(Forbidden) Access denied"))
    with pytest.raises(guard.Blocked, match="keyvault_secret_metadata_unavailable"):
        guard.metadata_lookup()


def test_idempotent_existing_secret_does_not_change_or_recover(monkeypatch, tmp_path):
    env, event = context()
    ctx = guard.validate_context(env, event)
    monkeypatch.setattr(guard, "read_receipt", lambda *_: None)
    monkeypatch.setattr(guard, "cost_preflight", lambda *_: {"decision": "COST_ZERO_CONFIRMED"})

    def lookup(*, deleted=False):
        assert not deleted
        return active_metadata()

    monkeypatch.setattr(guard, "metadata_lookup", lookup)
    monkeypatch.setattr(guard, "cli", lambda *_: pytest.fail("no mutation allowed"))
    got = guard.recover_or_provision(ctx, tmp_path / "dummy.json")
    assert got["result"] == "ACTIVE_ALREADY_PRESENT"
    assert got["metadata_readback"] is True
    assert got["runtime_binding_verified"] is False


def test_soft_deleted_secret_recovers_without_creating(monkeypatch, tmp_path):
    env, event = context()
    ctx = guard.validate_context(env, event)
    monkeypatch.setattr(guard, "read_receipt", lambda *_: None)
    monkeypatch.setattr(guard, "cost_preflight", lambda *_: {"decision": "COST_ZERO_CONFIRMED"})
    readbacks = iter([None, active_metadata(), active_metadata()])
    calls = []
    def lookup(*, deleted=False):
        return active_metadata() if deleted else next(readbacks)
    def cli(args):
        calls.append(args)
        assert args[0:3] == ["keyvault", "secret", "recover"]
        return 0, "", ""
    monkeypatch.setattr(guard, "metadata_lookup", lookup)
    monkeypatch.setattr(guard, "cli", cli)
    result = guard.recover_or_provision(ctx, tmp_path / "dummy.json")
    assert result["result"] == "RECOVERED_RUNTIME_BINDING_UNVERIFIED"
    assert len(calls) == 1


def test_absent_secret_created_via_private_file_only(monkeypatch, tmp_path):
    env, event = context()
    ctx = guard.validate_context(env, event)
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    monkeypatch.setattr(guard, "read_receipt", lambda *_: None)
    monkeypatch.setattr(guard, "cost_preflight", lambda *_: {"decision": "COST_ZERO_CONFIRMED"})
    normal = iter([None, None, active_metadata(), active_metadata()])
    observed = {}
    monkeypatch.setattr(guard, "metadata_lookup",
                        lambda *, deleted=False: None if deleted else next(normal))
    def cli(args):
        observed["args"] = args
        name = args[args.index("--file") + 1]
        secret_file = Path(name)
        observed["mode"] = stat.S_IMODE(secret_file.stat().st_mode)
        observed["size"] = secret_file.stat().st_size
        observed["token"] = secret_file.read_text(encoding="utf-8")
        return 0, "", ""
    monkeypatch.setattr(guard, "cli", cli)
    result = guard.recover_or_provision(ctx, tmp_path / "proof.json")
    assert result["result"] == "PROVISIONED_RUNTIME_BINDING_PENDING"
    assert result["runtime_binding_verified"] is False
    assert result["no_atomic_creation_guarantee"] is True
    assert observed["mode"] == 0o600
    assert observed["size"] >= 48
    assert observed["token"] not in " ".join(observed["args"])
    assert "--file" in observed["args"]
    assert "--value" not in observed["args"]


def test_failed_cost_never_touches_key_vault(monkeypatch, tmp_path):
    monkeypatch.setattr(guard, "read_receipt", lambda *_: None)
    def blocked(_):
        raise guard.Blocked("cost_unknown_no_azure_hard_stop")
    monkeypatch.setattr(guard, "cost_preflight", blocked)
    monkeypatch.setattr(guard, "metadata_lookup", lambda **_: pytest.fail("metadata billed"))
    env, event = context()
    with pytest.raises(guard.Blocked, match="cost_unknown_no_azure_hard_stop"):
        guard.recover_or_provision(guard.validate_context(env, event),
                                   tmp_path / "proof.json")


def test_receipt_binds_identity_and_requires_private_mode(tmp_path):
    env, event = context()
    ctx = guard.validate_context(env, event)
    filename = tmp_path / "proof.json"
    proof = {"decision": "COST_ZERO_CONFIRMED", "run_id": ctx["run_id"],
             "head_sha": ctx["sha"], "vault": guard.VAULT,
             "spending_limit": "On", "existing_vault_verified": True}
    guard.write_receipt(filename, proof)
    guard.read_receipt(filename, ctx)
    filename.chmod(0o644)
    with pytest.raises(guard.Blocked, match="cost_receipt_not_trusted"):
        guard.read_receipt(filename, ctx)



def test_owner_comment_validated_against_live_issue_and_recent_time():
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    record = {
        "id": 6319619092,
        "issue_url": f"https://api.github.com/repos/{guard.REPOSITORY}/issues/1705",
        "user": {"login": guard.OWNER},
        "body": guard.COMMAND,
        "created_at": now.isoformat(),
    }
    guard.validate_comment_record(record, "6319619092", now)
    for mutation in ("wrong_user", "wrong_issue", "wrong_body", "expired"):
        changed = json.loads(json.dumps(record))
        if mutation == "wrong_user":
            changed["user"]["login"] = "unknown"
        elif mutation == "wrong_issue":
            changed["issue_url"] += "0"
        elif mutation == "wrong_body":
            changed["body"] += " extra"
        else:
            changed["created_at"] = (now - timedelta(hours=2)).isoformat()
        with pytest.raises(guard.Blocked):
            guard.validate_comment_record(changed, "6319619092", now)
