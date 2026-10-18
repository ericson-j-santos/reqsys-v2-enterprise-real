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
        mirror_name="reqsys-github-mirror",
    )


def branch(*, push=(), merge=(), force=False):
    return {
        "name": "main",
        "allow_force_push": force,
        "push_access_levels": list(push),
        "merge_access_levels": list(merge),
    }


class FakeClient:
    def __init__(
        self,
        branch_before,
        branch_after=None,
        member=None,
        project_before=None,
        project_after=None,
    ):
        self.branch_before = branch_before
        self.branch_after = branch_after if branch_after is not None else branch_before
        self.member = member or {
            "id": 41627393,
            "username": "project_84366761_bot_generated",
            "name": "reqsys-github-mirror",
            "state": "active",
            "access_level": 40,
        }
        self.project_before = project_before or {
            "only_allow_merge_if_pipeline_succeeds": True,
            "allow_merge_on_skipped_pipeline": False,
        }
        self.project_after = project_after if project_after is not None else self.project_before
        self.patch_payloads = []
        self.put_payloads = []
        self.get_branch_calls = 0
        self.get_project_calls = 0

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
        if path == "projects/1" and method == "GET":
            self.get_project_calls += 1
            return 200, self.project_before if self.get_project_calls == 1 else self.project_after
        if path == "projects/1" and method == "PUT":
            self.put_payloads.append(payload)
            return 200, self.project_after
        raise AssertionError((method, path, payload, allow_status))


class ProtectedBranchHardeningTests(unittest.TestCase):
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

    def test_dry_run_reports_force_and_developer_removals_without_write(self):
        current = branch(
            push=({"id": 10, "access_level": 40}, {"id": 11, "access_level": 30}),
            merge=({"id": 20, "access_level": 40}, {"id": 21, "access_level": 30}),
            force=True,
        )
        client = FakeClient(current)
        result = module.ensure_protected_branch(client, config(dry_run=True))
        self.assertEqual(result["status"], "would_update")
        self.assertIn("disable_force_push", result["reason"])
        self.assertIn("remove_generic_developer_push", result["reason"])
        self.assertIn("remove_generic_developer_merge", result["reason"])
        self.assertEqual(client.patch_payloads, [])

    def test_apply_removes_only_developer_records_and_disables_force(self):
        before = branch(
            push=({"id": 10, "access_level": 40}, {"id": 11, "access_level": 30}),
            merge=({"id": 20, "access_level": 40}, {"id": 21, "access_level": 30}),
            force=True,
        )
        after = branch(
            push=({"id": 10, "access_level": 40},),
            merge=({"id": 20, "access_level": 40},),
            force=False,
        )
        client = FakeClient(before, after)
        result = module.ensure_protected_branch(client, config())
        self.assertEqual(
            client.patch_payloads,
            [{
                "allow_force_push": False,
                "allowed_to_push": [{"id": 11, "access_level": 30, "_destroy": True}],
                "allowed_to_merge": [{"id": 21, "access_level": 30, "_destroy": True}],
            }],
        )
        self.assertEqual(result["status"], "updated")
        self.assertTrue(result["verified"])

    def test_refuses_to_remove_developer_without_maintainer_fallback(self):
        current = branch(
            push=({"id": 11, "access_level": 30},),
            merge=({"id": 20, "access_level": 40},),
        )
        client = FakeClient(current)
        with self.assertRaisesRegex(module.ProvisioningError, "Maintainer fallback"):
            module.ensure_protected_branch(client, config())

    def test_postcondition_detects_developer_record_remaining(self):
        before = branch(
            push=({"id": 10, "access_level": 40}, {"id": 11, "access_level": 30}),
            merge=({"id": 20, "access_level": 40},),
        )
        client = FakeClient(before, before)
        with self.assertRaisesRegex(module.ProvisioningError, "generic_developer_push_present"):
            module.ensure_protected_branch(client, config())


class MirrorAllowanceTests(unittest.TestCase):
    def test_accepts_maintainer_role_fallback_without_self_elevation(self):
        current = branch(
            push=({"id": 10, "access_level": 40},),
            merge=({"id": 20, "access_level": 40},),
        )
        client = FakeClient(current)
        result = module.ensure_mirror_push_allowance(client, config())
        self.assertEqual(result["status"], "unchanged")
        self.assertEqual(result["grant_mode"], "maintainer_role_fallback")
        self.assertFalse(result["least_privilege_exact_identity"])
        self.assertEqual(client.patch_payloads, [])

    def test_accepts_existing_exact_user(self):
        current = branch(
            push=({"id": 10, "user_id": 41627393},),
            merge=({"id": 20, "access_level": 40},),
        )
        client = FakeClient(current)
        result = module.ensure_mirror_push_allowance(client, config())
        self.assertEqual(result["grant_mode"], "exact_user")
        self.assertTrue(result["least_privilege_exact_identity"])

    def test_dry_run_defers_until_generic_developer_hardening(self):
        current = branch(
            push=({"id": 10, "access_level": 40}, {"id": 11, "access_level": 30}),
            merge=({"id": 20, "access_level": 40},),
        )
        client = FakeClient(current)
        result = module.ensure_mirror_push_allowance(client, config(dry_run=True))
        self.assertEqual(result["status"], "would_validate_after_branch_hardening")
        self.assertEqual(client.patch_payloads, [])

    def test_apply_blocks_if_generic_developer_survives_hardening(self):
        current = branch(
            push=({"id": 10, "access_level": 40}, {"id": 11, "access_level": 30}),
            merge=({"id": 20, "access_level": 40},),
        )
        client = FakeClient(current)
        with self.assertRaisesRegex(module.ProvisioningError, "remains after"):
            module.ensure_mirror_push_allowance(client, config())

    def test_missing_allowance_is_manual_not_self_elevation(self):
        current = branch(
            push=({"id": 99, "group_id": 55},),
            merge=({"id": 20, "access_level": 40},),
        )
        client = FakeClient(current)
        result = module.ensure_mirror_push_allowance(client, config())
        self.assertEqual(result["status"], "manual_required")
        self.assertIn("self-elevation is disabled", result["reason"])
        self.assertEqual(client.patch_payloads, [])

    def test_blocks_legacy_user_if_still_allowed(self):
        current = branch(
            push=({"id": 10, "user_id": 41625052},),
            merge=({"id": 20, "access_level": 40},),
        )
        client = FakeClient(current)
        with self.assertRaisesRegex(module.ProvisioningError, "Legacy mirror identity"):
            module.ensure_mirror_push_allowance(client, config())

    def test_blocks_force_push_false_green(self):
        current = branch(
            push=({"id": 10, "access_level": 40},),
            merge=({"id": 20, "access_level": 40},),
            force=True,
        )
        client = FakeClient(current)
        with self.assertRaisesRegex(module.ProvisioningError, "force_push_enabled"):
            module.ensure_mirror_push_allowance(client, config())

    def test_blocks_identity_name_mismatch(self):
        member = {
            "id": 41627393,
            "username": "project_84366761_bot_generated",
            "name": "unexpected-name",
            "state": "active",
            "access_level": 40,
        }
        current = branch(
            push=({"id": 10, "access_level": 40},),
            merge=({"id": 20, "access_level": 40},),
        )
        client = FakeClient(current, member=member)
        with self.assertRaisesRegex(module.ProvisioningError, "identity mismatch"):
            module.ensure_mirror_push_allowance(client, config())


class ProjectMergePolicyTests(unittest.TestCase):
    def test_dry_run_rejects_skipped_pipeline_without_write(self):
        client = FakeClient(
            branch(push=({"id": 10, "access_level": 40},)),
            project_before={
                "only_allow_merge_if_pipeline_succeeds": True,
                "allow_merge_on_skipped_pipeline": True,
            },
        )
        result = module.ensure_project_merge_policy(client, config(dry_run=True))
        self.assertEqual(result["status"], "would_update")
        self.assertEqual(client.put_payloads, [])

    def test_apply_requires_success_and_rejects_skipped_pipeline(self):
        client = FakeClient(
            branch(push=({"id": 10, "access_level": 40},)),
            project_before={
                "only_allow_merge_if_pipeline_succeeds": True,
                "allow_merge_on_skipped_pipeline": True,
            },
            project_after={
                "only_allow_merge_if_pipeline_succeeds": True,
                "allow_merge_on_skipped_pipeline": False,
            },
        )
        result = module.ensure_project_merge_policy(client, config())
        self.assertEqual(
            client.put_payloads,
            [{
                "only_allow_merge_if_pipeline_succeeds": True,
                "allow_merge_on_skipped_pipeline": False,
            }],
        )
        self.assertEqual(result["status"], "updated")
        self.assertTrue(result["verified"])

    def test_postcondition_detects_skipped_pipeline_false_green(self):
        current = {
            "only_allow_merge_if_pipeline_succeeds": True,
            "allow_merge_on_skipped_pipeline": True,
        }
        client = FakeClient(
            branch(push=({"id": 10, "access_level": 40},)),
            project_before=current,
            project_after=current,
        )
        with self.assertRaisesRegex(module.ProvisioningError, "skipped_pipeline_still_allowed"):
            module.ensure_project_merge_policy(client, config())


if __name__ == "__main__":
    unittest.main()
