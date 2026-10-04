from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "testing" / "orchestrate.py"
SPEC = importlib.util.spec_from_file_location("reqsys_quality_orchestrator", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_manifest_and_schema_are_loadable_and_consistent():
    manifest = MODULE.load_manifest()
    schema = MODULE.load_schema()

    assert manifest["schema_version"] == "1.0"
    assert manifest["mode"] == "report-only"
    assert manifest["default_profile"] in manifest["profiles"]
    assert schema["$schema"].endswith("2020-12/schema")

    referenced = {
        suite_id
        for profile in manifest["profiles"].values()
        for suite_id in profile["suites"]
    }
    assert referenced <= set(manifest["suites"])


def test_pr_profile_routes_only_impacted_suites_but_keeps_selftest():
    manifest = MODULE.load_manifest()

    selected = dict(
        MODULE.select_suites(
            manifest,
            "pr",
            ["backend/app/services/example.py"],
        )
    )

    assert "quality_fabric_selftest" in selected
    assert "backend_tests" in selected
    assert "frontend_unit" not in selected
    assert "frontend_build" not in selected
    assert "frontend_e2e_responsive" not in selected


def test_auth_frontend_change_routes_unit_build_and_e2e():
    manifest = MODULE.load_manifest()

    selected = dict(
        MODULE.select_suites(
            manifest,
            "pr",
            ["frontend/src/services/authSession.js"],
        )
    )

    assert "quality_fabric_selftest" in selected
    assert "frontend_unit" in selected
    assert "frontend_build" in selected
    assert "frontend_e2e_responsive" in selected
    assert "backend_tests" not in selected


@pytest.mark.parametrize("unsafe", ["../outside", "/tmp/outside"])
def test_manifest_rejects_workdir_outside_repository(unsafe):
    manifest = MODULE.load_manifest()
    manifest["suites"]["quality_fabric_selftest"]["cwd"] = unsafe

    with pytest.raises(MODULE.ManifestError):
        MODULE.validate_manifest(manifest)


def test_run_suite_uses_argv_without_shell_and_redacts_sensitive_output(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="ok TOKEN=abc123",
            stderr="PASSWORD: super-secret",
        )

    monkeypatch.setattr(MODULE.subprocess, "run", fake_run)

    result = MODULE.run_suite(
        "probe",
        {
            "description": "probe",
            "cwd": ".",
            "command": ["{python}", "-c", "print('ok')"],
            "timeout_seconds": 5,
            "always_run": True,
            "paths": [],
            "evidence_kind": "governance",
        },
        profile_name="fast",
        correlation_id="qf-test",
    )

    assert result["status"] == "passed"
    assert result["command"][0] == sys.executable
    assert "abc123" not in result["stdout_tail"]
    assert "super-secret" not in result["stderr_tail"]
    assert "shell" not in calls[0][1]
    assert calls[0][1]["env"]["REQSYS_CORRELATION_ID"] == "qf-test"


def test_write_evidence_produces_json_markdown_junit_and_manifest_hash(tmp_path):
    manifest_path = ROOT / "governance" / "testing" / "test-matrix.yaml"
    evidence = {
        "schema_version": "1.0",
        "mode": "report-only",
        "profile": "fast",
        "commit_sha": "abc123",
        "correlation_id": "qf-test",
        "started_at_epoch": 1,
        "finished_at_epoch": 2,
        "changed_files": None,
        "selected_suites": ["probe"],
        "summary": {
            "total": 1,
            "passed": 1,
            "failed": 0,
            "timeout": 0,
            "error": 0,
            "planned": 0,
        },
        "decision": "pass",
        "results": [
            {
                "id": "probe",
                "description": "probe",
                "evidence_kind": "governance",
                "cwd": ".",
                "command": [sys.executable, "-V"],
                "timeout_seconds": 5,
                "status": "passed",
                "exit_code": 0,
                "duration_seconds": 0.01,
                "stdout_tail": "",
                "stderr_tail": "",
            }
        ],
        "manifest_sha256": "0" * 64,
    }

    paths = MODULE.write_evidence(evidence, tmp_path, manifest_path)

    assert set(paths) == {"json", "markdown", "junit", "manifest_sha256"}
    assert json.loads(paths["json"].read_text(encoding="utf-8"))["decision"] == "pass"
    assert "ReqSys Quality Fabric" in paths["markdown"].read_text(encoding="utf-8")
    assert "<testsuite" in paths["junit"].read_text(encoding="utf-8")
    assert paths["manifest_sha256"].read_text(encoding="utf-8").startswith("0" * 64)


def test_dry_run_builds_planned_evidence_without_executing_suite(monkeypatch, tmp_path):
    manifest = MODULE.load_manifest()
    selected = MODULE.select_suites(
        manifest,
        "pr",
        ["governance/testing/test-matrix.yaml"],
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("subprocess.run não deveria executar suítes em dry-run")

    original_current_commit_sha = MODULE.current_commit_sha
    monkeypatch.setattr(MODULE, "current_commit_sha", lambda: "deadbeef" * 5)
    monkeypatch.setattr(MODULE.subprocess, "run", fail_if_called)

    evidence = MODULE.build_evidence(
        manifest_path=ROOT / "governance" / "testing" / "test-matrix.yaml",
        profile_name="pr",
        selected=selected,
        changed=["governance/testing/test-matrix.yaml"],
        dry_run=True,
    )

    monkeypatch.setattr(MODULE, "current_commit_sha", original_current_commit_sha)

    assert evidence["decision"] == "planned"
    assert evidence["summary"]["planned"] == len(selected)
    assert evidence["selected_suites"] == ["quality_fabric_selftest"]


def test_cli_requires_base_and_head_together():
    with pytest.raises(MODULE.ManifestError):
        MODULE.main(["--base-sha", "abc", "--dry-run"])
