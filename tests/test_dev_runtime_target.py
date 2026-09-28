from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts import dev_runtime_target as target


def test_validate_runtime_base_accepts_only_quick_tunnel():
    assert (
        target.validate_runtime_base("https://safe-example.trycloudflare.com/")
        == "https://safe-example.trycloudflare.com"
    )
    for value in (
        "https://reqsys-app-dev.fly.dev",
        "https://reqsys-api-dev.fly.dev",
        "http://safe-example.trycloudflare.com",
        "https://user@safe-example.trycloudflare.com",
        "https://safe-example.trycloudflare.com:8443",
        "https://example.invalid",
    ):
        with pytest.raises(target.DevRuntimeResolutionError):
            target.validate_runtime_base(value)


def test_resolve_signed_runtime_requires_verified_contract(tmp_path: Path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "resolve_pc24x7_dev_locator.mjs").write_text("// test", encoding="utf-8")

    def run_fn(command, **kwargs):
        output = Path(command[command.index("--output") + 1])
        output.write_text(
            json.dumps(
                {
                    "contract": "reqsys-pc24x7-dev-signed-locator-resolution",
                    "environment": "dev",
                    "selected_url": "https://current-dev.trycloudflare.com",
                    "signature_verified": True,
                    "locator_transport": "ntfy_signed_ed25519",
                    "runtime_contract": {
                        "version": "2.0.0",
                        "required_endpoints": [
                            "/api/health",
                            "/api/runtime/health",
                            "/api/runtime/readiness",
                            "/api/runtime/build-info",
                        ],
                    },
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    result = target.resolve_signed_dev_runtime(repo_root=tmp_path, run_fn=run_fn)
    assert result["base_url"] == "https://current-dev.trycloudflare.com"
    assert result["signature_verified"] is True


def test_same_origin_targets_never_use_fly():
    targets = target.build_dev_targets("https://current-dev.trycloudflare.com")
    assert targets["health"].endswith("/api/health")
    assert targets["auth_config"].endswith("/api/v1/auth/config")
    assert all(".fly.dev" not in value for value in targets.values())
