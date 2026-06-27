from pathlib import Path

WORKFLOW = Path('.github/workflows/evidence-maturity-post-workflow.yml')


def read_workflow() -> str:
    return WORKFLOW.read_text(encoding='utf-8')


def test_evidence_maturity_post_workflow_triggers_on_required_workflows():
    text = read_workflow()

    assert 'workflow_run:' in text
    for workflow_name in (
        'CI — ReqSys v2 Enterprise',
        'Operational CI Intelligence',
        'PR Evidence Gate',
    ):
        assert workflow_name in text
    assert 'types:\n      - completed' in text


def test_evidence_maturity_post_workflow_generates_ci_intelligence_inline():
    text = read_workflow()

    assert 'operational_ci_intelligence.py' in text
    assert '--failure-patterns config/failure-patterns.json' in text
    assert 'artifacts/operational-ci-intelligence/operational-ci-intelligence.json' in text


def test_evidence_maturity_post_workflow_passes_sources_to_maturity_snapshot():
    text = read_workflow()

    assert 'delivery_maturity_snapshot.py' in text
    assert '--ci-report artifacts/operational-ci-intelligence/operational-ci-intelligence.json' in text
    assert '--pr-evidence audit/pr-evidence-gate.json' in text
    assert '--head-sha' in text


def test_evidence_maturity_post_workflow_uploads_sha_named_artifact():
    text = read_workflow()

    assert 'name: delivery-maturity-snapshot-${{ steps.sha.outputs.head_sha }}' in text
    assert 'data/delivery-maturity-history/maturity-history.json' in text
    assert 'retention-days: 30' in text
