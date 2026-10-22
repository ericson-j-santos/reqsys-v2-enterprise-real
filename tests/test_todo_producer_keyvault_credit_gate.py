from __future__ import annotations

import importlib.util
import json
import stat
import sys
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
        "GITHUB_WORKFLOW_REF": guard.WORKFLOW_REF,
        "GITHUB_WORKFLOW_SHA": "a" * 40,
        "GITHUB_RUN_ID": "39600000001",
        "GITHUB_RUN_ATTEMPT": "1",
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


def literal_zero_proof():
    return {
        "decision": guard.HARD_STOP_DECISION,
        "overage_hard_stop_present": True,
        "literal_zero_cost_verified": True,
        "keyvault_data_plane_allowed": True,
    }


def test_context_restricts_owner_issue_main_and_dev():
    env, event = context()
    assert guard.validate_context(env, event)["sha"] == "a" * 40
    for change in ("wrong_actor", "wrong_issue", "wrong_command", "wrong_branch",
                   "wrong_repo", "pull_request", "wrong_vault", "workflow_ref",
                   "workflow_sha", "workflow_commit"):
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
        elif change == "workflow_ref":
            env2["GITHUB_WORKFLOW_REF"] += "-other"
        elif change == "workflow_sha":
            env2["GITHUB_WORKFLOW_SHA"] = "not-a-sha"
        elif change == "workflow_commit":
            env2["GITHUB_WORKFLOW_SHA"] = "b" * 40
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
    assert proof["decision"] == guard.HARD_STOP_DECISION
    assert proof["spending_limit"] == "On"
    assert proof["overage_hard_stop_present"] is True
    assert proof["literal_zero_cost_verified"] is False
    assert proof["keyvault_data_plane_allowed"] is False
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
    monkeypatch.setattr(guard, "cost_preflight", lambda *_: literal_zero_proof())

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
    monkeypatch.setattr(guard, "cost_preflight", lambda *_: literal_zero_proof())
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
    monkeypatch.setattr(guard, "cost_preflight", lambda *_: literal_zero_proof())
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


def test_hard_stop_without_literal_zero_never_touches_key_vault(monkeypatch, tmp_path):
    monkeypatch.setattr(guard, "read_receipt", lambda *_: None)
    proof = literal_zero_proof()
    proof["literal_zero_cost_verified"] = False
    proof["keyvault_data_plane_allowed"] = False
    monkeypatch.setattr(guard, "cost_preflight", lambda *_: proof)
    monkeypatch.setattr(guard, "metadata_lookup",
                        lambda **_: pytest.fail("Key Vault data-plane reached"))
    env, event = context()
    with pytest.raises(guard.Blocked, match="literal_zero_cost_unproven"):
        guard.recover_or_provision(guard.validate_context(env, event),
                                   tmp_path / "proof.json")


def test_receipt_binds_identity_and_requires_private_mode(tmp_path):
    env, event = context()
    ctx = guard.validate_context(env, event)
    filename = tmp_path / "proof.json"
    proof = {"schema_version": 2, "decision": guard.HARD_STOP_DECISION,
             "run_id": ctx["run_id"],
             "head_sha": ctx["sha"], "vault": guard.VAULT,
             "spending_limit": "On", "existing_vault_verified": True,
             "overage_hard_stop_present": True,
             "literal_zero_cost_verified": True,
             "keyvault_data_plane_allowed": True}
    guard.write_receipt(filename, proof)
    guard.read_receipt(filename, ctx)
    filename.chmod(0o644)
    with pytest.raises(guard.Blocked, match="cost_receipt_not_trusted"):
        guard.read_receipt(filename, ctx)


def test_observational_hard_stop_receipt_is_not_data_plane_authorization(tmp_path):
    env, event = context()
    ctx = guard.validate_context(env, event)
    filename = tmp_path / "proof.json"
    proof = {"schema_version": 2, "decision": guard.HARD_STOP_DECISION,
             "run_id": ctx["run_id"],
             "head_sha": ctx["sha"], "vault": guard.VAULT,
             "spending_limit": "On", "existing_vault_verified": True,
             "overage_hard_stop_present": True,
             "literal_zero_cost_verified": False,
             "keyvault_data_plane_allowed": False}
    guard.write_receipt(filename, proof)
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


def _cycle_context():
    env, _ = context()
    env["GITHUB_EVENT_NAME"] = "schedule"
    event = {"repository": {"full_name": guard.REPOSITORY}}
    return env, event


def test_hourly_cost_context_allows_schedule_and_typed_main_dispatch():
    env, event = _cycle_context()
    ctx = guard.validate_cycle_cost_context(env, event)
    assert ctx["subscription"] == env["CCP_AZURE_SUBSCRIPTION_ID"]
    env["GITHUB_EVENT_NAME"] = "workflow_dispatch"
    env["GITHUB_ACTOR"] = guard.OWNER
    event.update({"sender": {"login": guard.OWNER}, "inputs": {"operation": "cycle"}})
    assert guard.validate_cycle_cost_context(env, event)["sha"] == "a" * 40


def test_runtime_context_allows_owner_and_rejects_uncorrelated_bot():
    env, event = context()
    env["GITHUB_ACTOR"] = guard.OWNER
    event["sender"]["login"] = guard.OWNER
    event["inputs"] = {"operation": "reconcile-runtime"}
    assert guard.validate_runtime_context(env, event)["sha"] == "a" * 40

    env["GITHUB_ACTOR"] = guard.DISPATCH_ACTOR
    event["sender"]["login"] = guard.DISPATCH_ACTOR
    with pytest.raises(guard.Blocked, match="runtime_event_invalid"):
        guard.validate_runtime_context(env, event)


@pytest.mark.parametrize("change", [
    "branch", "repo", "event", "vault", "subscription", "wrong_operation",
    "wrong_sender", "bot_sender", "scheduled_with_inputs", "workflow_ref",
    "workflow_sha", "workflow_commit",
])
def test_hourly_cost_context_blocks_invalid_identity(change):
    env, event = _cycle_context()
    if change == "branch":
        env["GITHUB_REF"] = "refs/heads/feature"
    elif change == "repo":
        event["repository"]["full_name"] = "unknown/repo"
    elif change == "event":
        env["GITHUB_EVENT_NAME"] = "pull_request"
    elif change == "vault":
        env["REQSYS_KEY_VAULT_NAME"] = "other"
    elif change == "subscription":
        env["CCP_AZURE_SUBSCRIPTION_ID"] = "not-a-guid"
    elif change == "workflow_ref":
        env["GITHUB_WORKFLOW_REF"] += "-other"
    elif change == "workflow_sha":
        env["GITHUB_WORKFLOW_SHA"] = "not-a-sha"
    elif change == "workflow_commit":
        env["GITHUB_WORKFLOW_SHA"] = "b" * 40
    elif change == "scheduled_with_inputs":
        event["inputs"] = {"operation": "cycle"}
    else:
        env["GITHUB_EVENT_NAME"] = "workflow_dispatch"
        actor = guard.DISPATCH_ACTOR if change == "bot_sender" else guard.OWNER
        env["GITHUB_ACTOR"] = actor
        event["sender"] = {"login": actor}
        event["inputs"] = {"operation": "cycle"}
        if change == "wrong_operation":
            event["inputs"]["operation"] = "producer-credit-gated"
        elif change == "wrong_sender":
            event["sender"]["login"] = "unknown-user"
    with pytest.raises(guard.Blocked):
        guard.validate_cycle_cost_context(env, event)


@pytest.mark.parametrize("spending,allowed", [
    ("On", True), ("Off", False), ("CurrentPeriodOff", False),
])
def test_hourly_preflight_never_calls_keyvault_before_cost_gate(monkeypatch, spending, allowed):
    env, event = _cycle_context()
    ctx = guard.validate_cycle_cost_context(env, event)
    paths = []

    def read_arm(path, blocker):
        paths.append(path)
        return subscription(spending=spending) if "Microsoft.KeyVault" not in path else vault()

    monkeypatch.setattr(guard, "read_arm", read_arm)
    monkeypatch.setattr(guard, "metadata_lookup", lambda **kwargs: pytest.fail("Key Vault reached"))
    if allowed:
        result = guard.cost_preflight(ctx)
        assert result["decision"] == guard.HARD_STOP_DECISION
        assert result["literal_zero_cost_verified"] is False
        assert len(paths) == 2
    else:
        with pytest.raises(guard.Blocked, match="cost_unknown_no_azure_hard_stop"):
            guard.cost_preflight(ctx)
        assert len(paths) == 1
    assert all(path.startswith("https://management.azure.com/") for path in paths)


@pytest.mark.parametrize("size", [43, 64])
def test_runtime_token_contract_accepts_only_supported_urlsafe_sizes(size):
    token = "A" * size
    assert guard.canonical_runtime_token(token) == token
    assert guard.canonical_runtime_token(token + "\n") == token


@pytest.mark.parametrize("value", [
    "A" * 42,
    "A" * 44,
    "A" * 65,
    "A" * 42 + "+",
    "A" * 21 + "\n" + "A" * 21,
    "A" * 42 + "\x00",
    "A" * 43 + "\r\n",
    "A" * 43 + "\n\n",
])
def test_runtime_token_contract_rejects_size_charset_cr_lf_and_nul(value):
    with pytest.raises(guard.Blocked, match="keyvault_secret_value_invalid"):
        guard.canonical_runtime_token(value)


def _main_environment(monkeypatch, tmp_path, env, event, phase, *arguments):
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event), encoding="utf-8")
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    command_dir = runner_temp / "_runner_file_commands"
    command_dir.mkdir()
    github_env = command_dir / "set_env_test"
    github_env.write_text("", encoding="utf-8")
    env.update({
        "GITHUB_EVENT_PATH": str(event_path),
        "RUNNER_TEMP": str(runner_temp),
        "GITHUB_ENV": str(github_env),
    })
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(sys, "argv", [str(SOURCE), phase, *arguments])
    return github_env


def test_export_runtime_token_validates_before_mask_and_github_env(tmp_path, capsys):
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    command_dir = runner_temp / "_runner_file_commands"
    command_dir.mkdir()
    github_env = command_dir / "set_env_test"
    github_env.write_text("", encoding="utf-8")
    token = "A" * 43

    guard.export_runtime_token(token, {
        "RUNNER_TEMP": str(runner_temp),
        "GITHUB_ENV": str(github_env),
    })

    assert capsys.readouterr().out == f"::add-mask::{token}\n"
    assert github_env.read_text(encoding="utf-8") == (
        f"TODO_GLOBAL_RUNTIME_TOKEN={token}\n"
    )


def test_export_runtime_token_rejects_injection_before_any_sink(tmp_path, capsys):
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    command_dir = runner_temp / "_runner_file_commands"
    command_dir.mkdir()
    github_env = command_dir / "set_env_test"
    github_env.write_text("", encoding="utf-8")

    with pytest.raises(guard.Blocked, match="keyvault_secret_value_invalid"):
        guard.export_runtime_token("A" * 43 + "\n", {
            "RUNNER_TEMP": str(runner_temp),
            "GITHUB_ENV": str(github_env),
        })

    assert capsys.readouterr().out == ""
    assert github_env.read_text(encoding="utf-8") == ""


def test_cost_cli_blocks_current_evidence_without_keyvault_data_plane(
        monkeypatch, tmp_path, capsys):
    env, event = context()
    receipt = tmp_path / "runner-temp" / "todo-producer-cost.json"
    github_env = _main_environment(
        monkeypatch, tmp_path, env, event, "cost", "--receipt", str(receipt),
    )
    calls = []

    def fake_cli(arguments):
        calls.append(arguments)
        assert arguments[0] == "rest", "Key Vault data-plane must stay unreachable"
        url = arguments[arguments.index("--url") + 1]
        body = vault() if "Microsoft.KeyVault" in url else subscription()
        return 0, json.dumps(body), ""

    monkeypatch.setattr(guard, "verify_owner_comment", lambda *_: None)
    monkeypatch.setattr(guard, "cli", fake_cli)

    assert guard.main() == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["decision"] == guard.DATA_PLANE_BLOCKED_DECISION
    assert payload["reason"] == "literal_zero_cost_unproven"
    assert len(calls) == 2
    assert all(call[0] == "rest" for call in calls)
    assert not receipt.exists()
    assert github_env.read_text(encoding="utf-8") == ""


def test_secret_cli_rejects_observational_receipt_without_data_plane(
        monkeypatch, tmp_path, capsys):
    env, event = context()
    receipt = tmp_path / "runner-temp" / "todo-producer-secret.json"
    github_env = _main_environment(
        monkeypatch, tmp_path, env, event, "secret", "--receipt", str(receipt),
    )
    ctx = guard.validate_context(env, event)
    guard.write_receipt(receipt, {
        "schema_version": 2,
        "decision": guard.HARD_STOP_DECISION,
        "run_id": ctx["run_id"],
        "head_sha": ctx["sha"],
        "vault": guard.VAULT,
        "spending_limit": "On",
        "existing_vault_verified": True,
        "overage_hard_stop_present": True,
        "literal_zero_cost_verified": False,
        "keyvault_data_plane_allowed": False,
    })
    calls = []

    monkeypatch.setattr(guard, "verify_owner_comment", lambda *_: None)
    monkeypatch.setattr(guard, "cli", lambda arguments: calls.append(arguments))

    assert guard.main() == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["decision"] == "BLOCKED"
    assert payload["reason"] == "cost_receipt_not_trusted"
    assert calls == []
    assert github_env.read_text(encoding="utf-8") == ""


@pytest.mark.parametrize(
    "spending,expected_reason,expected_rest_calls",
    [
        ("On", "literal_zero_cost_unproven", 2),
        ("Off", "cost_unknown_no_azure_hard_stop", 1),
        ("CurrentPeriodOff", "cost_unknown_no_azure_hard_stop", 1),
    ],
)
def test_cycle_secret_cli_block_has_zero_keyvault_data_plane(
        monkeypatch, tmp_path, capsys, spending, expected_reason,
        expected_rest_calls):
    env, event = _cycle_context()
    github_env = _main_environment(monkeypatch, tmp_path, env, event,
                                   "cycle-secret")
    calls = []

    def fake_cli(arguments):
        calls.append(arguments)
        assert arguments[0] == "rest", "Key Vault data-plane must stay unreachable"
        url = arguments[arguments.index("--url") + 1]
        body = vault() if "Microsoft.KeyVault" in url else subscription(spending=spending)
        return 0, json.dumps(body), ""

    monkeypatch.setattr(guard, "cli", fake_cli)

    assert guard.main() == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["reason"] == expected_reason
    assert payload["secret_value_exposed"] is False
    assert len(calls) == expected_rest_calls
    assert all(call[0] == "rest" for call in calls)
    assert github_env.read_text(encoding="utf-8") == ""
    if spending == "On":
        assert payload["decision"] == guard.DATA_PLANE_BLOCKED_DECISION
        assert payload["hard_stop_decision"] == guard.HARD_STOP_DECISION
        assert payload["literal_zero_cost_verified"] is False


def test_export_token_cli_rejects_multiline_before_mask_or_env(
        monkeypatch, tmp_path, capsys):
    env, event = context()
    env["GITHUB_ACTOR"] = guard.OWNER
    event["sender"]["login"] = guard.OWNER
    event["inputs"] = {"operation": "reconcile-runtime"}
    github_env = _main_environment(monkeypatch, tmp_path, env, event,
                                   "export-token")
    malicious = "A" * 21 + "\nINJECTED=" + "A" * 22 + "\n"
    monkeypatch.setattr(guard, "cost_preflight", lambda _ctx: literal_zero_proof())
    monkeypatch.setattr(guard, "cli", lambda _args: (0, malicious, ""))

    assert guard.main() == 2
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["reason"] == "keyvault_secret_value_invalid"
    assert "::add-mask::" not in output
    assert "INJECTED=" not in output
    assert github_env.read_text(encoding="utf-8") == ""


def test_runtime_reconcile_cli_blocks_before_keyvault_data_plane(
        monkeypatch, tmp_path, capsys):
    env, event = context()
    env["GITHUB_ACTOR"] = guard.OWNER
    event["sender"]["login"] = guard.OWNER
    event["inputs"] = {"operation": "reconcile-runtime"}
    github_env = _main_environment(monkeypatch, tmp_path, env, event,
                                   "runtime-cost")
    calls = []

    def fake_cli(arguments):
        calls.append(arguments)
        assert arguments[0] == "rest", "Key Vault data-plane must stay unreachable"
        url = arguments[arguments.index("--url") + 1]
        body = vault() if "Microsoft.KeyVault" in url else subscription()
        return 0, json.dumps(body), ""

    monkeypatch.setattr(guard, "cli", fake_cli)

    assert guard.main() == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["decision"] == guard.DATA_PLANE_BLOCKED_DECISION
    assert payload["reason"] == "literal_zero_cost_unproven"
    assert len(calls) == 2
    assert all(call[0] == "rest" for call in calls)
    assert github_env.read_text(encoding="utf-8") == ""
