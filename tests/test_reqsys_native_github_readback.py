"""API GitHub simulada: valida escopo sem acesso a rede ou segredo real."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import reqsys_native_github_readback as api  # noqa: E402

SHA = "a" * 40
LABELS = ["self-hosted", "Windows", "X64", "reqsys-dev", "reqsys-dev-base-v1",
          "reqsys-dev-native-runtime-v1"]


def make_responses():
    return {
        "/actions/runs/123": {"id": 123, "head_sha": SHA,
                              "repository": {"full_name": api.REPO}},
        "/actions/jobs/456": {"id": 456, "run_id": 123, "runner_id": 789,
                              "runner_name": "runner-example", "head_sha": SHA,
                              "labels": LABELS},
        "/actions/runners/789": {"id": 789, "status": "online", "busy": False,
                                 "name": "runner-example",
                                 "labels": [{"name": v} for v in LABELS]},
    }


def evaluate(data=None):
    responses = data or make_responses()
    calls = []
    def fetch(path, *, token):
        calls.append((path, token))
        return responses[path]
    result = api.readback(run_id=123, job_id=456, runner_id=789,
                          expected_sha=SHA, expected_labels=LABELS,
                          token="fake-token-only-for-unit-tests", fetch=fetch)
    return result, calls


def test_official_readback_three_readonly_gets_not_ready():
    r, calls = evaluate()
    assert [x[0] for x in calls] == ["/actions/runs/123", "/actions/jobs/456",
                                       "/actions/runners/789"]
    assert all(x[1] == "fake-token-only-for-unit-tests" for x in calls)
    assert r["identity_binding_verified"] is False
    assert r["ready_for_work"] is False
    assert r["dispatch_allowed"] is False
    assert r["source_sha"] == SHA
    assert "token" not in json.dumps(r)


@pytest.mark.parametrize("path,field,value,reason", [
    ("/actions/runs/123", "head_sha", "b"*40, "github_run_mismatch"),
    ("/actions/jobs/456", "head_sha", "b"*40, "github_job_mismatch"),
    ("/actions/jobs/456", "run_id", 222, "github_job_mismatch"),
    ("/actions/jobs/456", "runner_id", 999, "github_job_mismatch"),
    ("/actions/runners/789", "status", "offline", "github_runner_not_idle"),
    ("/actions/runners/789", "busy", True, "github_runner_not_idle"),
    ("/actions/runners/789", "labels", ["reqsys-dev-runtime-v1"], "github_runner_labels_mismatch"),
    ("/actions/jobs/456", "runner_name", "forged", "github_runner_name_mismatch"),
])
def test_reject_conflicting_api_snapshots(path,field,value,reason):
    r = make_responses()
    r[path][field] = value
    with pytest.raises(api.GitHubReadbackBlocked, match=reason):
        evaluate(r)


def test_reject_sanitized_input_invalid_id_sha():
    with pytest.raises(api.GitHubReadbackBlocked, match="github_ids_invalid"):
        api.readback(run_id=True, job_id=456, runner_id=789,
                     expected_sha=SHA, expected_labels=LABELS, token="valid-token-length-0000000000",
                     fetch=lambda *a, **k: {})
    with pytest.raises(api.GitHubReadbackBlocked, match="github_expected_sha_invalid"):
        api.readback(run_id=123, job_id=456, runner_id=789,
                     expected_sha="short", expected_labels=LABELS, token="valid-token-length-0000000000",
                     fetch=lambda *a, **k: {})


def test_reject_external_host_or_path_without_network(monkeypatch):
    with pytest.raises(api.GitHubReadbackBlocked, match="github_path_not_allowed"):
        api._github_get("https://attacker.example/x", token="valid-token-length-0000000000")
    with pytest.raises(api.GitHubReadbackBlocked, match="github_read_auth_unavailable"):
        api._github_get("/actions/runs/123", token="")


def test_no_runner_host_identity_claim():
    result, _ = evaluate()
    assert "physical_host_id" not in result
    assert "runner_instance_id" not in result


def test_repeated_observation_stable_except_timestamp():
    first, _ = evaluate()
    second, _ = evaluate()
    for field in ("runner_id", "job_id", "run_id", "source_sha", "ready_for_work"):
        assert first[field] == second[field]
