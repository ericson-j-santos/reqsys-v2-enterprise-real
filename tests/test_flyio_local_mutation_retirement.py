"""Garante que caminhos locais nao possam reativar ou mutar Fly.io."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import tomllib

from scripts import configurar_fly_auth_azure
from scripts.credential_control_plane_lifecycle import FlyAdapter, LifecycleError

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "flyio-retirement-policy.json"
MANIFEST_MARKER = "FLYIO_RETIRED_MANIFEST"


def load_policy() -> dict:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def test_retirement_policy_is_permanent_and_all_mutators_are_guarded():
    policy = load_policy()

    assert policy["status"] == "PERMANENTLY_RETIRED"
    assert policy["mutations_allowed"] is False
    assert policy["reactivation_allowed"] is False

    marker = policy["guard_marker"]
    guarded_entries = policy["mutating_entrypoints"]
    guarded = set(guarded_entries)
    read_only = set(policy["read_only_tools"])
    assert guarded.isdisjoint(read_only)
    assert len(guarded_entries) == len(guarded)
    for relative_path in sorted(guarded):
        path = ROOT / relative_path
        assert path.is_file(), relative_path
        prefix = "\n".join(path.read_text(encoding="utf-8").splitlines()[:80])
        assert marker in prefix, relative_path
    for relative_path in sorted(read_only):
        assert (ROOT / relative_path).is_file(), relative_path
    for relative_path in policy["legacy_build_artifacts"]:
        assert (ROOT / relative_path).is_file(), relative_path


def test_legacy_manifests_are_complete_marked_and_still_valid_toml():
    policy = load_policy()
    expected = set(policy["legacy_manifests"])
    discovered = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("fly*.toml")
        if not {"node_modules", ".venv", ".git"}.intersection(path.parts)
    }

    assert discovered == expected
    for relative_path in sorted(expected):
        path = ROOT / relative_path
        text = path.read_text(encoding="utf-8")
        assert MANIFEST_MARKER in "\n".join(text.splitlines()[:3]), relative_path
        assert isinstance(tomllib.loads(text), dict)


def test_fly_lifecycle_credentials_and_environment_manifest_fail_closed():
    lifecycle = json.loads(
        (ROOT / "config" / "control-plane-lifecycle-policy.json").read_text(encoding="utf-8")
    )
    fly_credentials = [
        item for item in lifecycle["managed_credentials"] if item.get("provider") == "fly"
    ]
    non_fly_credentials = [
        item for item in lifecycle["managed_credentials"] if item.get("provider") != "fly"
    ]
    assert fly_credentials
    assert all(item.get("enabled") is False for item in fly_credentials)
    assert non_fly_credentials
    assert all(item.get("enabled") is True for item in non_fly_credentials)

    environments = json.loads(
        (ROOT / "infra" / "fly-environments.json").read_text(encoding="utf-8")
    )
    retirement = environments["retirement"]
    assert retirement["status"] == "PERMANENTLY_RETIRED"
    assert retirement["mutations_allowed"] is False
    assert retirement["reactivation_allowed"] is False


def test_python_mutation_adapters_refuse_before_invoking_provider():
    with pytest.raises(configurar_fly_auth_azure.ConfigError, match="retirado definitivamente"):
        configurar_fly_auth_azure.aplicar_fly(None, None)

    adapter = FlyAdapter()
    with pytest.raises(LifecycleError, match="retirado definitivamente"):
        adapter.create_deploy_token(
            app="reqsys-api-dev",
            issuer_token="unused",
            name="unused",
            expires_in_days=1,
        )
    with pytest.raises(LifecycleError, match="retirado definitivamente"):
        adapter.revoke(token_id="unused", issuer_token="unused")


def test_cutover_real_is_refused_before_cli_resolution_or_side_effects():
    text = (ROOT / "scripts" / "cutover_fly_postgres.py").read_text(encoding="utf-8")
    main = text.split("def main() -> int:", 1)[1]

    guard = main.index("if not args.dry_run:")
    cli_resolution = main.index("fly = _fly_bin()")
    assert guard < cli_resolution
    assert "return 78" in main[guard:cli_resolution]

    for function_name in ("passo_5_setar_secret", "passo_6_deploy_e_verificar", "rollback"):
        function = text.split(f"def {function_name}", 1)[1].split("\ndef ", 1)[0]
        assert "FLYIO_RETIREMENT_GUARD" in function


@pytest.mark.parametrize(
    "relative_path",
    [
        "scripts/rollback_environment_observability_api.sh",
        "scripts/run_reqsys_free_tier_backup.sh",
    ],
)
def test_shell_mutators_exit_before_reading_inputs(relative_path):
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash indisponivel")

    result = subprocess.run(
        [bash, relative_path],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 78
    assert "retirado definitivamente" in result.stderr


@pytest.mark.parametrize(
    ("relative_path", "arguments"),
    [
        ("scripts/fly-deploy.ps1", []),
        ("scripts/configurar-redmine.ps1", ["-ApiKey", "unused", "-ProjectId", "1"]),
        ("scripts/setup-ocr-gitlab-ci-automatic.ps1", []),
        ("scripts/setup-ocr-gitlab-ci-vars.ps1", []),
        ("scripts/configure-ocr-gitlab-ci-variables.ps1", []),
        ("scripts/setup-ocr-gitlab-variables.ps1", []),
    ],
)
def test_powershell_mutators_throw_before_provider_access(relative_path, arguments):
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if powershell is None:
        pytest.skip("PowerShell indisponivel")

    result = subprocess.run(
        [powershell, "-NoProfile", "-File", relative_path, *arguments],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "retirado definitivamente" in result.stderr
