from pathlib import Path

import yaml

WORKFLOWS = (
    Path(".github/workflows/fly-environment-evidence-capture.yml"),
    Path(".github/workflows/fly-environment-promotion-stage.yml"),
    Path(".github/workflows/fly-automatic-environment-promotion.yml"),
)


def test_workflows_are_valid_yaml_mappings() -> None:
    for path in WORKFLOWS:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(payload, dict)
        assert payload.get("name")
        assert payload.get("jobs")
