from __future__ import annotations

import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEVSECOPS_CI = ROOT / "gitlab" / "ci" / "devsecops.yml"
GITLEAKS_CONFIG = ROOT / ".gitleaks.toml"


def test_scanner_images_are_immutable_and_trivy_receives_one_target() -> None:
    content = DEVSECOPS_CI.read_text(encoding="utf-8")

    assert "zricethezav/gitleaks:v8.30.1@sha256:" in content
    assert "aquasec/trivy:0.74.0@sha256:" in content
    assert "--output audit/gitlab-trivy-report.json ." in content
    assert "--severity HIGH,CRITICAL ." in content
    assert "backend frontend" not in content


def test_gitleaks_uses_default_rules_and_narrow_synthetic_allowlist() -> None:
    pipeline = DEVSECOPS_CI.read_text(encoding="utf-8")
    config = tomllib.loads(GITLEAKS_CONFIG.read_text(encoding="utf-8"))

    assert "--config .gitleaks.toml" in pipeline
    assert config["extend"]["useDefault"] is True

    allowlists = config["allowlists"]
    assert len(allowlists) == 1
    allowlist = allowlists[0]
    assert allowlist["targetRules"] == ["generic-api-key"]
    assert "paths" not in allowlist
    assert set(allowlist["regexes"]) == {
        "ci-placeholder-secret-min-32-chars-long",
        "abc123segredo",
        "SEGREDO-UNICO-NAO-DEVE-VAZAR-9f8e7d",
        "OUTRO-MARCADOR-SECRETO-XYZ123",
    }
