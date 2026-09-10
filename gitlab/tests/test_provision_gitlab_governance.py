from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

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


class MirrorAllowanceTests(unittest.TestCase):
    def test_config_rejects_legacy_mirror_user_id(self):
        env = {
            "CI_PROJECT_ID": "1",
            "GITLAB_PROVISIONING_TOKEN": "secret",
            "CI_DEFAULT_BRANCH": "main",
            "MIRROR_USER_ID": "41625052",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(module.ProvisioningError, "explicitly forbidden"):
                module.Config.from_environment(dry_run=True)

    def test_dry_run_declares_exact_user_without_writing(self):
        client = FakeClient(branch({"access_level": 40}))
        result = module.ensure_mirror_push_allowance(client, config(dry_run=True))
        self.assertEqual(
            result,
            {
                "control": "mirror_push_allowance",
                "status": "would_update",
                "user_id": 41627393,
                "reason": "add_explicit_user_allowance",
            },
        )
        self.assertEqual(client.patch_payloads, [])

    def test_apply_adds_exact_user_preserves_existing_and_disables_force_push(self):
        before = branch({"id": 10, "access_level": 40}, force=True)
        after = branch(
            {"id": 10, "access_level": 40},
            {"id": 11, "user_id": 41627393},
            force=False,
        )
        client = FakeClient(before, after)
        result = module.ensure_mirror_push_allowance(client, config())
        self.assertEqual(
            client.patch_payloads,
            [{"allow_force_push": False, "allowed_to_push": [{"user_id": 41627393}]}],
        )
        self.assertEqual(result["status"], "updated")
        self.assertTrue(result["verified"])

    def test_existing_exact_user_is_idempotent(self):
        current = branch(
            {"id": 10, "access_level": 40},
            {"id": 11, "user_id": 41627393},
            force=False,
        )
        client = FakeClient(current)
        result = module.ensure_mirror_push_allowance(client, config())
        self.assertEqual(result["status"], "unchanged")
        self.assertEqual(client.patch_payloads, [])

    def test_blocks_generic_developer_push(self):
        client = FakeClient(branch({"id": 10, "access_level": 30}))
        with self.assertRaisesRegex(module.ProvisioningError, "Generic Developer"):
            module.ensure_mirror_push_allowance(client, config())

    def test_blocks_legacy_user_if_still_allowed(self):
        client = FakeClient(branch({"id": 10, "user_id": 41625052}))
        with self.assertRaisesRegex(module.ProvisioningError, "Legacy mirror identity"):
            module.ensure_mirror_push_allowance(client, config())

    def test_blocks_identity_mismatch(self):
        member = {
            "id": 41627393,
            "username": "unexpected-user",
            "state": "active",
            "access_level": 40,
        }
        client = FakeClient(branch({"access_level": 40}), member=member)
        with self.assertRaisesRegex(module.ProvisioningError, "identity mismatch"):
            module.ensure_mirror_push_allowance(client, config())

    def test_postcondition_detects_false_green_when_target_not_persisted(self):
        before = branch({"id": 10, "access_level": 40})
        after = branch({"id": 10, "access_level": 40})
        client = FakeClient(before, after)
        with self.assertRaisesRegex(module.ProvisioningError, "target_user_missing"):
            module.ensure_mirror_push_allowance(client, config())

    def test_postcondition_detects_existing_allowance_removed(self):
        before = branch({"id": 10, "group_id": 99})
        after = branch({"id": 11, "user_id": 41627393})
        client = FakeClient(before, after)
        with self.assertRaisesRegex(module.ProvisioningError, "existing_allowance_removed"):
            module.ensure_mirror_push_allowance(client, config())

    def test_postcondition_detects_force_push_remaining_enabled(self):
        before = branch({"id": 10, "access_level": 40}, force=True)
        after = branch(
            {"id": 10, "access_level": 40},
            {"id": 11, "user_id": 41627393},
            force=True,
        )
        client = FakeClient(before, after)
        with self.assertRaisesRegex(module.ProvisioningError, "force_push_enabled"):
            module.ensure_mirror_push_allowance(client, config())


if __name__ == "__main__":
    unittest.main()
