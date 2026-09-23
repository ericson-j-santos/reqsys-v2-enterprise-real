import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import scripts.fabric_hml_secret_bootstrap_temp as m


class FabricHmlSecretBootstrapTests(unittest.TestCase):
    def _base_patches(self, events):
        def fake_set_variable(_gh, name, value):
            events.append(("variable", name, value))

        def fake_gh_names(_gh, kind):
            if kind == "secret":
                return {m.TARGET_SECRET}
            return {
                "FABRIC_TENANT_ID",
                "FABRIC_CLIENT_ID",
                "FABRIC_WORKSPACE_ID",
                "FABRIC_HML_E2E_ENABLED",
            }

        return [
            mock.patch.object(m.platform, "node", return_value=m.EXPECTED_HOST),
            mock.patch.object(m, "find_az", return_value="az"),
            mock.patch.object(m.shutil, "which", return_value="gh"),
            mock.patch.object(m, "run", return_value="{}"),
            mock.patch.object(m, "exact_app", return_value=("app-id", "object-id")),
            mock.patch.object(m, "user_fabric_token", return_value="user-token"),
            mock.patch.object(m, "exact_workspace_id", return_value="workspace-id"),
            mock.patch.object(m, "set_variable", side_effect=fake_set_variable),
            mock.patch.object(m, "gh_names", side_effect=fake_gh_names),
        ]

    def test_existing_secret_is_rotated_only_after_new_credential_is_validated(self):
        events = []
        patches = self._base_patches(events)

        def fake_create(*_args, **_kwargs):
            events.append(("create",))
            return "new-secret-value", "new-key-id"

        def fake_validate(**_kwargs):
            events.append(("validate",))
            return True, 200, True, 200, 2

        def fake_stdin(args, value, **_kwargs):
            events.append(("write-secret",))
            self.assertEqual(value, "new-secret-value")
            self.assertNotIn(value, args)

        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp) / "evidence.json"
            with mock.patch.dict(os.environ, {"EVIDENCE_FILE": str(evidence), "GITHUB_RUN_ID": "123"}), \
                mock.patch.object(m, "create_credential", side_effect=fake_create), \
                mock.patch.object(m, "validate_client_credentials_with_retry", side_effect=fake_validate), \
                mock.patch.object(m, "run_stdin", side_effect=fake_stdin), \
                mock.patch.object(m, "delete_credential") as delete_mock:
                for patcher in patches:
                    patcher.start()
                try:
                    self.assertEqual(m.main(), 0)
                finally:
                    for patcher in reversed(patches):
                        patcher.stop()

            data = json.loads(evidence.read_text(encoding="utf-8"))
            self.assertEqual(
                [event[0] for event in events if event[0] in {"create", "validate", "write-secret"}],
                ["create", "validate", "write-secret"],
            )
            self.assertIn(("variable", "FABRIC_HML_E2E_ENABLED", "false"), events)
            self.assertIn(("variable", "FABRIC_HML_E2E_ENABLED", "true"), events)
            self.assertTrue(data["secret_replaced"])
            self.assertTrue(data["e2e_enabled"])
            self.assertEqual(data["validation_attempts"], 2)
            delete_mock.assert_not_called()

    def test_failed_new_credential_validation_rolls_back_without_overwriting_secret(self):
        events = []
        patches = self._base_patches(events)
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp) / "evidence.json"
            with mock.patch.dict(os.environ, {"EVIDENCE_FILE": str(evidence), "GITHUB_RUN_ID": "124"}), \
                mock.patch.object(m, "create_credential", return_value=("bad-secret", "new-key-id")), \
                mock.patch.object(
                    m,
                    "validate_client_credentials_with_retry",
                    return_value=(False, None, False, 401, 6),
                ), \
                mock.patch.object(m, "run_stdin") as stdin_mock, \
                mock.patch.object(m, "delete_credential") as delete_mock:
                for patcher in patches:
                    patcher.start()
                try:
                    self.assertEqual(m.main(), 2)
                finally:
                    for patcher in reversed(patches):
                        patcher.stop()

            data = json.loads(evidence.read_text(encoding="utf-8"))
            stdin_mock.assert_not_called()
            delete_mock.assert_called_once_with("az", "app-id", "new-key-id")
            self.assertTrue(data["credential_rollback"])
            self.assertFalse(data["e2e_enabled"])
            self.assertEqual(data["status"], "new_credential_validation_failed")
            self.assertIn(("variable", "FABRIC_HML_E2E_ENABLED", "false"), events)

    @mock.patch.object(m.time, "sleep")
    def test_retry_stops_after_first_full_success(self, sleep_mock):
        with mock.patch.object(
            m,
            "validate_client_credentials",
            side_effect=[
                (False, None, False, 401),
                (True, 403, False, 200),
                (True, 200, True, 200),
            ],
        ):
            result = m.validate_client_credentials_with_retry(
                client_id="app",
                secret="secret",
                workspace_id="workspace",
                attempts=5,
                delay_seconds=1,
            )

        self.assertEqual(result, (True, 200, True, 200, 3))
        self.assertEqual(sleep_mock.call_count, 2)


if __name__ == "__main__":
    unittest.main()
