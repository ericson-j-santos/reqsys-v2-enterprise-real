from __future__ import annotations

import sys
from pathlib import Path

import pytest

from scripts import (
    check_fly_secret_strength,
    configurar_fly_auth_azure,
    cutover_fly_postgres,
)

ROOT = Path(__file__).resolve().parents[1]


def test_remote_secret_check_refuses_without_starting_flyctl():
    with pytest.raises(RuntimeError, match="retirado definitivamente"):
        check_fly_secret_strength.executar(
            "reqsys-api",
            [check_fly_secret_strength.SecretCheck("JWT_SECRET", 32)],
        )
    assert check_fly_secret_strength.main() == 78


def test_auth_secret_mutator_cli_refuses_before_credentials_or_network():
    assert configurar_fly_auth_azure.main() == 78
    with pytest.raises(configurar_fly_auth_azure.ConfigError, match="retirado definitivamente"):
        configurar_fly_auth_azure.aplicar_fly(None, None)


def test_cutover_refuses_real_and_dry_run(monkeypatch):
    required = [
        "cutover_fly_postgres.py",
        "--app",
        "reqsys-api-dev",
        "--fly-config",
        "backend/fly.dev.toml",
        "--postgres-url",
        "postgresql://redacted",
    ]
    monkeypatch.setattr(sys, "argv", required)
    assert cutover_fly_postgres.main() == 78

    monkeypatch.setattr(sys, "argv", [*required, "--dry-run"])
    assert cutover_fly_postgres.main() == 78


def test_legacy_build_and_boot_artifacts_are_absent():
    for relative_path in (
        "Dockerfile.fly",
        "backend/Dockerfile.fly",
        "backend/fly_boot.sh",
        "scripts/fly_boot.sh",
    ):
        assert not (ROOT / relative_path).exists(), relative_path
