from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pre_pr_readiness.py"
WORKFLOW_PATH = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "pre-pr-readiness.yml"
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
    common_install = "python -m pip install --disable-pip-version-check PyYAML pytest 'httpx==0.28.1' 'openpyxl==3.1.5'"
    backend_branch = "if git diff --name-only \"origin/$BASE_REF...HEAD\" | grep -q '^backend/'; then"

    assert common_install in workflow
    assert backend_branch in workflow
    assert workflow.index(common_install) < workflow.index(backend_branch)


def test_negative_self_test_proves_detector_is_fail_closed() -> None:
    assert MODULE.self_test_negative() is True
