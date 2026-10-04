from pathlib import Path

from scripts import validate_action_immutability as gate


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/environment-observability-promotion.yml"
FLYCTL_SHA = "ed8efb33836e8b2096c7fd3ba1c8afe303ebbff1"


def test_environment_observability_workflow_has_only_immutable_external_actions() -> None:
    rel = WORKFLOW.relative_to(ROOT).as_posix()
    assert gate.scan(ROOT, [rel]) == []


def test_flyctl_master_is_pinned_in_all_environment_jobs() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "superfly/flyctl-actions/setup-flyctl@master" not in text
    assert text.count(f"superfly/flyctl-actions/setup-flyctl@{FLYCTL_SHA}") == 3


def test_control_negative_would_reject_master_ref(tmp_path: Path) -> None:
    path = tmp_path / ".github/workflows/negative.yml"
    path.parent.mkdir(parents=True)
    path.write_text(
        "name: negative\non: workflow_dispatch\njobs:\n  test:\n"
        "    runs-on: ubuntu-latest\n    steps:\n"
        "      - uses: superfly/flyctl-actions/setup-flyctl@master\n",
        encoding="utf-8",
    )
    findings = gate.scan(tmp_path, [path.relative_to(tmp_path).as_posix()])
    assert len(findings) == 1
    assert findings[0].reason == "external_action_ref_is_mutable"
