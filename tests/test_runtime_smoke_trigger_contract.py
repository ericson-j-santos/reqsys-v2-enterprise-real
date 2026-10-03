from __future__ import annotations

from pathlib import Path


WORKFLOW_PATH = Path(".github/workflows/runtime-production-smoke-governed.yml")


def _workflow_text() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def _section(text: str, start_marker: str, end_marker: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def test_runtime_smoke_runs_after_every_main_push_without_path_filter() -> None:
    workflow = _workflow_text()
    push_section = _section(workflow, "  push:\n", "\npermissions:")

    assert "    branches: [main]" in push_section
    assert "paths:" not in push_section


def test_runtime_smoke_keeps_pr_path_filter_for_low_wip() -> None:
    workflow = _workflow_text()
    pull_request_section = _section(workflow, "  pull_request:\n", "\n  push:")

    assert "    branches: [main]" in pull_request_section
    assert "    paths:" in pull_request_section
    assert '".github/workflows/runtime-production-smoke-governed.yml"' in pull_request_section
    assert '"scripts/runtime_production_smoke_governed.py"' in pull_request_section
    assert '"tests/test_runtime_production_smoke_governed.py"' in pull_request_section
