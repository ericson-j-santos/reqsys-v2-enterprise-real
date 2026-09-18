from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path("scripts/pc24x7_cofre_runtime_control.py")
SPEC = importlib.util.spec_from_file_location("pc24x7_cofre_runtime_control", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def _inspect_payload(sha: str, health: str = "healthy") -> str:
    return json.dumps([
        {
            "Config": {
                "Labels": {
                    "com.docker.compose.project": module.PROJECT,
                    "com.docker.compose.service": module.SERVICE,
                },
                "Env": [f"GITHUB_SHA={sha}"],
            },
            "Mounts": [
                {"Destination": module.SECRET_TARGET, "RW": False, "Type": "bind"},
                {"Destination": module.DATA_TARGET, "RW": True, "Type": "volume"},
            ],
            "State": {"Status": "running", "Health": {"Status": health}},
        }
    ])


def test_inspect_accepts_exact_dev_runtime(monkeypatch):
    sha = "a" * 40
    monkeypatch.setattr(
        module,
        "run_docker",
        lambda args, timeout=120: subprocess.CompletedProcess(
            ["docker", *args], 0, stdout=_inspect_payload(sha), stderr=""
        ),
    )

    result = module.inspect_container(sha)

    assert result["runtime_sha"] == sha
    assert result["secret_mount_read_only"] is True
    assert result["data_volume_persistent"] is True
    assert result["production_touched"] is False


def test_inspect_rejects_runtime_sha_mismatch(monkeypatch):
    monkeypatch.setattr(
        module,
        "run_docker",
        lambda args, timeout=120: subprocess.CompletedProcess(
            ["docker", *args], 0, stdout=_inspect_payload("b" * 40), stderr=""
        ),
    )

    with pytest.raises(module.RuntimeControlError, match="runtime_sha_mismatch"):
        module.inspect_container("a" * 40)


def test_restart_uses_only_exact_container(monkeypatch, tmp_path):
    sha = "c" * 40
    calls = []

    def fake_run(args, timeout=120):
        calls.append(args)
        if args[0] == "restart":
            return subprocess.CompletedProcess(["docker", *args], 0, stdout=module.CONTAINER, stderr="")
        return subprocess.CompletedProcess(["docker", *args], 0, stdout=_inspect_payload(sha), stderr="")

    monkeypatch.setattr(module, "run_docker", fake_run)
    monkeypatch.setattr(sys, "argv", [
        str(SCRIPT),
        "restart",
        "--expected-sha", sha,
        "--correlation-id", "corr-test",
        "--evidence-file", str(tmp_path / "evidence.json"),
    ])

    assert module.main() == 0
    assert ["restart", module.CONTAINER] in calls
    payload = json.loads((tmp_path / "evidence.json").read_text(encoding="utf-8"))
    assert payload["restart_performed"] is True
    assert payload["sensitive_values_exposed"] is False
