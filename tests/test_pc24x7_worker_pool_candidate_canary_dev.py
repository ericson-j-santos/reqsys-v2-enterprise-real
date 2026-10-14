"""Read-only synthetic guards for the Windows DEV candidate canary."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pc24x7_worker_pool_candidate_canary_dev.py"
spec = importlib.util.spec_from_file_location("candidate_canary_test", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

SHA = "a" * 40
CORR = "pc24x7-workerpool-canary-38392720950-1"


def valid():
    return dict(host=module.HOST, expected_sha=SHA, observed_sha=SHA,
                worker_sha=module.WORKER_SHA, correlation_id=CORR,
                confirm=module.CONFIRM)


def test_valid_preconditions_are_pure():
    with patch.object(module, "execute", side_effect=AssertionError("unexpected IO")):
        module.preconditions(**valid())


@pytest.mark.parametrize(("key", "value"), [
    ("host", "OTHER"), ("expected_sha", "short"),
    ("observed_sha", "b" * 40), ("worker_sha", "b" * 40),
    ("confirm", "NO"), ("correlation_id", "../bad"),
])
def test_invalid_preconditions_fail_closed(key, value):
    args = valid()
    args[key] = value
    with patch.object(module, "execute", side_effect=AssertionError("unexpected IO")):
        with pytest.raises(module.CanaryBlocked):
            module.preconditions(**args)


def example(tmp_path):
    name = "wp-canary-38392720950-1"
    image = "sha256:" + "f" * 64
    token = tmp_path / "token"
    receipt = {
        "Name": "/" + name,
        "Image": image,
        "State": {"Running": True},
        "Config": {"User": "reqsys"},
        "HostConfig": {
            "Privileged": False, "ReadonlyRootfs": True,
            "CapDrop": ["ALL"], "NetworkMode": "bridge",
            "PortBindings": {"8097/tcp": [{"HostIp": "127.0.0.1", "HostPort": "18098"}]},
        },
        "Mounts": [
            {"Destination": "/data", "Type": "volume", "Name": name, "RW": True},
            {"Destination": "/run/secrets/canary-token", "Type": "bind",
             "Source": str(token), "RW": False},
        ],
    }
    return receipt, image, name, token


def test_candidate_isolation_positive(tmp_path):
    receipt, image, name, token = example(tmp_path)
    module.candidate_identity(receipt, image=image, name=name,
                              volume=name, token_file=token)


@pytest.mark.parametrize("kind", [
    "public", "legacy", "privileged", "writable", "wrong_volume", "rw_token", "stopped",
])
def test_candidate_isolation_negative(tmp_path, kind):
    receipt, image, name, token = example(tmp_path)
    if kind == "public":
        receipt["HostConfig"]["PortBindings"]["8097/tcp"][0]["HostIp"] = "0.0.0.0"
    elif kind == "legacy":
        receipt["HostConfig"]["PortBindings"]["8097/tcp"][0]["HostPort"] = "8097"
    elif kind == "privileged":
        receipt["HostConfig"]["Privileged"] = True
    elif kind == "writable":
        receipt["HostConfig"]["ReadonlyRootfs"] = False
    elif kind == "wrong_volume":
        receipt["Mounts"][0]["Name"] = "noncanary"
    elif kind == "rw_token":
        receipt["Mounts"][1]["RW"] = True
    elif kind == "stopped":
        receipt["State"]["Running"] = False
    with pytest.raises(module.CanaryBlocked):
        module.candidate_identity(receipt, image=image, name=name,
                                  volume=name, token_file=token)


def test_minimal_build_context_does_not_copy_other_paths(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    (source / "requirements.txt").write_text("one==1\n", encoding="utf-8")
    (source / "app").mkdir()
    (source / "app" / "main.py").write_text("value=1\n", encoding="utf-8")
    (source / "excluded-file").write_text("excluded", encoding="utf-8")
    target = tmp_path / "build"
    module.safe_staging(source, target)
    assert sorted(str(p.relative_to(target)) for p in target.rglob("*") if p.is_file()) == [
        "Dockerfile", "app/main.py", "requirements.txt"
    ]


def test_redirect_and_nonloopback_are_never_accepted():
    with pytest.raises(module.CanaryBlocked, match="candidate_url_invalid"):
        module.request("GET", "http://127.0.0.1:8097/health", "fixture", None)
    with pytest.raises(module.CanaryBlocked, match="candidate_url_invalid"):
        module.request("GET", "https://example.invalid/health", "fixture", None)


def test_workflow_and_gateway_scope():
    workflow = (ROOT / ".github/workflows/codex-worker-pool-smoke-dev.yml").read_text()
    gateway = (ROOT / ".github/workflows/reqsys-authorized-actions-gateway.yml").read_text()
    job = workflow.split("\n  candidate-canary:\n", 1)[1]
    for word in ("self-hosted, Windows, X64, pc24x7, reqsys-dev", "session_launcher.py",
                 "SESSION_LAUNCH_OK", "command_gateway.py", "--expected-head",
                 "pc24x7_worker_pool_candidate_canary_dev.py", "cutover_ready",
                 "WORKER_POOL_DEV_PHYSICAL_ISOLATED_CANARY_VERIFIED"):
        assert word in job
    command = "/reqsys run pc24x7-worker-pool-candidate-canary-dev"
    assert f"github.event.comment.body == '{command}'" in gateway
    assert "mode='candidate-canary'" in gateway
    assert "-f mode=candidate-canary" in gateway
    assert "github.event.issue.number == 1705" in gateway
    assert "github.event.comment.user.login == 'ericson-j-santos'" in gateway
    assert "          - candidate-canary" in workflow


def test_canary_never_means_cutover_ready():
    text = SCRIPT.read_text()
    assert '"cutover_ready": False' in text
    assert '"real_backup_imported_into_candidate": False' in text
    assert '"rollback_rehearsal_passed": False' in text
    assert '"live_database_modified": False' in text
    assert '"claim_performed": False' in text
    assert '"127.0.0.1:18098:8097"' in text


def test_candidate_startup_retries_only_transient_http_unavailability():
    responses = [module.CanaryBlocked("candidate_http_unavailable"),
                 (200, {"status": "healthy"})]
    with patch.object(module, "request", side_effect=responses) as req:
        with patch.object(module.time, "sleep") as sleeper:
            module.wait_for_candidate_health("synthetic-token")
    assert req.call_count == 2
    sleeper.assert_called_once_with(0.5)


def test_candidate_startup_rejects_policy_fault_without_retry():
    with patch.object(module, "request",
                      side_effect=module.CanaryBlocked("candidate_url_invalid")) as req:
        with patch.object(module.time, "sleep") as sleeper:
            with pytest.raises(module.CanaryBlocked, match="candidate_url_invalid"):
                module.wait_for_candidate_health("synthetic-token")
    req.assert_called_once()
    sleeper.assert_not_called()


def test_candidate_startup_terminal_timeout_never_approves_canary():
    with patch.object(module, "request",
                      side_effect=module.CanaryBlocked("candidate_http_unavailable")) as req:
        with patch.object(module.time, "sleep") as sleeper:
            with pytest.raises(module.CanaryBlocked, match="candidate_not_ready"):
                module.wait_for_candidate_health("synthetic-token")
    assert req.call_count == 26
    assert sleeper.call_count == 26


def test_docker_desktop_bind_sources_match_only_exact_token():
    """Win32 vs Linux VM bind mapping must resolve to the same precise file."""
    original = r"C:\Users\Windows\AppData\Local\ReqSys\WorkerPoolCanary\test-run\test-token"
    translated = [
        original,
        "c:/Users/Windows/AppData/Local/ReqSys/WorkerPoolCanary/test-run/test-token",
        "/run/desktop/mnt/host/c/Users/Windows/AppData/Local/ReqSys/WorkerPoolCanary/test-run/test-token",
        "/host_mnt/c/Users/Windows/AppData/Local/ReqSys/WorkerPoolCanary/test-run/test-token",
    ]
    for source in translated:
        assert module._same_token_mount_source(source, original)
        assert module._same_token_mount_source(source, original)

    bad_sources = [
        "/host_mnt/d/Users/Windows/AppData/Local/ReqSys/WorkerPoolCanary/test-run/test-token",
        "/run/desktop/mnt/host/c/Users/Windows/AppData/Local/ReqSys/WorkerPoolCanary/test-run/other-token",
        "/etc/secret",
        "/mnt/c/Users/Windows/AppData/Local/ReqSys/WorkerPoolCanary/test-run/test-token",
        "c:/Users/Windows/AppData/Local/ReqSys/WorkerPoolCanary/test-run/../test-token",
        "",
    ]
    for source in bad_sources:
        assert not module._same_token_mount_source(source, original)


def test_isolation_distinguishes_data_mount_token_flags_and_source(tmp_path):
    payload, image, name, token = example(tmp_path)
    for mutation, reason in (
        ("volume", "candidate_data_mount_invalid"),
        ("flags", "candidate_token_mount_flags_invalid"),
        ("source", "candidate_token_mount_source_invalid"),
    ):
        import copy

        receipt = copy.deepcopy(payload)
        if mutation == "volume":
            receipt["Mounts"][0]["Name"] = "foreign"
        elif mutation == "flags":
            receipt["Mounts"][1]["RW"] = True
        else:
            receipt["Mounts"][1]["Source"] = str(tmp_path / "foreign-token")
        with pytest.raises(module.CanaryBlocked, match="^" + reason + "$"):
            module.candidate_identity(receipt, image=image, name=name,
                                      volume=name, token_file=token)

def test_candidate_sha_pin_is_consistent_with_physical_precondition():
    """Avoid a costly physical canary with divergent worker source identities."""
    import re

    workflow = (ROOT / ".github/workflows/codex-worker-pool-smoke-dev.yml").read_text(encoding="utf-8")
    candidate_job = workflow.split("\n  candidate-canary:\n", 1)[1]
    pinned = re.findall(r"(?m)^      WORKER_POOL_SHA: ([0-9a-f]{40})$", candidate_job)
    assert pinned == [module.WORKER_SHA]
    assert module.SHA40.fullmatch(module.WORKER_SHA) is not None
