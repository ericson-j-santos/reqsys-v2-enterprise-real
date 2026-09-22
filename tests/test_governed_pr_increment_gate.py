from __future__ import annotations

import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
import sys

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.governed_pr_increment_gate import (  # noqa: E402
    evaluate_pr_increment_gate,
    fetch_live_pr_context,
    infer_increment_from_pr,
    main as governed_gate_main,
)
from scripts import coordenador_status_consolidator as consolidator  # noqa: E402
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


def test_infer_increment_state_gap_from_maturity_pr_title() -> None:
    inferred = infer_increment_from_pr(
        title="feat: elevar maturidade BDD e conclusão para nível adequado (>=80%)",
        head_ref="cursor/maturidade-adequado-80-8c6a",
    )
    assert inferred["increment_type"] == "gap_fix"
    assert inferred["inference_source"] == "heuristic:state_gap"


def test_infer_increment_ops_environments_as_hotfix() -> None:
    inferred = infer_increment_from_pr(
        title="feat: validate readiness for all environments",
        head_ref="cursor/environments-readiness-f247",
    )
    assert inferred["increment_type"] == "hotfix"
    assert inferred["inference_source"] == "heuristic:ops_evidence"


def test_infer_increment_ops_dashboard_as_hotfix() -> None:
    inferred = infer_increment_from_pr(
        title="feat: render environments validation dashboard",
        head_ref="cursor/environments-dashboard-f247",
    )
    assert inferred["increment_type"] == "hotfix"
    assert inferred["inference_source"] == "heuristic:ops_evidence"


def test_infer_increment_hotfix_from_branch() -> None:
    inferred = infer_increment_from_pr(head_ref="hotfix/auth-token", title="fix token")
    assert inferred["increment_type"] == "hotfix"


def test_infer_increment_fly_demo_login_as_hotfix() -> None:
    inferred = infer_increment_from_pr(
        title="fix(ops): garantir ALLOW_DEMO_LOGIN=true no deploy automático de dev",
        head_ref="cursor/fly-dev-demo-login-7df8",
    )
    assert inferred["increment_type"] == "hotfix"
    assert inferred["reference"] == "OPS-GAP-FLY-DEMO-LOGIN"
    assert inferred["inference_source"] == "heuristic:fly_ops"


def test_evaluate_pr_increment_gate_allows_fly_demo_login_hotfix() -> None:
    report = consolidate("owner/repo", "main", orchestrator_fixture("yellow"), health_fixture("green"))
    result = evaluate_pr_increment_gate(
        report,
        title="fix(ops): garantir ALLOW_DEMO_LOGIN=true no deploy automático de dev",
        head_ref="cursor/fly-dev-demo-login-7df8",
    )
    assert result["allowed"] is True
    assert result["increment_type"] == "hotfix"
    assert result["reference"] == "OPS-GAP-FLY-DEMO-LOGIN"


def test_evaluate_pr_increment_gate_allows_ops_hotfix_when_yellow() -> None:
    report = consolidate("owner/repo", "main", orchestrator_fixture("yellow"), health_fixture("green"))
    result = evaluate_pr_increment_gate(
        report,
        title="feat: validate readiness for all environments",
        head_ref="cursor/environments-readiness-f247",
    )
    assert result["allowed"] is True
    assert result["increment_type"] == "hotfix"
    assert result["inference"]["inference_source"] == "heuristic:ops_evidence"


def test_evaluate_pr_increment_gate_requires_reference_for_inferred_state_gap(monkeypatch) -> None:
    """Sem gap ativo no backlog, um gap_fix inferido e sem referencia deve bloquear.

    O backlog documentado e dado vivo do repositorio; sem isolamento este teste
    passava a verde/vermelho conforme gaps eram abertos ou resolvidos.
    """
    monkeypatch.setattr(consolidator, "_documented_gap_ids", lambda include_resolved=False: set())
    report = consolidate("owner/repo", "main", orchestrator_fixture("yellow"), health_fixture("green"))
    report["automatic_backlog"] = []
    result = evaluate_pr_increment_gate(
        report,
        title="feat: elevar maturidade BDD e conclusão para nível adequado (>=80%)",
        head_ref="cursor/maturidade-adequado-80-8c6a",
    )
    assert result["allowed"] is False
    assert result["reason"] == "gap_fix_sem_referencia"
    assert result["increment_type"] == "gap_fix"
    assert result["inference"]["inference_source"] == "heuristic:state_gap"


def test_evaluate_pr_increment_gate_allows_generic_gap_fix_when_backlog_has_gaps(monkeypatch) -> None:
    """Com gap ativo, o gap_fix sem referencia e permitido porem sinalizado."""
    monkeypatch.setattr(
        consolidator,
        "_documented_gap_ids",
        lambda include_resolved=False: {"OPS-GAP-1677"},
    )
    report = consolidate("owner/repo", "main", orchestrator_fixture("yellow"), health_fixture("green"))
    result = evaluate_pr_increment_gate(
        report,
        title="feat: elevar maturidade BDD e conclusão para nível adequado (>=80%)",
        head_ref="cursor/maturidade-adequado-80-8c6a",
    )
    assert result["allowed"] is True
    assert result["reason"] == "gap_fix_generico"
    assert "OPS-GAP-1677" in result["detail"]


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


def test_pr_opened_with_empty_body_regresses_to_new_front() -> None:
    """Regressao observada no PR #1831: body/label aplicados apos a abertura."""
    inferred = infer_increment_from_pr(
        title="fix(cofre): tolerate CRLF legacy and fail closed on decrypt errors",
        body="",
        labels=[],
        head_ref="fix/cofre-crlf-fail-closed-20260919",
    )
    assert inferred["increment_type"] == "new_front"
    assert inferred["inference_source"] == "default:new_front"


def test_fetch_live_pr_context_normalizes_payload() -> None:
    captured: list[str] = []

    def fake_fetcher(url: str) -> dict:
        captured.append(url)
        return {
            "number": 1831,
            "title": "fix(cofre): tolerate CRLF legacy and fail closed on decrypt errors",
            "body": "increment-type: gap_fix\n\n## Objetivo",
            "labels": [{"name": "increment:gap_fix"}, {"name": ""}],
            "head": {"ref": "fix/cofre-crlf-fail-closed-20260919"},
        }

    context = fetch_live_pr_context("owner/repo", 1831, "token", fetcher=fake_fetcher)
    assert captured == ["https://api.github.com/repos/owner/repo/pulls/1831"]
    assert context["labels"] == ["increment:gap_fix"]
    assert context["head_ref"] == "fix/cofre-crlf-fail-closed-20260919"
    assert context["number"] == 1831

    inferred = infer_increment_from_pr(
        title=context["title"],
        body=context["body"],
        labels=context["labels"],
        head_ref=context["head_ref"],
    )
    assert inferred["increment_type"] == "gap_fix"
    assert inferred["inference_source"] == "label:increment:gap_fix"


def test_fetch_live_pr_context_tolerates_null_body_and_labels() -> None:
    context = fetch_live_pr_context(
        "owner/repo",
        7,
        "token",
        fetcher=lambda _url: {"number": 7, "title": "t", "body": None, "labels": None, "head": None},
    )
    assert context["body"] == ""
    assert context["labels"] == []
    assert context["head_ref"] == ""


def test_evaluate_pr_increment_gate_records_pr_context_source() -> None:
    report = {
        "state": "state_yellow",
        "increment_gate": {
            "new_front_allowed": False,
            "blockers": ["state_yellow"],
            "allowed_increment_types": ["gap_fix", "hotfix", "consolidate"],
        },
        "recommended_actions": [],
    }
    payload = evaluate_pr_increment_gate(
        report,
        labels=["increment:gap_fix"],
        pr_number=1831,
        pr_context_source="live_api",
    )
    assert payload["increment_type"] == "gap_fix"
    assert payload["pr_context_source"] == "live_api"
    assert payload["allowed"] is True


def test_evaluate_pr_increment_gate_defaults_context_source_to_event_payload() -> None:
    report = {
        "state": "state_yellow",
        "increment_gate": {
            "new_front_allowed": False,
            "blockers": ["state_yellow"],
            "allowed_increment_types": ["gap_fix", "hotfix", "consolidate"],
        },
        "recommended_actions": [],
    }
    payload = evaluate_pr_increment_gate(report, labels=["increment:gap_fix"], pr_number=1831)
    assert payload["pr_context_source"] == "event_payload"


def test_governed_pr_automation_open_path_refreshes_pr_context() -> None:
    text = read_workflow()
    assert "--refresh-pr" in text
    assert "pr_context_source" in text
