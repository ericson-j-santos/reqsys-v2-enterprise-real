from __future__ import annotations

import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
import sys

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.governed_pr_increment_gate import (  # noqa: E402
    evaluate_pr_increment_gate,
    infer_increment_from_pr,
    main as governed_gate_main,
)
from scripts.coordenador_status_consolidator import consolidate  # noqa: E402
from tests.test_coordenador_status_consolidator import (  # noqa: E402
    health_fixture,
    orchestrator_fixture,
    watchdog_fixture,
)

WORKFLOW = Path(".github/workflows/governed-pr-automation.yml")


def read_workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_infer_increment_from_label() -> None:
    inferred = infer_increment_from_pr(labels=["increment:gap_fix"])
    assert inferred["increment_type"] == "gap_fix"
    assert inferred["inference_source"] == "label:increment:gap_fix"


def test_infer_increment_from_body_ops_gap() -> None:
    inferred = infer_increment_from_pr(
        body="increment-type: gap_fix\nReferencia OPS-GAP-999",
    )
    assert inferred["increment_type"] == "gap_fix"
    assert inferred["reference"] == "OPS-GAP-999"


def test_infer_increment_defaults_to_new_front() -> None:
    inferred = infer_increment_from_pr(title="feat: nova funcionalidade", head_ref="cursor/nova-feature-5f23")
    assert inferred["increment_type"] == "new_front"
    assert inferred["inference_source"] == "default:new_front"


def test_infer_increment_hotfix_from_branch() -> None:
    inferred = infer_increment_from_pr(head_ref="hotfix/auth-token", title="fix token")
    assert inferred["increment_type"] == "hotfix"


def test_evaluate_pr_increment_gate_blocks_new_front_when_red() -> None:
    report = consolidate("owner/repo", "main", orchestrator_fixture("red"), health_fixture("red"))
    result = evaluate_pr_increment_gate(report, title="feat: nova frente")
    assert result["allowed"] is False
    assert result["increment_type"] == "new_front"
    assert result["new_front_allowed"] is False


def test_evaluate_pr_increment_gate_allows_gap_fix_with_reference() -> None:
    report = consolidate("owner/repo", "main", orchestrator_fixture("red"), health_fixture("red"))
    result = evaluate_pr_increment_gate(
        report,
        labels=["increment:gap_fix"],
        body="OPS-GAP-999",
    )
    assert result["allowed"] is True
    assert result["increment_type"] == "gap_fix"


def test_evaluate_pr_increment_gate_allows_close_duplicate() -> None:
    report = consolidate(
        "owner/repo",
        "main",
        orchestrator_fixture("green"),
        health_fixture("green"),
        watchdog_fixture(duplicates=True),
    )
    result = evaluate_pr_increment_gate(
        report,
        labels=["increment:close_duplicate"],
        body="Fecha PR #10 duplicado",
    )
    assert result["allowed"] is True
    assert result["increment_type"] == "close_duplicate"


def test_governed_gate_cli_with_status_json(tmp_path: Path) -> None:
    report = consolidate("owner/repo", "main", orchestrator_fixture("green"), health_fixture("green"))
    status_path = tmp_path / "coordenador-status.json"
    status_path.write_text(json.dumps(report), encoding="utf-8")
    output_dir = tmp_path / "out"

    exit_code = governed_gate_main(
        [
            "--title",
            "feat: ok",
            "--status-json",
            str(status_path),
            "--output-dir",
            str(output_dir),
            "--json",
        ]
    )
    assert exit_code == 0
    payload = json.loads((output_dir / "governed-pr-increment-gate.json").read_text(encoding="utf-8"))
    assert payload["allowed"] is True


def test_governed_pr_automation_triggers_on_pull_request_open() -> None:
    text = read_workflow()
    assert "pull_request:" in text
    assert "opened" in text
    assert "reopened" in text
    assert "ready_for_review" in text
    assert "labeled" in text


def test_governed_pr_automation_has_increment_gate_job() -> None:
    text = read_workflow()
    assert "increment-gate-on-open:" in text
    assert "governed_pr_increment_gate.py" in text
    assert "coordenador_status_consolidator.py" in text
    assert "governed-pr-increment-gate-evidence" in text


def test_governed_pr_automation_merge_job_checks_increment_gate() -> None:
    text = read_workflow()
    assert "Validar increment gate do PR (merge path)" in text
    assert "if: github.event_name == 'workflow_dispatch'" in text
