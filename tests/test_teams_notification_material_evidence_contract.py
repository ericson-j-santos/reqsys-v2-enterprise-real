from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTIFIER = (ROOT / ".github/workflows/teams-commit-notification.yml").read_text(encoding="utf-8")
OBSERVER = (ROOT / ".github/workflows/teams-notification-observability.yml").read_text(encoding="utf-8")


def test_notifier_uses_material_source_policy_and_preserves_remediation_filter() -> None:
    assert "triage_decision(source_conclusion, evidence)" in NOTIFIER
    assert "remediation_decision(report)" in NOTIFIER
    assert "no_material_remediation" in NOTIFIER or "remediation_decision" in NOTIFIER
    assert "notification_skipped=true" in NOTIFIER
    assert "suppression_class(skip_reason)" in NOTIFIER
    assert 'skip_class != "material_noop"' in NOTIFIER


def test_notifier_exposes_exclusive_job_step_markers() -> None:
    assert "name: Confirmar entrega real" in NOTIFIER
    assert "if: steps.notify.outputs.delivered == 'true'" in NOTIFIER
    assert "name: Confirmar supressão sem mudança material" in NOTIFIER
    assert "steps.notify.outputs.skip_class == 'material_noop'" in NOTIFIER
    assert "teams-commit-notification-evidence-${{ github.run_id }}" not in NOTIFIER


def test_notifier_uses_strict_route_specific_delivery_contract() -> None:
    assert "delivery_result_decision(delivery_mode, result)" in NOTIFIER
    assert 'bool(result.get("entregue", result.get("success")))' not in NOTIFIER


def test_observer_requires_matching_jobs_api_marker_for_recovery() -> None:
    assert "/actions/runs/{run_id}/jobs?filter=latest&per_page=100" in OBSERVER
    assert "workflow_run_delivery_decision(" in OBSERVER
    assert 'int(run_id), os.environ.get("HEAD_SHA", ""), jobs_payload' in OBSERVER
    assert "actions/download-artifact" not in OBSERVER
    assert "recovery_confirmed" in OBSERVER
    assert "incident_required" in OBSERVER
    assert "observation_unavailable" in OBSERVER
    assert "suppressed" in OBSERVER
    assert "delivery_reason" in OBSERVER
    assert "if: steps.evidence.outputs.incident_required == 'true'" in OBSERVER
    assert "if: steps.evidence.outputs.recovery_confirmed == 'true'" in OBSERVER
    assert "if: steps.evidence.outputs.observation_unavailable == 'true'" in OBSERVER
    assert "&page={page}" in OBSERVER
    assert 'jobs_payload = {"total_count": total_count, "jobs": jobs}' in OBSERVER
    assert "conclusion in {\"success\", \"manual_validation\"}" not in OBSERVER
