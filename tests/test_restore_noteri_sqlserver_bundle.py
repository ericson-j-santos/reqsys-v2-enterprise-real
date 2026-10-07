"""Pure tests for the fail-closed NOTERI SQL Server restore contract."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import restore_noteri_sqlserver_bundle as restore


def manifest() -> dict:
    files = []
    for database in sorted(restore.EXPECTED_DATABASES, key=str.casefold):
        payload = database.encode("utf-8")
        files.append(
            {
                "name": f"{database}.bak",
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    return {
        "schema": restore.MANIFEST_SCHEMA,
        "source_host": restore.SOURCE_HOST,
        "created_at_local": "2026-10-07T07:15:03-03:00",
        "backup_options": ["COPY_ONLY", "CHECKSUM"],
        "restore_verifyonly": True,
        "database_count": 17,
        "files": files,
    }


def test_manifest_selects_exactly_fourteen_user_databases():
    entries = restore.parse_manifest(manifest())
    selected = restore.select_user_databases([entry["database"] for entry in entries])

    assert len(entries) == 17
    assert len(selected) == 14
    assert set(selected) == restore.USER_DATABASES
    assert not set(selected) & restore.SYSTEM_DATABASES


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("schema", "wrong", "invalid_manifest_schema"),
        ("source_host", "OTHER", "invalid_manifest_source"),
        (
            "created_at_local",
            "2026-10-07T07:15:04-03:00",
            "invalid_manifest_creation_time",
        ),
        ("database_count", 16, "invalid_manifest_verification"),
        ("restore_verifyonly", False, "invalid_manifest_verification"),
    ],
)
def test_manifest_binding_is_fail_closed(field, value, code):
    candidate = manifest()
    candidate[field] = value

    with pytest.raises(restore.RestoreError, match=code):
        restore.parse_manifest(candidate)


def test_manifest_rejects_unknown_database_even_with_valid_hash():
    candidate = manifest()
    candidate["files"][0]["name"] = "unexpected.bak"

    with pytest.raises(restore.RestoreError, match="unexpected_database_inventory"):
        restore.parse_manifest(candidate)


def test_verify_bundle_checks_all_seventeen_hashes(tmp_path):
    candidate = manifest()
    (tmp_path / "manifest.json").write_text(json.dumps(candidate), encoding="utf-8")
    for entry in candidate["files"]:
        (tmp_path / entry["name"]).write_bytes(Path(entry["name"]).stem.encode("utf-8"))

    verified = restore.verify_bundle(tmp_path)

    assert len(verified) == 17


def test_verify_bundle_rejects_digest_mismatch(tmp_path):
    candidate = manifest()
    (tmp_path / "manifest.json").write_text(json.dumps(candidate), encoding="utf-8")
    for entry in candidate["files"]:
        payload = Path(entry["name"]).stem.encode("utf-8")
        (tmp_path / entry["name"]).write_bytes(payload)
    (tmp_path / candidate["files"][0]["name"]).write_bytes(b"tampered")

    with pytest.raises(restore.RestoreError, match="backup_file_metadata_mismatch"):
        restore.verify_bundle(tmp_path)


def test_sql_escaping_is_deterministic():
    assert restore.sql_string("O'Brien") == "N'O''Brien'"
    assert restore.sql_identifier("name]part") == "[name]]part]"


def test_filelist_parsing_and_safe_move_targets():
    columns = ["ReqSysData", "C:/old/reqsys.mdf", "D"] + [""] * 19
    log_columns = ["ReqSysLog", "C:/old/reqsys.ldf", "L"] + [""] * 19

    parsed = restore.parse_filelistonly(["|".join(columns), "|".join(log_columns)])
    targets = restore.safe_move_targets("ReqSysMovimentoDev", parsed)

    assert targets == [
        ("ReqSysData", "/var/opt/mssql/data/noteri_reqsysmovimentodev_1.mdf"),
        ("ReqSysLog", "/var/opt/mssql/data/noteri_reqsysmovimentodev_1.ldf"),
    ]


def test_filelist_rejects_unexpected_type_and_shape():
    bad_type = ["Data", "C:/old/data", "S"] + [""] * 19
    with pytest.raises(restore.RestoreError, match="unexpected_filelistonly_output"):
        restore.parse_filelistonly(["|".join(bad_type)])
    with pytest.raises(restore.RestoreError, match="unexpected_filelistonly_output"):
        restore.parse_filelistonly(["Data|too|short"])


def test_password_never_appears_in_confirmation_failure(capsys):
    secret = "Strong-Example-Password-123!"
    exit_code = restore.main(["--confirm", "WRONG"])
    output = capsys.readouterr().out

    assert exit_code == 1
    assert secret not in output
    assert json.loads(output) == {"ok": False, "code": "fixed_confirmation_required"}


@pytest.mark.parametrize(
    ("kind", "expected_arguments"),
    [
        (
            "container",
            [
                "container",
                "ls",
                "--all",
                "--filter",
                f"name=^{restore.CONTAINER_NAME}$",
                "--format",
                "{{.Names}}",
            ],
        ),
        (
            "volume",
            [
                "volume",
                "ls",
                "--filter",
                f"name=^{restore.VOLUME_NAME}$",
                "--format",
                "{{.Name}}",
            ],
        ),
    ],
)
def test_absent_resource_inventory_uses_kind_specific_format(
    monkeypatch, kind, expected_arguments
):
    calls = []

    def fake_docker(arguments, **kwargs):
        calls.append((arguments, kwargs))
        return subprocess.CompletedProcess(
            ["docker", *arguments], 1 if "inspect" in arguments else 0, "", ""
        )

    monkeypatch.setattr(restore, "_docker", fake_docker)

    assert (
        restore.inspect_named(
            kind,
            restore.CONTAINER_NAME if kind == "container" else restore.VOLUME_NAME,
        )
        is None
    )
    assert calls[1][0] == expected_arguments


def test_resource_inventory_rejects_unknown_kind():
    with pytest.raises(restore.RestoreError, match="unsupported_docker_resource_kind"):
        restore.inspect_named("network", "unexpected")


@pytest.mark.skipif(os.name != "nt", reason="Docker Desktop Windows path mapping")
def test_same_path_accepts_only_exact_docker_desktop_bind_mapping(tmp_path):
    expected = tmp_path.resolve()
    drive, tail = os.path.splitdrive(str(expected))
    mapped = (
        f"/run/desktop/mnt/host/{drive[0].casefold()}/"
        f"{tail.replace(chr(92), '/').lstrip('/')}"
    )

    assert restore._same_path(mapped, expected)
    assert restore._same_path(str(expected), expected)
    assert not restore._same_path(mapped + "-other", expected)


def test_sqlcmd_streams_batch_without_command_line_query(monkeypatch):
    observed = {}

    def fake_docker(arguments, **kwargs):
        observed["arguments"] = arguments
        observed["kwargs"] = kwargs
        return subprocess.CompletedProcess(["docker", *arguments], 0, "17\n", "")

    monkeypatch.setattr(restore, "_docker", fake_docker)

    assert restore._sqlcmd("SELECT 17;", "Secret-Example-123!", code="probe") == ["17"]
    assert "--interactive" in observed["arguments"]
    assert "-Q" not in observed["arguments"]
    assert observed["arguments"][-2:] == ["-i", "/dev/stdin"]
    assert observed["kwargs"]["input_text"] == "SET NOCOUNT ON; SELECT 17;\nGO\n"
    assert observed["kwargs"]["extra_env"] == {"SQLCMDPASSWORD": "Secret-Example-123!"}
