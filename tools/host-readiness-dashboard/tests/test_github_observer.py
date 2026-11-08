"""Verifica observação GitHub sintética sem rede, credenciais ou host real."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api.github_observer import QUALIFICATION_STEP, ObservationUnavailable, github_json, observations

NOW = datetime(2026, 11, 8, 14, 0, tzinfo=timezone.utc)
REPO = "ericson-j-santos/desktop-pc24x7-runtime"
RUN = {"id": 123, "repository": {"full_name": REPO}, "head_sha": "a" * 40,
       "status": "completed", "conclusion": "success"}
JOB = {"id": 456, "run_id": 123, "runner_id": 9, "runner_name": "DESKTOP-PDQK954-runtime",
       "status": "completed", "conclusion": "success", "labels": ["self-hosted"],
       "completed_at": NOW.isoformat(), "html_url": f"https://github.com/{REPO}/actions/runs/123/job/456",
       "steps": [{"name": QUALIFICATION_STEP, "status": "completed", "conclusion": "success"}]}


def fake_reader(path, job=JOB, run=RUN):
    if path.endswith("/actions/runs?per_page=8"):
        return {"workflow_runs": [run] if path.startswith(f"repos/{REPO}/") else []}
    if path == f"repos/{REPO}/actions/runs/123/jobs?per_page=100":
        return {"jobs": [job]}
    raise AssertionError("unexpected URL: " + path)


class ObservationTests(unittest.TestCase):
    def test_job_only_never_qualifies_host(self):
        result = observations(reader=fake_reader, now=NOW + timedelta(seconds=10))
        desk = result["hosts"][0]
        self.assertTrue(desk["pickup_observed"])
        self.assertTrue(desk["fresh"])
        self.assertEqual(desk["job_id"], 456)
        self.assertFalse(result["ready_for_work"])
        self.assertFalse(result["continuity_certified"])
        self.assertTrue(all(h["ready_for_work"] is False for h in result["hosts"]))

    def test_missing_qualification_and_wrong_runner_fail_closed(self):
        for invalid in ({**JOB, "steps": []}, {**JOB, "runner_name": "different"},
                        {**JOB, "runner_id": 0}, {**JOB, "html_url": "https://evil.example"}):
            with self.subTest(invalid=invalid):
                r = observations(reader=lambda path: fake_reader(path, job=invalid), now=NOW)
                self.assertFalse(r["hosts"][0]["pickup_observed"])
                self.assertFalse(r["hosts"][0]["ready_for_work"])

    def test_stale_does_not_renew_proof(self):
        r = observations(reader=fake_reader, now=NOW + timedelta(minutes=8))
        self.assertTrue(r["hosts"][0]["pickup_observed"])
        self.assertFalse(r["hosts"][0]["fresh"])
        self.assertFalse(r["hosts"][0]["ready_for_work"])

    def test_unavailable_fail_closed(self):
        def broken(_):
            raise ObservationUnavailable("offline")
        r = observations(reader=broken, now=NOW)
        self.assertTrue(all(h["block"] == "github_observation_unavailable" for h in r["hosts"]))
        self.assertFalse(r["ready_for_work"])

    def test_no_arbitrary_github_path_or_secret(self):
        with self.assertRaisesRegex(ObservationUnavailable, "github_path_not_allowed"):
            github_json("https://evil.invalid/host")
        with self.assertRaisesRegex(ObservationUnavailable, "github_path_not_allowed"):
            github_json("repos/other/secret/actions/runs?per_page=8")

    def test_replay_is_deterministic(self):
        self.assertEqual(observations(reader=fake_reader, now=NOW), observations(reader=fake_reader, now=NOW))


if __name__ == "__main__":
    unittest.main()

# Exercita endpoint HTTP real com observador injetado; nunca chama a rede.
class ObservationHttpTests(unittest.TestCase):
    def test_observation_endpoint_requires_auth_and_never_enables_host(self):
        import base64
        import json
        import tempfile
        import threading
        from http.server import ThreadingHTTPServer
        from unittest.mock import patch
        from urllib.error import HTTPError
        from urllib.request import Request, urlopen
        from api.readiness import handler_factory
        with tempfile.TemporaryDirectory() as tmp:
            html = Path(tmp) / 'index.html'
            html.write_text('<h1>dev</h1>')
            token = 'token-' + 'x' * 24
            server = ThreadingHTTPServer(('127.0.0.1', 0), handler_factory(Path(tmp) / 'store.db', token, html, 'k' * 40, 'a' * 40))
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            url = f'http://127.0.0.1:{server.server_port}/api/v1/github-observations'
            try:
                with self.assertRaises(HTTPError) as blocked:
                    urlopen(url, timeout=3)
                self.assertEqual(blocked.exception.code, 401)
                auth = base64.b64encode(('viewer:' + token).encode()).decode()
                with patch('api.github_observer.observations', return_value={'schema_version': '1', 'ready_for_work': False, 'continuity_certified': False, 'hosts': []}) as mock:
                    with urlopen(Request(url, headers={'Authorization': 'Basic ' + auth}), timeout=3) as response:
                        result = json.load(response)
                    self.assertFalse(result['ready_for_work'])
                    self.assertFalse(result['continuity_certified'])
                    mock.assert_called_once_with()
                with self.assertRaises(HTTPError) as blocked:
                    urlopen(Request(url, method='POST', headers={'Authorization': 'Basic ' + auth}), timeout=3)
                self.assertEqual(blocked.exception.code, 405)
                self.assertFalse((Path(tmp) / 'store.db').exists())
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=3)
