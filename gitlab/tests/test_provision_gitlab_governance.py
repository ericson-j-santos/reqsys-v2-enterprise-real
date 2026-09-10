from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "provision_gitlab_governance.py"
SPEC = importlib.util.spec_from_file_location("provision_gitlab_governance", MODULE_PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def config(*, dry_run: bool = False, user_id: int | None = 41627393):
    return module.Config(
        api_url="https://gitlab.example/api/v4",
        project_id="1",
        token="secret",
        default_branch="main",
        timeout_seconds=20,
        dry_run=dry_run,
        mirror_user_id=user_id,
        mirror_username="reqsys-github-mirror",
    )


class FakeClient:
    def __init__(self, branch_before, branch_after=None, member=None):
        self.branch_before = branch_before
        self.branch_after = branch_after if branch_after is not None else branch_before
        self.member = member or {
            "id": 41627393,
            "username": "reqsys-github-mirror",
            "state": "active",
            "access_level": 40,
        }
        self.patch_payloads = []
        self.get_branch_calls = 0

    def project_path(self, suffix=""):
        return f"projects/1{suffix}"

    def request(self, method, path, payload=None, allow_status=None):
        if path.endswith("/members/all/41627393") and method == "GET":
            return 200, self.member
        if "/protected_branches/main" in path and method == "GET":
            self.get_branch_calls += 1
            return 200, self.branch_before if self.get_branch_calls == 1 else self.branch_after
        if "/protected_branches/main" in path and method == "PATCH":
            self.patch_payloads.append(payload)
            return 200, self.branch_after
        raise AssertionError((method, path, payload, allow_status))


def branch(*entries, force=False):
    return {
        "name": "main",
        "allow_force_push": force,
        "push_access_levels": list(entries),
    }


def test_config_rejects_legacy_mirror_user_id():
    env = {
        "CI_PROJECT_ID": "1",
        "GITLAB_PROVISIONING_TOKEN": "secret",
        "CI_DEFAULT_BRANCH": "main",
        "MIRROR_USER_ID": "41625052",
    }
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(module.ProvisioningError, match="explicitly forbidden"):
            module.Config.from_environment(dry_run=True)


def test_dry_run_declares_exact_user_without_writing():
    client = FakeClient(branch({"access_level": 40}))
    result = module.ensure_mirror_push_allowance(client, config(dry_run=True))

    assert result == {
        "control": "mirror_push_allowance",
        "status": "would_update",
        "user_id": 41627393,
        "reason": "add_explicit_user_allowance",
    }
    assert client.patch_payloads == []


def test_apply_adds_exact_user_preserves_existing_and_disables_force_push():
    before = branch({"id": 10, "access_level": 40}, force=True)
    after = branch(
        {"id": 10, "access_level": 40},
        {"id": 11, "user_id": 41627393},
        force=False,
    )
    client = FakeClient(before, after)

    result = module.ensure_mirror_push_allowance(client, config())

    assert client.patch_payloads == [
        {
            "allow_force_push": False,
            "allowed_to_push": [{"user_id": 41627393}],
        }
    ]
    assert result["status"] == "updated"
    assert result["verified"] is True


def test_existing_exact_user_is_idempotent():
    current = branch(
        {"id": 10, "access_level": 40},
        {"id": 11, "user_id": 41627393},
        force=False,
    )
    client = FakeClient(current)

    result = module.ensure_mirror_push_allowance(client, config())

    assert result["status"] == "unchanged"
    assert client.patch_payloads == []


def test_blocks_generic_developer_push():
    client = FakeClient(branch({"id": 10, "access_level": 30}))
    with pytest.raises(module.ProvisioningError, match="Generic Developer"):
        module.ensure_mirror_push_allowance(client, config())


def test_blocks_legacy_user_if_still_allowed():
    client = FakeClient(branch({"id": 10, "user_id": 41625052}))
    with pytest.raises(module.ProvisioningError, match="Legacy mirror identity"):
        module.ensure_mirror_push_allowance(client, config())


def test_blocks_identity_mismatch():
    member = {
        "id": 41627393,
        "username": "unexpected-user",
        "state": "active",
        "access_level": 40,
    }
    client = FakeClient(branch({"access_level": 40}), member=member)
    with pytest.raises(module.ProvisioningError, match="identity mismatch"):
        module.ensure_mirror_push_allowance(client, config())


def test_postcondition_detects_false_green_when_target_not_persisted():
    before = branch({"id": 10, "access_level": 40})
    after = branch({"id": 10, "access_level": 40})
    client = FakeClient(before, after)

    with pytest.raises(module.ProvisioningError, match="target_user_missing"):
        module.ensure_mirror_push_allowance(client, config())


def test_postcondition_detects_existing_allowance_removed():
    before = branch({"id": 10, "group_id": 99})
    after = branch({"id": 11, "user_id": 41627393})
    client = FakeClient(before, after)

    with pytest.raises(module.ProvisioningError, match="existing_allowance_removed"):
        module.ensure_mirror_push_allowance(client, config())


def test_postcondition_detects_force_push_remaining_enabled():
    before = branch({"id": 10, "access_level": 40}, force=True)
    after = branch(
        {"id": 10, "access_level": 40},
        {"id": 11, "user_id": 41627393},
        force=True,
    )
    client = FakeClient(before, after)

    with pytest.raises(module.ProvisioningError, match="force_push_enabled"):
        module.ensure_mirror_push_allowance(client, config())
