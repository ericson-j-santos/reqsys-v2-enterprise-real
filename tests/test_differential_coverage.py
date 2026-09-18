from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "testing" / "differential_coverage.py"
SPEC = importlib.util.spec_from_file_location("differential_coverage", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_parse_changed_lines_handles_multiple_files_and_zero_count():
    diff = """diff --git a/backend/app/a.py b/backend/app/a.py
+++ b/backend/app/a.py
@@ -10,0 +11,2 @@
+x
+y
diff --git a/backend/app/b.py b/backend/app/b.py
+++ b/backend/app/b.py
@@ -5 +5,0 @@
-old
@@ -8 +8 @@
-old
+new
"""
    changed = MODULE.parse_changed_lines(diff)
    assert changed["backend/app/a.py"] == {11, 12}
    assert changed["backend/app/b.py"] == {8}


def test_evaluate_counts_only_executable_changed_lines():
    coverage = {
        "files": {
            "app/service.py": {
                "executed_lines": [10, 12],
                "missing_lines": [11],
                "excluded_lines": [13],
            }
        }
    }
    changed = {"backend/app/service.py": {10, 11, 13, 99}}

    result = MODULE.evaluate_differential_coverage(coverage, changed, minimum=85.0)

    assert result["executable_changed_lines"] == 2
    assert result["covered_changed_lines"] == 1
    assert result["missing_changed_lines"] == 1
    assert result["coverage_percent"] == 50.0
    assert result["status"] == "warning"


def test_evaluate_passes_at_or_above_reference():
    coverage = {
        "files": {
            "backend/app/service.py": {
                "executed_lines": [1, 2, 3, 4, 5, 6, 7, 8, 9],
                "missing_lines": [10],
            }
        }
    }
    changed = {"backend/app/service.py": set(range(1, 11))}
    result = MODULE.evaluate_differential_coverage(coverage, changed, minimum=85.0)
    assert result["coverage_percent"] == 90.0
    assert result["status"] == "pass"


def test_evaluate_not_applicable_when_no_executable_backend_change():
    coverage = {"files": {"app/service.py": {"executed_lines": [1], "missing_lines": []}}}
    changed = {
        "backend/app/service.py": {100},
        "frontend/src/App.vue": {1},
    }
    result = MODULE.evaluate_differential_coverage(coverage, changed, minimum=85.0)
    assert result["coverage_percent"] is None
    assert result["status"] == "not_applicable"


def test_render_markdown_explicitly_states_report_only():
    evidence = {
        "status": "warning",
        "coverage_percent": 75.0,
        "minimum_percent": 85.0,
        "executable_changed_lines": 4,
        "covered_changed_lines": 3,
        "missing_changed_lines": 1,
        "files": [],
    }
    markdown = MODULE.render_markdown(evidence)
    assert "Report-only" in markdown
    assert "não bloqueia merge" in markdown


def test_normalize_coverage_path_prefixes_backend():
    assert MODULE.normalize_coverage_path("app/api.py") == "backend/app/api.py"
    assert MODULE.normalize_coverage_path("backend/app/api.py") == "backend/app/api.py"
