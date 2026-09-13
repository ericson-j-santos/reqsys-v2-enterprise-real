from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pre_pr_readiness.py"
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


def test_negative_self_test_proves_detector_is_fail_closed() -> None:
    assert MODULE.self_test_negative() is True
