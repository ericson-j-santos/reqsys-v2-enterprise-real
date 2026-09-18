from scripts import workflow_inventory_decision_gate as gate


def _workflow(path, triggers, recommendation="REMOVER", confidence="baixa"):
    return {
        "path": path,
        "name": path,
        "triggers": triggers,
        "callers": [],
        "recommendation": recommendation,
        "confidence": confidence,
        "requires_human_validation": True,
        "rationale": ["não observado na amostra"],
    }


def test_sample_absence_never_removes_scheduled_workflow():
    item = gate.normalize_decision(_workflow(".github/workflows/a.yml", ["schedule", "workflow_dispatch"]))
    assert item["recommendation"] == "MANTER"
    assert item["requires_human_validation"] is True


def test_manual_low_confidence_candidate_becomes_reusable():
    item = gate.normalize_decision(_workflow(".github/workflows/manual-report.yml", ["workflow_dispatch"]))
    assert item["recommendation"] == "TRANSFORMAR_EM_REUTILIZAVEL"


def test_workflow_run_candidate_becomes_merge_candidate():
    item = gate.normalize_decision(_workflow(".github/workflows/watch.yml", ["workflow_run", "workflow_dispatch"]))
    assert item["recommendation"] == "FUNDIR"


def test_consolidated_operator_is_kept_with_high_confidence():
    item = gate.normalize_decision(_workflow(gate.CONSOLIDATED_OPERATOR, ["schedule", "workflow_dispatch"]))
    assert item["recommendation"] == "MANTER"
    assert item["confidence"] == "alta"
    assert item["requires_human_validation"] is False
