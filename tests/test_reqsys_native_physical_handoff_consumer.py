from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.reqsys_native_physical_handoff_consumer import (
    E2E_PLATFORM_SHA,
    VALIDATOR_RELATIVE_PATH,
    VALIDATOR_SHA256,
    consume_physical_handoff,
)
from scripts.validate_reqsys_native_dev_profile import NativeAdmissionBlocked

HEAD = "a" * 40
PUBLIC = "b" * 64


def fixture(tmp_path: Path):
    root = tmp_path / "platform"
    root.mkdir()
    validator = root / VALIDATOR_RELATIVE_PATH
    validator.parent.mkdir()
    # Tests patch the published digest to the bytes generated here.
    validator.write_text("# official validator fixture\n", encoding="utf-8")
    evidence = tmp_path / "evidence.json"
    evidence.write_text("{}", encoding="utf-8")
    return root, validator, evidence


def result(**changes):
    value = {
        "result": "PHYSICAL_HANDOFF_EVIDENCE_VALID",
        "repository": "ericson-j-santos/reqsys-v2-enterprise-real",
        "pr_number": 3141,
        "head_sha": HEAD,
        "workflow_run_id": 100,
        "job_id": 200,
        "run_attempt": 3,
        "task_id": "task-0001",
        "physical_hosts": ["host-a-00000001", "host-b-00000002"],
        "dispatch_allowed": False,
        "merge_authorized": False,
        "deployment_authorized": False,
    }
    value.update(changes)
    return value


def runner(output=None, *, platform_sha=E2E_PLATFORM_SHA):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if command[0] == "git":
            return subprocess.CompletedProcess(command, 0, platform_sha + "\n", "")
        return subprocess.CompletedProcess(command, 0, json.dumps(output or result()), "")
    return run, calls


def invoke(tmp_path, monkeypatch, output=None, **changes):
    root, validator, evidence = fixture(tmp_path)
    import scripts.reqsys_native_physical_handoff_consumer as module

    monkeypatch.setattr(
        module,
        "VALIDATOR_SHA256",
        __import__("hashlib").sha256(validator.read_bytes()).hexdigest(),
    )
    run, calls = runner(output)
    args = {
        "platform_root": root.resolve(),
        "evidence": evidence.resolve(),
        "public_key_hex": PUBLIC,
        "expected_pr_number": 3141,
        "expected_head_sha": HEAD,
        "expected_environment": "dev",
        "expected_run_id": 100,
        "expected_job_id": 200,
        "expected_run_attempt": 3,
        "run": run,
    }
    args.update(changes)
    return consume_physical_handoff(**args), calls


def test_positive_is_bound_and_never_authorizes_operations(tmp_path, monkeypatch):
    observed, calls = invoke(tmp_path, monkeypatch)
    assert observed["native_physical_admitted"] is True
    assert observed["physical_hosts"] == ["host-a-00000001", "host-b-00000002"]
    assert observed["dispatch_allowed"] is False
    assert observed["merge_authorized"] is False
    assert observed["deployment_authorized"] is False
    assert calls[1][calls[1].index("--expected-run-attempt") + 1] == "3"


@pytest.mark.parametrize(
    "changed",
    [
        {"head_sha": "f" * 40},
        {"run_attempt": 2},
        {"physical_hosts": ["host-a-00000001"]},
        {"dispatch_allowed": True},
        {"merge_authorized": True},
        {"deployment_authorized": True},
    ],
)
def test_result_drift_fails_closed(tmp_path, monkeypatch, changed):
    with pytest.raises(NativeAdmissionBlocked, match="physical_handoff_result_mismatch"):
        invoke(tmp_path, monkeypatch, output=result(**changed))


def test_platform_sha_and_validator_hash_fail_closed(tmp_path, monkeypatch):
    root, validator, evidence = fixture(tmp_path)
    run, _ = runner(result(), platform_sha="f" * 40)
    import scripts.reqsys_native_physical_handoff_consumer as module

    monkeypatch.setattr(
        module,
        "VALIDATOR_SHA256",
        __import__("hashlib").sha256(validator.read_bytes()).hexdigest(),
    )
    with pytest.raises(NativeAdmissionBlocked, match="e2e_platform_sha_mismatch"):
        consume_physical_handoff(
            platform_root=root.resolve(),
            evidence=evidence.resolve(),
            public_key_hex=PUBLIC,
            expected_pr_number=3141,
            expected_head_sha=HEAD,
            expected_environment="dev",
            expected_run_id=100,
            expected_job_id=200,
            expected_run_attempt=3,
            run=run,
        )
    monkeypatch.setattr(module, "VALIDATOR_SHA256", VALIDATOR_SHA256)
    with pytest.raises(NativeAdmissionBlocked, match="validator_hash_mismatch"):
        consume_physical_handoff(
            platform_root=root.resolve(),
            evidence=evidence.resolve(),
            public_key_hex=PUBLIC,
            expected_pr_number=3141,
            expected_head_sha=HEAD,
            expected_environment="dev",
            expected_run_id=100,
            expected_job_id=200,
            expected_run_attempt=3,
            run=run,
        )
