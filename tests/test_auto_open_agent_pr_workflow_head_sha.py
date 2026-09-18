from scripts.auto_open_agent_pr import main


def test_main_uses_explicit_workflow_run_head_sha(monkeypatch, tmp_path):
    class FakeClient:
        created_payload = None

        def find_existing_pr(self, head: str, base: str):
            return None

        def create_pr(self, **kwargs):
            self.created_payload = kwargs
            return {"number": 777, "html_url": "https://example/pr/777"}

        def add_labels(self, number: int, labels: list[str]):
            return None

    fake = FakeClient()
    captured = {}

    def fake_wait(client, *, head_sha, base, wait_seconds, poll_seconds):
        captured["head_sha"] = head_sha
        return {
            "status": "passed",
            "head_sha": head_sha,
            "base_sha": "main-sha",
            "run_id": 337,
            "run_url": "https://example/run/337",
        }

    monkeypatch.setenv("GITHUB_REPOSITORY", "ericson-j-santos/reqsys-v2-enterprise-real")
    monkeypatch.setenv("GITHUB_SHA", "wrong-main-sha")
    monkeypatch.setenv("GH_TOKEN", "token-teste")
    monkeypatch.setenv("PR_REQUEST_ARTIFACT_DIR", str(tmp_path))
    monkeypatch.setattr("scripts.auto_open_agent_pr.GitHubClient", lambda token, repo: fake)
    monkeypatch.setattr("scripts.auto_open_agent_pr.wait_for_ready_for_pr", fake_wait)
    monkeypatch.setattr(
        "sys.argv",
        [
            "auto_open_agent_pr.py",
            "--base",
            "main",
            "--branch",
            "copilot/test",
            "--head-sha",
            "approved-head-sha",
        ],
    )

    assert main() == 0
    assert captured["head_sha"] == "approved-head-sha"
    assert "approved-head-sha" in fake.created_payload["body"]
    assert "wrong-main-sha" not in fake.created_payload["body"]
