"""Fixed DEV task read must never claim, enqueue, or run snapshot recovery."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "codex_worker_pool_task_2547_read_dev.py"

spec = importlib.util.spec_from_file_location("pool_task_probe", MODULE)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def task(**updates):
    obj = {
        "task_id": probe.TASK_ID,
        "repository": probe.REPOSITORY,
        "issue_number": probe.ISSUE_NUMBER,
        "request_id": probe.REQUEST_ID,
        "base_sha": probe.BASE_SHA,
        "state": "queued",
        "attempt_count": 0,
        "max_attempts": 3,
        "leased_by": None,
        "builder_worker_id": None,
        "validator_worker_id": None,
        "produced_sha": None,
    }
    obj.update(updates)
    return obj


def run(response, *, sha=None, host=None):
    calls = []

    def request(method, url, token, body):
        calls.append((method, url, body))
        return 200, response

    output = probe.probe_task(
        expected_sha=probe.BASE_SHA,
        token="test-token-never-persisted",
        host=host or probe.HOST,
        observed_sha=sha or probe.BASE_SHA,
        request_fn=request,
    )
    assert calls == [("GET", f"{probe.POOL_URL}/v1/tasks/{probe.TASK_ID}", None)]
    assert "test-token" not in repr(output)
    assert output["snapshot_called"] is False
    assert output["runtime_mutated"] is False
    assert output["worker_eligibility_checked"] is False
    return output


def test_task_queued_positive_and_single_get():
    out = run(task())
    assert out["result"] == "WORKER_POOL_TASK_READ_OK"
    assert out["state"] == "queued" and out["leased"] is False


def test_active_lease_is_hashed_without_plaintext_worker():
    out = run(task(state="running", leased_by="desktop-builder", builder_worker_id="desktop-builder", produced_sha="a" * 40))
    assert out["leased"] is True and out["produced_sha"] == "a" * 40
    assert "desktop-builder" not in repr(out)


@pytest.mark.parametrize("change,code", [
    ({"task_id": "another"}, "task_identity_mismatch"),
    ({"issue_number": 1}, "task_identity_mismatch"),
    ({"request_id": "forged"}, "task_identity_mismatch"),
    ({"base_sha": "1" * 40}, "task_identity_mismatch"),
    ({"state": "unknown"}, "task_state_invalid"),
    ({"attempt_count": 5}, "task_attempts_invalid"),
    ({"produced_sha": "bad"}, "produced_sha_invalid"),
    ({"state": "queued", "leased_by": "unexpected"}, "queued_task_has_lease"),
    ({"state": "running", "leased_by": "token=secret!"}, "worker_identity_invalid"),
])
def test_invalid_task_fails_closed(change, code):
    with pytest.raises(probe.TaskReadError, match=code):
        run(task(**change))


def test_wrong_host_does_not_contact_api():
    with pytest.raises(probe.TaskReadError, match="host_identity_refused"):
        run(task(), host="OTHER-DESKTOP")


def test_wrong_sha_does_not_contact_api():
    with pytest.raises(probe.TaskReadError, match="checkout_sha_mismatch"):
        run(task(), sha="f" * 40)


def test_bad_http_status_fails_closed():
    with pytest.raises(probe.TaskReadError, match="task_http_not_ok"):
        probe.probe_task(expected_sha=probe.BASE_SHA, token="test-token", host=probe.HOST,
             observed_sha=probe.BASE_SHA, request_fn=lambda *args: (404, {"detail": "secret"}))


def test_raw_block_reason_is_never_published():
    out = run(task(state="blocked", blocked_reason="api_key=topsecret"))
    assert out["blocked_reason_code"] == "redacted"
    assert "topsecret" not in repr(out)


def test_gateway_task_read_is_fixed_and_not_legacy_smoke():
    workflow = (ROOT / ".github/workflows/codex-worker-pool-smoke-dev.yml").read_text()
    gateway = (ROOT / ".github/workflows/reqsys-authorized-actions-gateway.yml").read_text()
    command = "/reqsys run codex-worker-pool-task-2547-read-dev"
    assert "github.event.comment.body == '" + command + "'" in gateway
    assert "'" + command + "')" in gateway
    assert "mode='task-2547-read'" in gateway
    assert "-f mode=task-2547-read" in gateway
    assert "      - task-2547-read" in workflow
    assert "  task-2547-read:" in workflow
    assert "SESSION_LAUNCH_BLOCKED" in workflow
    assert "codex_worker_pool_task_2547_read_dev.py" in workflow
    assert "WORKER_POOL_TASK_READ_OK" in workflow
    assert "SELF_HOSTED_RUNNER_PICKUP_TIMEOUT_OR_BUSY" in gateway
    assert "-f task_id=" not in gateway and "-f worker_id=" not in gateway
