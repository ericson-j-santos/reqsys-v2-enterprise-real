from pathlib import Path


def test_capture_never_persists_secret_values() -> None:
    script = Path("scripts/capture_fly_environment_state.py").read_text(encoding="utf-8")
    workflow = Path(".github/workflows/fly-environment-evidence-capture.yml").read_text(
        encoding="utf-8"
    )
    assert '"secret_values_persisted": False' in script
    assert "Digest" not in script
    assert "FLY_API_TOKEN" in workflow
    assert "secret_values_persisted" not in workflow
