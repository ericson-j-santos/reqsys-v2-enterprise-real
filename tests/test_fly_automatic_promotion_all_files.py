from pathlib import Path


REQUIRED = (
    ".github/workflows/fly-environment-evidence-capture.yml",
    ".github/workflows/fly-environment-promotion-stage.yml",
    ".github/workflows/fly-automatic-environment-promotion.yml",
    "scripts/capture_fly_environment_state.py",
    "scripts/evaluate_environment_promotion_capture.py",
    "docs/contracts/fly-automatic-environment-promotion.md",
)


def test_required_automatic_promotion_files_exist() -> None:
    missing = [path for path in REQUIRED if not Path(path).is_file()]
    assert missing == []
