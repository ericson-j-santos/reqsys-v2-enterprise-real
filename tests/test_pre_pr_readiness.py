from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pre_pr_readiness.py"
WORKFLOW_PATH = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "pre-pr-readiness.yml"
MERGE_POLICY_PATH = Path(__file__).resolve().parents[1] / "governance" / "merge" / "current-sha-required-workflows.json"
MERGE_QUEUE_WORKFLOW_PATH = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "governed-merge-queue.yml"
SPEC = importlib.util.spec_from_file_location("pre_pr_readiness", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_detect_profiles_docs_only() -> None:
    assert MODULE.detect_profiles(["docs/guide.md"]) == ["docs_only"]


def test_detect_profiles_operational_and_frontend() -> None:
    profiles = MODULE.detect_profiles([".github/workflows/x.yml", "frontend/src/App.vue"])
    assert profiles == ["frontend", "operational"]


def test_candidate_pytests_links_script_to_matching_test(tmp_path: Path) -> None:
    test_file = tmp_path / "tests" / "test_alpha.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    assert MODULE.candidate_pytests(["scripts/alpha.py"], tmp_path) == ["tests/test_alpha.py"]


def test_targeted_pytests_uses_backend_as_import_root(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, list[str], Path | None]] = []

    def fake_timed_check(name: str, command: list[str], *, cwd: Path | None = None):
        calls.append((name, command, cwd))
        return MODULE.CheckResult(name, "passed", "ok", 0.0)

    monkeypatch.setattr(MODULE, "_timed_check", fake_timed_check)
    results = MODULE.targeted_pytest_checks(
        ["tests/test_gate.py", "backend/tests/test_api.py"],
        tmp_path,
    )

    assert [item.status for item in results] == ["passed", "passed"]
    assert calls[0][0] == "targeted:pytest:root"
    assert calls[0][1][-2:] == ["tests/test_gate.py", "-q"]
    assert calls[0][2] == tmp_path
    assert calls[1][0] == "targeted:pytest:backend"
    assert calls[1][1][-2:] == ["tests/test_api.py", "-q"]
    assert calls[1][2] == tmp_path / "backend"


def test_targeted_pytests_fails_closed_for_unknown_test_root(tmp_path: Path) -> None:
    results = MODULE.targeted_pytest_checks(["custom/tests/test_x.py"], tmp_path)
    assert len(results) == 1
    assert results[0].status == "failed"
    assert "sem import root conhecido" in results[0].detail


def test_invalid_json_is_detected(tmp_path: Path) -> None:
    invalid = tmp_path / "broken.json"
    invalid.write_text("{broken", encoding="utf-8")
    results = MODULE.validate_structured_files(["broken.json"], tmp_path)
    assert len(results) == 1
    assert results[0].status == "failed"


def test_valid_workflow_yaml_is_accepted(tmp_path: Path) -> None:
    workflow = tmp_path / ".github" / "workflows" / "sample.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        "name: Sample\non:\n  push:\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo ok\n",
        encoding="utf-8",
    )
    results = MODULE.validate_structured_files([".github/workflows/sample.yml"], tmp_path)
    assert len(results) == 1
    assert results[0].status == "passed"


def test_workflow_installs_root_dependencies_before_backend_profile_branch() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    common_install = "python -m pip install --disable-pip-version-check PyYAML pytest ruff 'httpx==0.28.1' 'openpyxl==3.1.5'"
    backend_branch = "if git diff --name-only \"origin/$BASE_REF...HEAD\" | grep -q '^backend/'; then"

    assert common_install in workflow
    assert backend_branch in workflow
    assert workflow.index(common_install) < workflow.index(backend_branch)


def test_negative_self_test_proves_detector_is_fail_closed() -> None:
    assert MODULE.self_test_negative() is True


def test_referenced_contract_tests_discovers_aggregate_test(tmp_path: Path) -> None:
    test_file = tmp_path / "tests" / "test_control_plane.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text(
        'MODULE = "scripts/noteri_control_plane_watchdog.py"\n',
        encoding="utf-8",
    )
    result = MODULE.referenced_contract_tests(
        ["scripts/noteri_control_plane_watchdog.py"],
        tmp_path,
    )
    assert result == ["tests/test_control_plane.py"]


def test_referenced_contract_tests_ignores_generic_frontend_names_and_stems(tmp_path: Path) -> None:
    test_file = tmp_path / "tests" / "test_unrelated.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text(
        'ENTRY = "main.js"\nTEMPLATE = "index.html"\nMAIN = "backend/app/main.py"\nEVIDENCE = "delivery-evidence-index"\n',
        encoding="utf-8",
    )

    result = MODULE.referenced_contract_tests(
        ["frontend/src/main.js", "frontend/index.html"],
        tmp_path,
    )

    assert result == []


def test_candidate_pytests_includes_python_tests_declared_by_changed_sdd(tmp_path: Path) -> None:
    declared = tmp_path / "tests" / "test_noteri_agent.py"
    declared.parent.mkdir(parents=True)
    declared.write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    spec = tmp_path / ".sdd" / "specs" / "noteri.spec.json"
    spec.parent.mkdir(parents=True)
    spec.write_text(
        json.dumps(
            {
                "sdd_gate": {
                    "tests": [
                        "tests/test_noteri_agent.py",
                        "frontend/src/auth/__tests__/startupFailSafe.test.js",
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    result = MODULE.candidate_pytests(
        [".sdd/specs/noteri.spec.json", "frontend/src/main.js"],
        tmp_path,
    )

    assert result == ["tests/test_noteri_agent.py"]


def test_validate_python_runs_ruff_for_changed_python(monkeypatch, tmp_path: Path) -> None:
    script = tmp_path / "scripts" / "alpha.py"
    script.parent.mkdir(parents=True)
    script.write_text("x = 1\n", encoding="utf-8")
    calls: list[tuple[str, list[str], Path | None]] = []

    def fake_timed_check(name: str, command: list[str], *, cwd: Path | None = None):
        calls.append((name, command, cwd))
        return MODULE.CheckResult(name, "passed", "ok", 0.0)

    monkeypatch.setattr(MODULE, "_timed_check", fake_timed_check)
    results = MODULE.validate_python(["scripts/alpha.py"], tmp_path)

    assert [item.name for item in results] == [
        "py_compile:scripts/alpha.py",
        "python:ruff:changed",
    ]
    assert calls[1][1][:4] == [sys.executable, "-m", "ruff", "check"]
    assert calls[1][1][4:8] == ["--select", "E,F", "--ignore", "E501"]
    assert "scripts/alpha.py" in calls[1][1]


def test_validate_shell_runs_bash_syntax_check(monkeypatch, tmp_path: Path) -> None:
    script = tmp_path / "scripts" / "alpha.sh"
    script.parent.mkdir(parents=True)
    script.write_text("#!/usr/bin/env bash\necho ok\n", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_timed_check(name: str, command: list[str], *, cwd: Path | None = None):
        calls.append(command)
        return MODULE.CheckResult(name, "passed", "ok", 0.0)

    monkeypatch.setattr(MODULE, "_timed_check", fake_timed_check)
    results = MODULE.validate_shell(["scripts/alpha.sh"], tmp_path)

    assert results[0].name == "shell:bash-n:changed"
    assert calls == [["bash", "-n", "scripts/alpha.sh"]]


def test_pre_pr_workflow_installs_ruff_before_readiness() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "PyYAML pytest ruff" in workflow
    assert "python scripts/pre_pr_readiness.py" in workflow


def test_governed_merge_requires_pre_pr_readiness_on_current_sha() -> None:
    policy = json.loads(MERGE_POLICY_PATH.read_text(encoding="utf-8"))
    assert "Pre-PR Readiness Gate" in policy["required_workflows"]
    assert "Pre-PR Readiness Gate" not in policy["optional_when_not_registered"]


def test_pre_pr_runs_on_push_and_pull_request_using_exact_pr_head() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "pull_request:\n    branches:\n      - main" in workflow
    assert "EVALUATED_SHA: ${{ github.event.pull_request.head.sha || github.sha }}" in workflow
    assert "BASE_REF: ${{ github.event.pull_request.base.ref || github.event.inputs.base_ref || 'main' }}" in workflow
    assert "ref: ${{ env.EVALUATED_SHA }}" in workflow
    assert '--expected-head-sha "$EVALUATED_SHA"' in workflow


def test_merge_queue_can_require_pre_pr_from_pull_request_event() -> None:
    workflow = MERGE_QUEUE_WORKFLOW_PATH.read_text(encoding="utf-8")
    assert '-f event="pull_request"' in workflow
    policy = json.loads(MERGE_POLICY_PATH.read_text(encoding="utf-8"))
    assert "Pre-PR Readiness Gate" in policy["required_workflows"]
