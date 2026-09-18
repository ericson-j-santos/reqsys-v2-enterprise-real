import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "resolve_managed_credential.py"
spec = importlib.util.spec_from_file_location("resolver", MODULE_PATH)
resolver = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = resolver
spec.loader.exec_module(resolver)


def policy():
    return {
        "contract": "reqsys-credential-control-plane-lifecycle",
        "execution": {
            "secret_store": {
                "provider": "azure_key_vault",
                "allow_github_secret_fallback": False,
            }
        },
        "managed_credentials": [
            {
                "credential_id": "fly-api-prod-deploy",
                "provider": "fly",
                "secret_name": "reqsys-fly-api-prod-deploy-token",
                "enabled": True,
                "consumers": ["github-actions:fly-production"],
            }
        ],
    }


def test_selects_only_authorized_consumer():
    item = resolver.select_credential(policy(), "fly-api-prod-deploy", "github-actions:fly-production")
    assert item["secret_name"] == "reqsys-fly-api-prod-deploy-token"


def test_rejects_wrong_consumer():
    with pytest.raises(resolver.ResolutionError, match="Consumer não autorizado"):
        resolver.select_credential(policy(), "fly-api-prod-deploy", "github-actions:fly-staging")


def test_rejects_policy_with_github_secret_fallback(tmp_path):
    data = policy()
    data["execution"]["secret_store"]["allow_github_secret_fallback"] = True
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(resolver.ResolutionError, match="sem fallback"):
        resolver.load_policy(path)


def test_rejects_expired_secret():
    metadata = resolver.SecretMetadata(
        enabled=True,
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    with pytest.raises(resolver.ResolutionError, match="expirada"):
        resolver.validate_metadata(metadata, now=datetime.now(timezone.utc))


def test_exports_without_logging_plain_value(tmp_path, capsys):
    github_env = tmp_path / "github-env"
    resolver.export_to_github_env("FLY_API_TOKEN", "super-secret-value", github_env)
    assert github_env.read_text(encoding="utf-8") == "FLY_API_TOKEN=super-secret-value\n"
    assert "::add-mask::super-secret-value" in capsys.readouterr().out


def test_rejects_invalid_export_name(tmp_path):
    with pytest.raises(resolver.ResolutionError, match="inválido"):
        resolver.export_to_github_env("bad-name", "x", tmp_path / "env")
