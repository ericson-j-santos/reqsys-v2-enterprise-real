"""Positive/negative controls for the fixed PC24x7 DEV Worker Pool runtime version probe."""
from __future__ import annotations

import importlib.util
import inspect
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "scripts/codex_worker_pool_version_2547_probe_dev.py"
_spec = importlib.util.spec_from_file_location("fixed_pool_version_probe", FILE)
assert _spec is not None and _spec.loader is not None
probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(probe)

EXPECTED = "a" * 40


def healthy():
    return {"status": "healthy", "service": "codex-worker-pool"}


def task():
    return {
        "task_id": probe.TASK_ID,
        "issue_number": probe.ISSUE,
        "repository": probe.REPOSITORY,
        "request_id": probe.REQUEST_ID,
        "base_sha": probe.TASK_BASE_SHA,
        "state": "queued",
    }


def legacy_schema():
    return {
        "info": {"title": "ReqSys Codex Worker Pool", "version": "1.2.0"},
        "paths": {probe.TASK_PATH: {"get": {}}},
    }


def modern_schema():
    return {
        "info": {"title": "Engineering Worker Pool", "version": "1.4.0"},
        "paths": {probe.TASK_PATH: {"get": {}}, probe.OPENAPI_DIAG_TEMPLATE: {"get": {}}},
    }


def modern_diagnostics():
    return {
        "read_mode": "sqlite_mode_ro",
        "claim_performed": False,
        "reconciliation_requested": False,
        "required_role": "builder",
        "precheck_eligible_workers": 0,
        "task": {
            "task_id": probe.TASK_ID,
            "repository": probe.REPOSITORY,
            "issue_number": 2547,
            "base_sha": probe.TASK_BASE_SHA,
            "state": "queued",
        },
        "lane": {
            "configured": True, "enabled": True,
            "max_in_flight": 1, "active_count": 0,
        },
        "workers": [
            {
                "worker_id": "PRIVATE_WORKER_ID",
                "role": "builder",
                "reasons": ["offline_or_stale"],
            },
        ],
    }


def call(schema, diag=None, *, healthy_response=None, task_response=None,
         host=None, sha=None, token="private-test-token", overrides=None):
    paths = {
        "/health": (200, healthy() if healthy_response is None else healthy_response),
        "/openapi.json": (200, schema),
        probe.TASK_PATH: (200, task() if task_response is None else task_response),
        probe.DIAG_PATH: (200, modern_diagnostics() if diag is None else diag),
    }
    paths.update(overrides or {})
    calls = []

    def get(path, sent_token):
        calls.append((path, bool(sent_token)))
        return paths[path]

    outcome = probe.probe_version(
        expected_sha=EXPECTED, observed_sha=sha or EXPECTED, host=host or probe.HOST,
        token=token, request_fn=get,
    )
    return outcome, calls


def test_legacy_detected_without_mutating_or_calling_diagnostics():
    result, calls = call(legacy_schema())
    assert result["result"] == "WORKER_POOL_VERSION_PROBE_OK"
    assert result["api_version"] == "1.2.0"
    assert result["upgrade_required"] is True
    assert result["diagnostics_route_present"] is False
    assert result["runtime_source_sha_attested"] is False
    assert calls == [
        ("/health", False), ("/openapi.json", False), (probe.TASK_PATH, True),
    ]
    assert result["snapshot_called"] is False
    assert result["runtime_mutated_by_probe"] is False
    assert result["production_touched"] is False
    assert "private-test-token" not in json.dumps(result)


def test_modern_runtime_exposes_readonly_worker_precheck_with_no_ids():
    result, calls = call(modern_schema())
    assert result["api_version"] == "1.4.0"
    assert result["upgraded_diagnostics_available"] is True
    assert result["upgrade_required"] is False
    assert result["precheck_eligible_workers"] == 0
    assert result["builders_registered"] == 1
    assert result["ineligibility_reason_counts"] == {"offline_or_stale": 1}
    assert calls[-1] == (probe.DIAG_PATH, True)
    assert len(calls) == 4
    assert "PRIVATE_WORKER_ID" not in json.dumps(result)
    assert result["claim_performed"] is False
    assert result["runtime_source_sha_attested"] is False


@pytest.mark.parametrize("bad,expected", [
    ({"info": {"title": "Wrong Service", "version": "1.2.0"}, "paths": {}},
     "runtime_service_identity_unexpected"),
    ({"info": {"title": "Engineering Worker Pool", "version": "1.4.0"}, "paths": {}},
     "modern_runtime_missing_diagnostics"),
    ({"info": {"title": "ReqSys Codex Worker Pool", "version": "1.4.0"}, "paths": {}},
     "legacy_service_version_inconsistent"),
    ({"info": {"title": "Engineering Worker Pool", "version": "1.2.0"}, "paths": {}},
     "engineering_service_version_inconsistent"),
    ({"info": {"title": "ReqSys Codex Worker Pool", "version": "secret-value"}, "paths": {}},
     "runtime_version_invalid"),
])
def test_invalid_service_identity_or_version_fails_closed(bad, expected):
    with pytest.raises(probe.ProbeBlocked, match="^" + expected + "$"):
        call(bad)


def test_concrete_runtime_url_is_not_an_openapi_template():
    wrong_schema = modern_schema()
    wrong_schema["paths"] = {probe.DIAG_PATH: {"get": {}}}
    with pytest.raises(probe.ProbeBlocked, match="modern_runtime_missing_diagnostics"):
        call(wrong_schema)


def test_missing_host_invalid_sha_and_token_fail_before_transport():
    for kwargs, code in [
        ({"host": "OTHER-HOST"}, "host_identity_refused"),
        ({"sha": "b" * 40}, "checkout_sha_mismatch"),
        ({"token": ""}, "service_token_missing"),
    ]:
        with pytest.raises(probe.ProbeBlocked, match="^" + code + "$"):
            call(legacy_schema(), **kwargs)


def test_task_identity_mismatch_fails_closed():
    forged = task()
    forged["request_id"] = "foreign-request"
    with pytest.raises(probe.ProbeBlocked, match="task_identity_mismatch"):
        call(legacy_schema(), task_response=forged)


def test_old_runtime_unavailable_does_not_report_stale():
    with pytest.raises(probe.ProbeBlocked, match="health_identity_not_ready"):
        call(legacy_schema(), healthy_response={"status": "not_ready"})


@pytest.mark.parametrize("changes,reason", [
    ({"read_mode": "sqlite_mode_rw"}, "diagnostic_not_read_only"),
    ({"claim_performed": True}, "diagnostic_mutation_claimed"),
    ({"workers": [{"worker_id": "PRIVATE", "role": "builder", "reasons": ["token=PRIVATE"]}]},
     "diagnostic_reason_unsafe"),
    ({"precheck_eligible_workers": 10}, "diagnostic_worker_count_invalid"),
])
def test_diagnostics_negative_controls(changes, reason):
    payload = modern_diagnostics()
    payload.update(changes)
    with pytest.raises(probe.ProbeBlocked, match="^" + reason + "$"):
        call(modern_schema(), diag=payload)


def test_nonallowlisted_paths_are_rejected_without_transport():
    with pytest.raises(probe.ProbeBlocked, match="non_allowlisted_endpoint"):
        probe.request_json("/v1/snapshot", "private-test-token")
    with pytest.raises(probe.ProbeBlocked, match="non_allowlisted_endpoint"):
        probe.request_json("/v1/workers", "private-test-token")


def test_redirect_is_refused_and_loopback_does_not_use_proxy():
    assert probe.RefuseRedirect().redirect_request(
        None, None, 302, "Moved", {}, "https://outside.example/steal"
    ) is None
    source = inspect.getsource(probe.request_json)
    assert "build_opener(ProxyHandler({}), RefuseRedirect())" in source
    assert "urlopen(" not in source


def test_workflow_and_owner_command_are_fixed_and_non_deploying():
    workflow = (ROOT / ".github/workflows/codex-worker-pool-smoke-dev.yml").read_text()
    gateway = (ROOT / ".github/workflows/reqsys-authorized-actions-gateway.yml").read_text()
    command = "/reqsys run codex-worker-pool-version-2547-read-dev"
    assert "github.event.comment.body == '" + command + "'" in gateway
    assert "'" + command + "')" in gateway
    assert "github.event.issue.number == 1705" in gateway
    assert "github.event.comment.user.login == 'ericson-j-santos'" in gateway
    assert "mode='version-2547-read'" in gateway
    assert "-f mode=version-2547-read" in gateway
    assert "          - version-2547-read" in workflow
    assert "  version-2547-read:" in workflow
    assert "codex_worker_pool_version_2547_probe_dev.py" in workflow
    assert "SESSION_LAUNCH_OK" in workflow
    assert "WORKER_POOL_VERSION_PROBE_OK" in workflow
    assert "runtime_mutated_by_probe" in workflow
    assert "-f task_id=" not in gateway
    assert "-f worker_id=" not in gateway


def test_version_probe_evidence_location_matches_workflow():
    workflow = (ROOT / ".github/workflows/codex-worker-pool-smoke-dev.yml").read_text(encoding="utf-8")
    assert workflow.count("\n  version-2547-read:\n") == 1
    section = workflow.split("\n  version-2547-read:\n", 1)[1]
    lines = [line.strip() for line in section.splitlines() if line.strip().startswith("EVIDENCE_REL: ")]
    assert len(lines) == 1
    declared = lines[0].split("EVIDENCE_REL: ", 1)[1]
    assert (ROOT / Path(*declared.split("\\"))) == probe.EVIDENCE
    assert ("path: ${{ steps.session.outputs.target_path }}\\" + declared) in section
