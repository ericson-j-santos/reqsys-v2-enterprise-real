import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from scripts import desktop_runner_pickup_canary as subject


def test_canary_rejects_wrong_host(tmp_path: Path) -> None:
    with pytest.raises(subject.CanaryError, match="wrong_host"):
        subject.execute(
            confirm=subject.CONFIRM,
            evidence_file=tmp_path / "evidence.json",
            host="OTHER-HOST",
            platform="nt",
        )


def test_canary_requires_exact_runner_and_sha(tmp_path: Path) -> None:
    env = {
        "RUNNER_NAME": subject.TARGET_HOST,
        "GITHUB_REPOSITORY": "ericson-j-santos/reqsys-v2-enterprise-real",
        "GITHUB_SHA": "a" * 40,
    }
    with patch.dict(subject.os.environ, env, clear=False):
        result = subject.execute(
            confirm=subject.CONFIRM,
            evidence_file=tmp_path / "evidence.json",
            host=subject.TARGET_HOST,
            platform="nt",
        )
    assert result["result"] == "DESKTOP_GITHUB_RUNNER_PICKUP_PROVEN"
    assert result["production_touched"] is False
    assert result["secrets_read"] is False


def test_canary_rejects_runner_name_mismatch(tmp_path: Path) -> None:
    with patch.dict(
        subject.os.environ,
        {
            "RUNNER_NAME": "OTHER-RUNNER",
            "GITHUB_REPOSITORY": "ericson-j-santos/reqsys-v2-enterprise-real",
            "GITHUB_SHA": "a" * 40,
        },
        clear=False,
    ):
        with pytest.raises(subject.CanaryError, match="runner_name_mismatch"):
            subject.execute(
                confirm=subject.CONFIRM,
                evidence_file=tmp_path / "evidence.json",
                host=subject.TARGET_HOST,
                platform="nt",
            )


def test_canary_failure_evidence_does_not_leak_exception(tmp_path: Path) -> None:
    evidence = tmp_path / "blocked.json"
    with (
        patch.object(
            subject,
            "execute",
            side_effect=subject.CanaryError("token=must-not-leak"),
        ),
        patch(
            "sys.argv",
            [
                "desktop_runner_pickup_canary.py",
                "--confirm",
                subject.CONFIRM,
                "--evidence-file",
                str(evidence),
            ],
        ),
    ):
        assert subject.main() == 2

    persisted = evidence.read_text(encoding="utf-8")
    assert "must-not-leak" not in persisted
    payload = subject.json.loads(persisted)
    assert payload["error"] == "desktop_runner_pickup_not_proven"


GIB = 1024**3


def test_capacity_snapshot_synthetic_readonly() -> None:
    readers = dict(
        memory_reader=lambda: (16 * GIB, 7 * GIB),
        disk_reader=lambda _path: SimpleNamespace(total=256 * GIB, free=87 * GIB),
        cpu_reader=lambda: 6,
        sql_reader=lambda: 1,
        docker_reader=lambda: True,
        system_drive="C:",
    )
    first = subject.host_capacity(**readers)
    second = subject.host_capacity(**readers)
    assert first == second
    assert first["status"] == "measured"
    assert first["ram_total_gib"] == 16
    assert first["ram_available_gib"] == 7
    assert first["system_disk_free_gib"] == 87
    assert first["logical_cpu_count"] == 6
    assert first["registered_sql_instances"] == 1
    assert first["registered_sql_instances_are_live"] is False
    assert first["docker_daemon_verified"] is False
    assert first["hml_existing_verified"] is False
    assert first["hml_provisioning_authorized"] is False
    assert first["production_touched"] is False
    assert "password" not in str(first).lower()


def test_capacity_rejects_unexpected_drive_without_file_access() -> None:
    disk = Mock()
    with pytest.raises(subject.CanaryError, match="capacity_drive_invalid"):
        subject.host_capacity(system_drive=r"C:\users", disk_reader=disk)
    disk.assert_not_called()


def test_capacity_rejects_inconsistent_numbers() -> None:
    with pytest.raises(subject.CanaryError, match="capacity_metrics_invalid"):
        subject.host_capacity(
            memory_reader=lambda: (8 * GIB, 12 * GIB),
            disk_reader=lambda _path: SimpleNamespace(total=256 * GIB, free=2 * GIB),
            cpu_reader=lambda: 6,
            sql_reader=lambda: 0,
            docker_reader=lambda: False,
            system_drive="C:",
        )


def test_capacity_report_is_not_hml_approval(tmp_path: Path) -> None:
    env = {
        "RUNNER_NAME": subject.TARGET_HOST,
        "GITHUB_REPOSITORY": "ericson-j-santos/reqsys-v2-enterprise-real",
        "GITHUB_SHA": "b" * 40,
    }
    with patch.dict(subject.os.environ, env):
        result = subject.execute(
            confirm=subject.CONFIRM,
            evidence_file=tmp_path / "result.json",
            host=subject.TARGET_HOST,
            platform="nt",
            capacity_probe=lambda: {"status": "measured", "hml_provisioning_authorized": False},
        )
    assert result["ok"] is True
    assert result["capacity"]["hml_provisioning_authorized"] is False
    assert subject.json.loads((tmp_path / "result.json").read_text()) == result


def test_capacity_errors_remain_sanitized_and_non_authorizing(tmp_path: Path) -> None:
    env = {
        "RUNNER_NAME": subject.TARGET_HOST,
        "GITHUB_REPOSITORY": "ericson-j-santos/reqsys-v2-enterprise-real",
        "GITHUB_SHA": "c" * 40,
    }
    with patch.dict(subject.os.environ, env):
        result = subject.execute(
            confirm=subject.CONFIRM,
            evidence_file=tmp_path / "result.json",
            host=subject.TARGET_HOST,
            platform="nt",
            capacity_probe=Mock(side_effect=RuntimeError("secret=never-print-this")),
        )
    raw = (tmp_path / "result.json").read_text()
    assert result["ok"] is True  # Runner picked up; capacity is separately unknown.
    assert result["capacity"] == {
        "status": "unavailable",
        "reason": "capacity_probe_failed",
        "hml_provisioning_authorized": False,
    }
    assert "never-print-this" not in raw


def test_wrong_host_does_not_probe_capacity(tmp_path: Path) -> None:
    probe = Mock()
    with pytest.raises(subject.CanaryError, match="wrong_host"):
        subject.execute(
            confirm=subject.CONFIRM,
            evidence_file=tmp_path / "result.json",
            host="NOT-AN-AUTHORIZED-DESKTOP",
            platform="nt",
            capacity_probe=probe,
        )
    probe.assert_not_called()


def test_runtime_probe_attaches_sanitized_observation(tmp_path: Path) -> None:
    env = {
        "RUNNER_NAME": subject.TARGET_HOST,
        "GITHUB_REPOSITORY": "ericson-j-santos/reqsys-v2-enterprise-real",
        "GITHUB_SHA": "f" * 40,
    }
    probe = Mock(return_value={
        "status": "partial",
        "docker": {"status": "unavailable", "engine_verified": False},
        "hml_provisioning_authorized": False,
        "production_touched": False,
        "secrets_read": False,
    })
    with patch.dict(subject.os.environ, env):
        evidence = subject.execute(
            confirm=subject.CONFIRM,
            evidence_file=tmp_path / "result.json",
            host=subject.TARGET_HOST,
            platform="nt",
            capacity_probe=lambda: {"status": "measured", "hml_provisioning_authorized": False},
            runtime_probe=probe,
        )
    assert probe.call_count == 1
    assert evidence["sql_hml_host_inventory"]["status"] == "partial"
    assert subject.json.loads((tmp_path / "result.json").read_text(encoding="utf-8")) == evidence


def test_runtime_probe_rejects_false_hml_authorization_without_raw_error(tmp_path: Path) -> None:
    env = {
        "RUNNER_NAME": subject.TARGET_HOST,
        "GITHUB_REPOSITORY": "ericson-j-santos/reqsys-v2-enterprise-real",
        "GITHUB_SHA": "f" * 40,
    }
    with patch.dict(subject.os.environ, env):
        evidence = subject.execute(
            confirm=subject.CONFIRM,
            evidence_file=tmp_path / "result.json",
            host=subject.TARGET_HOST,
            platform="nt",
            capacity_probe=lambda: {"status": "measured"},
            runtime_probe=lambda: {
                "status": "measured",
                "hml_provisioning_authorized": True,
                "token": "must-not-leak",
                "production_touched": False,
                "secrets_read": False,
            },
        )
    assert evidence["ok"] is True
    assert evidence["sql_hml_host_inventory"]["status"] == "unavailable"
    assert "must-not-leak" not in (tmp_path / "result.json").read_text(encoding="utf-8")


def test_wrong_host_never_calls_runtime_probe(tmp_path: Path) -> None:
    runtime = Mock()
    with pytest.raises(subject.CanaryError, match="wrong_host"):
        subject.execute(
            confirm=subject.CONFIRM,
            evidence_file=tmp_path / "result.json",
            host="SOME-OTHER-PC",
            platform="nt",
            runtime_probe=runtime,
        )
    runtime.assert_not_called()


def test_runtime_probe_loads_with_isolated_python(tmp_path: Path) -> None:
    """Reproduce the portable Python ._pth layout: script directory absent."""
    isolated_code = """
import importlib.util
import json
import os
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("isolated_desktop_canary", sys.argv[1])
assert spec is not None and spec.loader is not None
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)
os.environ.update({
    "RUNNER_NAME": subject.TARGET_HOST,
    "GITHUB_REPOSITORY": "ericson-j-santos/reqsys-v2-enterprise-real",
    "GITHUB_SHA": "f" * 40,
})
evidence_path = Path(sys.argv[2])
result = subject.execute(
    confirm=subject.CONFIRM,
    evidence_file=evidence_path,
    host=subject.TARGET_HOST,
    platform="nt",
    capacity_probe=lambda: {"status": "measured"},
)
runtime = result["sql_hml_host_inventory"]
assert runtime["status"] in {"measured", "partial", "unavailable"}
assert runtime.get("reason") != "runtime_probe_failed", runtime
assert runtime["hml_provisioning_authorized"] is False
assert runtime["production_touched"] is False
assert runtime["secrets_read"] is False
assert json.loads(evidence_path.read_text(encoding="utf-8")) == result
"""
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            isolated_code,
            str(Path(subject.__file__).resolve()),
            str(tmp_path / "isolated-evidence.json"),
        ],
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr[-800:]


def test_runtime_probe_import_failure_is_sanitized(tmp_path: Path) -> None:
    env = {
        "RUNNER_NAME": subject.TARGET_HOST,
        "GITHUB_REPOSITORY": "ericson-j-santos/reqsys-v2-enterprise-real",
        "GITHUB_SHA": "f" * 40,
    }
    evidence_path = tmp_path / "result.json"
    with (
        patch.dict(subject.os.environ, env),
        patch.object(
            subject,
            "_load_runtime_probe",
            side_effect=OSError("secret=never-print-this"),
        ),
    ):
        result = subject.execute(
            confirm=subject.CONFIRM,
            evidence_file=evidence_path,
            host=subject.TARGET_HOST,
            platform="nt",
            capacity_probe=lambda: {"status": "measured"},
        )
    assert result["sql_hml_host_inventory"]["status"] == "unavailable"
    assert result["sql_hml_host_inventory"]["reason"] == "runtime_probe_failed"
    assert "never-print-this" not in evidence_path.read_text(encoding="utf-8")
