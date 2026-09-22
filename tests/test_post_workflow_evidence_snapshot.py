from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.post_workflow_evidence_snapshot import build_snapshot, compute_maturity_score


def test_compute_maturity_score_from_pipeline_and_runtime():
    sources = {
        "pipeline_governance": {"estadoGeral": "verde"},
        "runtime_health": {"maturity_percent": 80},
        "ci_intelligence": {"operational_score": 70},
    }
    score = compute_maturity_score(sources)
    assert score == 81.67


def test_build_snapshot_flags_blocked_pipeline():
    sources = {
        "pipeline_governance": {"estadoGeral": "bloqueado"},
        "runtime_health": None,
        "ci_intelligence": None,
        "delivery_maturity": None,
        "coordenador_status": None,
    }
    snapshot = build_snapshot(sources, "pull_request", "abc")
    assert snapshot["blocked_for_promotion"] is True
    assert snapshot["pipeline_estado_geral"] == "bloqueado"


def test_main_returns_zero_even_when_blocked(monkeypatch):
    from scripts import post_workflow_evidence_snapshot as module

    monkeypatch.setattr(
        module,
        "build_snapshot",
        lambda *args, **kwargs: {"blocked_for_promotion": True, "recommended_actions": []},
    )
    monkeypatch.setattr(module, "render_markdown", lambda snapshot: "report")
    monkeypatch.setattr(
        module.argparse.ArgumentParser,
        "parse_args",
        lambda self: module.argparse.Namespace(
            out_dir=Path("/tmp/post-workflow-evidence-test"),
            event="ci",
            sha="abc",
            pipeline_report=Path("/tmp/pipeline-missing.json"),
            workflow_run_id=None,
            correlation_id=None,
        ),
    )
    assert module.main() == 0
