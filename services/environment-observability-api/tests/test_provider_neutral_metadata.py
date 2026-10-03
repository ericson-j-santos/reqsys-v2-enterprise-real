from __future__ import annotations

from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]


def test_runtime_metadata_uses_only_provider_neutral_environment_variables() -> None:
    main_source = (SERVICE_ROOT / "app" / "main.py").read_text(encoding="utf-8")
    bootstrap_source = (SERVICE_ROOT / "sitecustomize.py").read_text(encoding="utf-8")

    assert "FLY_" not in main_source
    assert "FLY_" not in bootstrap_source
    assert 'os.getenv("DEPLOYMENT_ID", "unknown")' in main_source
    assert 'os.getenv("REGION", "unknown")' in main_source
    assert 'os.getenv("INSTANCE_ID", "unknown")' in main_source
    assert 'os.getenv("REGION", "unknown")' in bootstrap_source
    assert 'os.getenv("INSTANCE_ID", "unknown")' in bootstrap_source
