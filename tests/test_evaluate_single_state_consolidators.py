from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.evaluate_single_state_consolidators import (
    evaluate_consolidators,
    load_json_object,
    main,
    render_markdown,
)

NOW = 1_785_534_000


def _validator(**overrides: object) -> dict:
    payload = {
        "contract": "post-merge-main-runtime-validator",
        "generated_at_epoch": NOW - 5,
        "repo": "example/repo",
        "sha": "abc",
        "github_run_id": "123",
        "status": "passed",
    }
    payload.update(overrides)
    return payload


def _snapshot(**overrides: object) -> dict:
    payload = {
        "contract": "main-operational-state-snapshot",
        "generated_at_epoch": NOW,
        "repo": "example/repo",
        "sha": "abc",
        "github_run_id": "123",
        "status": "passed",
        "branch": "main",
        "current_pr": None,
        "critical_evidence": "present",
        "dominant_blocker": "none",
    }
    payload.update(overrides)
    return payload


def _evaluate(validator: dict | None = None, snapshot: dict | None = None) -> dict:
    return evaluate_consolidators(
        validator if validator is not None else _validator(),
        snapshot if snapshot is not None else _snapshot(),
        observed_at_epoch=NOW,
    )


def test_consistent_artifacts_pass() -> None:
    report = _evaluate()

    assert report["ready"] is True
    assert report["status"] == "passed"
    assert report["decision"] == "single_state_consolidators_consistent"
    assert report["blocking_issues"] == []
    assert report["automatic_state_promotion_allowed"] is False


@pytest.mark.parametrize(
    ("validator", "snapshot", "blocking"),
    [
        (_validator(sha="old"), _snapshot(), "sha_consistency"),
        (_validator(github_run_id="1"), _snapshot(), "run_consistency"),
        (_validator(repo="other/repo"), _snapshot(), "repository_consistency"),
        (_validator(), _snapshot(branch="dev"), "main_branch_scope"),
        (
            _validator(generated_at_epoch=NOW + 600),
            _snapshot(),
            "temporal_consistency",
        ),
        (
            _validator(generated_at_epoch=NOW),
            _snapshot(generated_at_epoch=NOW - 1),
            "temporal_consistency",
        ),
    ],
)
def test_correlation_and_time_fail_closed(
    validator: dict,
    snapshot: dict,
    blocking: str,
) -> None:
    report = _evaluate(validator, snapshot)

    assert report["ready"] is False
    assert blocking in report["blocking_issues"]


def test_status_propagation_blocks_false_green() -> None:
    report = _evaluate(
        _validator(status="blocked"),
        _snapshot(status="passed"),
    )

    assert report["ready"] is False
    assert "status_propagation" in report["blocking_issues"]


def test_blocked_state_propagates_consistently() -> None:
    report = _evaluate(
        _validator(status="blocked"),
        _snapshot(
            status="blocked",
            critical_evidence="blocked_or_missing",
            dominant_blocker="runtime_smoke",
        ),
    )

    assert report["ready"] is True


def test_invalid_contract_and_json_are_reported(tmp_path: Path) -> None:
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text("{", encoding="utf-8")

    payload, error = load_json_object(invalid_path)
    report = evaluate_consolidators(
        payload,
        _snapshot(contract="wrong"),
        validator_error=error,
        observed_at_epoch=NOW,
    )

    assert report["ready"] is False
    assert "validator_json_integrity" in report["blocking_issues"]
    assert "artifact_contracts" in report["blocking_issues"]


def test_render_markdown_contains_evidence_fields() -> None:
    markdown = render_markdown(_evaluate())

    assert "Estado Único ReqSys" in markdown
    assert "sha_consistency" in markdown
    assert "Production touched" in markdown


def test_main_writes_report_and_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    validator_path = tmp_path / "validator.json"
    snapshot_path = tmp_path / "snapshot.json"
    output_path = tmp_path / "out" / "report.json"
    validator_path.write_text(json.dumps(_validator()), encoding="utf-8")
    snapshot_path.write_text(json.dumps(_snapshot()), encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluate_single_state_consolidators.py",
            "--validator",
            str(validator_path),
            "--snapshot",
            str(snapshot_path),
            "--output",
            str(output_path),
        ],
    )

    assert main() == 0
    assert output_path.exists()
    assert (output_path.parent / "summary.md").exists()


def test_negative_clock_skew_is_rejected() -> None:
    with pytest.raises(ValueError):
        evaluate_consolidators(
            _validator(),
            _snapshot(),
            observed_at_epoch=NOW,
            max_clock_skew_seconds=-1,
        )
