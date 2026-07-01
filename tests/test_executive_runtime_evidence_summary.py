from __future__ import annotations

import json
from pathlib import Path

from scripts.executive_runtime_evidence_summary import build_summary, main, render_markdown


def _smoke(status: str = "healthy") -> dict:
    return {
        "status": status,
        "base_url": "https://reqsys-app.fly.dev",
        "required_ok": 4,
        "required_total": 4,
        "required_success_percentual": 100.0,
        "total_success_percentual": 91.0,
        "average_latency_ms": 120,
        "github_run_id": "10",
        "checks": [
            {"path": "/health", "required": True, "ok": True},
            {"path": "/api/runtime/health", "required": True, "ok": True},
        ],
    }


def _sentinel(status: str = "ready") -> dict:
    return {
        "status": status,
        "workflow_name": "Runtime Production Smoke Governed",
        "run_id": 20,
        "run_url": "https://github.com/example/repo/actions/runs/20",
        "expected_artifact": "runtime-production-smoke-governed",
        "artifacts": ["runtime-production-smoke-governed"],
        "blocking_issues": [],
    }


def test_build_summary_passed_when_smoke_and_sentinel_are_ready() -> None:
    payload = build_summary(_smoke(), _sentinel(), repo="example/repo", run_id="30")

    assert payload["contract"] == "executive-runtime-evidence-summary"
    assert payload["summary"]["status"] == "passed"
    assert payload["summary"]["risk"] == "low"
    assert payload["summary"]["production_ready"] is True
    assert payload["cards"]["runtime_smoke"]["required"] == "4/4"
    assert payload["cards"]["post_merge_sentinel"]["artifact_present"] is True


def test_build_summary_warns_when_source_artifacts_are_missing() -> None:
    payload = build_summary({}, {}, repo="example/repo")

    assert payload["summary"]["status"] == "warning"
    assert payload["summary"]["risk"] == "medium"
    assert payload["summary"]["production_ready"] is False
    assert "runtime_smoke_artifact_missing" in payload["cards"]["runtime_smoke"]["blocking_issues"]
    assert "post_merge_sentinel_artifact_missing" in payload["cards"]["post_merge_sentinel"]["blocking_issues"]


def test_build_summary_marks_critical_when_smoke_is_degraded() -> None:
    smoke = _smoke(status="degraded")
    smoke["checks"] = [{"path": "/api/runtime/health", "required": True, "ok": False}]
    payload = build_summary(smoke, _sentinel(), repo="example/repo")

    assert payload["summary"]["status"] == "critical"
    assert payload["summary"]["risk"] == "high"
    assert "/api/runtime/health" in payload["cards"]["runtime_smoke"]["blocking_issues"]


def test_render_markdown_exposes_executive_fields() -> None:
    payload = build_summary(_smoke(), _sentinel(), repo="example/repo")

    markdown = render_markdown(payload)

    assert "Executive Runtime Evidence Summary" in markdown
    assert "Runtime smoke" in markdown
    assert "Post-merge sentinel" in markdown
    assert "Production ready" in markdown


def test_main_writes_json_and_markdown(tmp_path: Path, monkeypatch) -> None:
    smoke_path = tmp_path / "smoke.json"
    sentinel_path = tmp_path / "sentinel.json"
    output_dir = tmp_path / "out"
    smoke_path.write_text(json.dumps(_smoke()), encoding="utf-8")
    sentinel_path.write_text(json.dumps(_sentinel()), encoding="utf-8")

    monkeypatch.setattr(
        "sys.argv",
        [
            "executive_runtime_evidence_summary.py",
            "--runtime-smoke",
            str(smoke_path),
            "--post-merge-sentinel",
            str(sentinel_path),
            "--repo",
            "example/repo",
            "--github-run-id",
            "30",
            "--output-dir",
            str(output_dir),
        ],
    )

    assert main() == 0
    assert (output_dir / "executive-runtime-evidence-summary.json").exists()
    assert (output_dir / "summary.md").exists()
