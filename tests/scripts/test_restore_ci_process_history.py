import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.restore_ci_process_history import HISTORY_MEMBER, restore


def history_zip(content: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(HISTORY_MEMBER, content)
    return buffer.getvalue()


class RestoreHistoryTests(unittest.TestCase):
    def test_restores_latest_successful_main_artifact(self):
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

    def test_no_prior_artifact_is_non_blocking(self):
        with tempfile.TemporaryDirectory() as temp, patch("scripts.restore_ci_process_history._request_json", return_value={"workflow_runs": []}):
            output = Path(temp) / "history.jsonl"
            self.assertEqual(restore("o/r", "t", output, "20"), 0)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
