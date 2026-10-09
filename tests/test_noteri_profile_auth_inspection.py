"""Controles da inspeção de autenticação; nenhum login é executado."""
import json
import unittest
from scripts import noteri_profile_auth_inspection as m


class AuthInspectionTests(unittest.TestCase):
    def report(self, payload):
        return m.summarize(m.PATHS[0], 200, "application/json", json.dumps(payload).encode())

    def test_nested_and_top_level_config(self):
        for payload in ({"demo_login_enabled": False}, {"data": {"demo_login_enabled": False}}):
            self.assertIs(self.report(payload)["demo_login_enabled"], False)

    def test_absence_not_reported_as_disabled(self):
        self.assertIsNone(self.report({"status": "ok"})["demo_login_enabled"])

    def test_secret_and_personal_fields_not_emitted(self):
        payload = {"data": {"access_token": "secret-value", "password": "private-value",
                            "email": "private@example.test", "azure_client_id": "opaque",
                            "azure_tenant_id": "opaque-tenant", "demo_login_enabled": False}}
        rendered = json.dumps(self.report(payload))
        for forbidden in ("secret-value", "private-value", "private@example.test", "opaque"):
            self.assertNotIn(forbidden, rendered)
        self.assertTrue(self.report(payload)["public_client_configured"])

    def test_truthy_string_does_not_enable_auth(self):
        self.assertIsNone(self.report({"demo_login_enabled": "true"})["demo_login_enabled"])

    def test_html_fallback_does_not_imply_auth(self):
        result = m.summarize(m.PATHS[0], 200, "text/html", b"<!doctype html><html></html>")
        self.assertFalse(result["json_object"])
        self.assertTrue(result["html_document"])
        self.assertNotIn("demo_login_enabled", result)

    def test_fixed_route(self):
        with self.assertRaisesRegex(m.Blocked, "path_not_allowlisted"):
            m.get("/arbitrary")

    def test_redirect_not_followed(self):
        self.assertIsNone(m.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.test"))

    def test_wrong_host_blocks_before_network(self):
        with self.assertRaisesRegex(m.Blocked, "host_not_authorized"):
            m.inspect("a"*40, "auth-inspection", host="Other", platform="nt",
                      fetch=lambda p: self.fail("network must not run"))

    def test_wrong_sha_blocks_before_network(self):
        with self.assertRaisesRegex(m.Blocked, "source_sha_mismatch"):
            m.inspect("a"*40, "auth-inspection", host="Noteri", platform="nt",
                      sha_reader=lambda: "b"*40, fetch=lambda p: self.fail("network must not run"))

    def test_repeat_fixed_get_plan_is_idempotent(self):
        seen = []
        def fetch(path):
            seen.append(path)
            return {"path": path}
        args = dict(host="Noteri", platform="nt", sha_reader=lambda: "a"*40, fetch=fetch)
        first = m.inspect("a"*40, "auth-inspection", **args)
        self.assertEqual(first, m.inspect("a"*40, "auth-inspection", **args))
        self.assertEqual(seen, list(m.PATHS)*2)
        self.assertFalse(first["credentials_used"])
        self.assertFalse(first["profile_post_sent"])

    def test_oversized_data_blocked(self):
        with self.assertRaisesRegex(m.Blocked, "path_or_size_invalid"):
            m.summarize(m.PATHS[0], 200, "application/json", b"x"*(m.LIMIT+1))


if __name__ == "__main__":
    unittest.main()
