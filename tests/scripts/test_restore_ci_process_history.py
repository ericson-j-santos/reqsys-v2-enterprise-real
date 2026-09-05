import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.restore_ci_process_history import (
    ARCHIVE_HISTORY_MEMBERS,
    OUTPUT_HISTORY_PATH,
    _CrossOriginSafeRedirectHandler,
    restore,
)


def history_zip(content: str, member: str = ARCHIVE_HISTORY_MEMBERS[0]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(member, content)
    return buffer.getvalue()


class RestoreHistoryTests(unittest.TestCase):
    def test_cross_origin_redirect_strips_github_credentials(self):
        handler = _CrossOriginSafeRedirectHandler()
        request = Request(
            "https://api.github.com/repos/o/r/actions/artifacts/99/zip",
            headers={
                "Authorization": "Bearer secret",
                "X-GitHub-Api-Version": "2022-11-28",
                "Accept": "application/vnd.github+json",
            },
        )
        redirected = handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "https://example.blob.core.windows.net/artifact?sig=abc",
        )
        self.assertIsNotNone(redirected)
        headers = dict(redirected.header_items())
        self.assertNotIn("Authorization", headers)
        self.assertNotIn("X-github-api-version", headers)
        self.assertEqual(headers.get("Accept"), "application/vnd.github+json")

    def test_same_origin_redirect_keeps_github_credentials(self):
        handler = _CrossOriginSafeRedirectHandler()
        request = Request("https://api.github.com/a", headers={"Authorization": "Bearer secret"})
        redirected = handler.redirect_request(request, None, 302, "Found", {}, "https://api.github.com/b")
        self.assertEqual(dict(redirected.header_items()).get("Authorization"), "Bearer secret")

    def test_restores_latest_successful_main_artifact_using_real_upload_layout(self):
        calls = []

        def fake_json(url, token):
            calls.append(url)
            if "/actions/workflows/" in url:
                return {"workflow_runs": [{"id": 20}, {"id": 19}]}
            if "/actions/runs/20/artifacts" in url:
                return {"artifacts": [{"id": 99, "name": "ci-lead-time-analytics-20", "expired": False}]}
            return {"artifacts": []}

        with tempfile.TemporaryDirectory() as temp, patch("scripts.restore_ci_process_history._request_json", side_effect=fake_json), patch("scripts.restore_ci_process_history._request_bytes", return_value=history_zip('{"run_id":"20"}\n')):
            output = Path(temp) / "history.jsonl"
            self.assertEqual(restore("o/r", "t", output, "21"), 0)
            self.assertEqual(output.read_text(), '{"run_id":"20"}\n')
            self.assertTrue(any("branch=main" in call for call in calls))

    def test_accepts_legacy_prefixed_archive_member(self):
        def fake_json(url, token):
            if "/actions/workflows/" in url:
                return {"workflow_runs": [{"id": 20}]}
            if "/actions/runs/20/artifacts" in url:
                return {"artifacts": [{"id": 99, "name": "ci-lead-time-analytics-20", "expired": False}]}
            return {"artifacts": []}

        with tempfile.TemporaryDirectory() as temp, patch("scripts.restore_ci_process_history._request_json", side_effect=fake_json), patch("scripts.restore_ci_process_history._request_bytes", return_value=history_zip('{"run_id":"20"}\n', OUTPUT_HISTORY_PATH)):
            output = Path(temp) / "history.jsonl"
            restore("o/r", "t", output, "21")
            self.assertEqual(output.read_text(), '{"run_id":"20"}\n')

    def test_skips_current_run(self):
        def fake_json(url, token):
            if "/actions/workflows/" in url:
                return {"workflow_runs": [{"id": 20}, {"id": 19}]}
            if "/actions/runs/19/artifacts" in url:
                return {"artifacts": [{"id": 98, "name": "ci-lead-time-analytics-19", "expired": False}]}
            return {"artifacts": []}

        with tempfile.TemporaryDirectory() as temp, patch("scripts.restore_ci_process_history._request_json", side_effect=fake_json), patch("scripts.restore_ci_process_history._request_bytes", return_value=history_zip('{"run_id":"19"}\n')):
            output = Path(temp) / "history.jsonl"
            restore("o/r", "t", output, "20")
            self.assertIn('"19"', output.read_text())

    def test_skips_artifact_without_history_member(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("ci-lead-time-analytics.json", "{}")

        def fake_json(url, token):
            if "/actions/workflows/" in url:
                return {"workflow_runs": [{"id": 20}]}
            if "/actions/runs/20/artifacts" in url:
                return {"artifacts": [{"id": 99, "name": "ci-lead-time-analytics-20", "expired": False}]}
            return {"artifacts": []}

        with tempfile.TemporaryDirectory() as temp, patch("scripts.restore_ci_process_history._request_json", side_effect=fake_json), patch("scripts.restore_ci_process_history._request_bytes", return_value=buffer.getvalue()):
            output = Path(temp) / "history.jsonl"
            self.assertEqual(restore("o/r", "t", output, "21"), 0)
            self.assertFalse(output.exists())

    def test_no_prior_artifact_is_non_blocking(self):
        with tempfile.TemporaryDirectory() as temp, patch("scripts.restore_ci_process_history._request_json", return_value={"workflow_runs": []}):
            output = Path(temp) / "history.jsonl"
            self.assertEqual(restore("o/r", "t", output, "20"), 0)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
