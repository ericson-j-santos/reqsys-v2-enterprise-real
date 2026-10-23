from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.pc24x7_public_dev_cutover_guard as guard

SHA = "a" * 40
IMAGE = "sha256:" + "b" * 64
CORRELATION = "pc24x7-public-static-123-1"


def _prepared_runtime():
    return {
        "schema": 2,
        "state": "prepared",
        "host": guard.HOST,
        "environment": "dev",
        "project": guard.PROJECT,
        "runtime_root": str(guard.ROOT),
        "runtime_sha": "c" * 40,
        "services": {},
        "compose_files": [],
        "environment_files": [],
        "rollback_override": {},
        "fingerprint": "d" * 64,
    }


def _patch_prepare_dependencies(monkeypatch, root: Path):
    monkeypatch.setattr(guard.recovery, "observed_scope", lambda _host: None)
    monkeypatch.setattr(guard.recovery, "capture", lambda *_args, **_kwargs: {"fingerprint": "1" * 64})
    monkeypatch.setattr(guard.recovery, "prepare", lambda *_args, **_kwargs: _prepared_runtime())
    monkeypatch.setattr(guard, "_unique_container", lambda _service: "db-container")
    monkeypatch.setattr(guard, "_db_identity", lambda _container, _root: IMAGE)
    monkeypatch.setattr(
        guard,
        "database_snapshot",
        lambda *_args, **_kwargs: {"table_count": 4, "row_count_total": 19, "fingerprint": "e" * 64},
    )
    monkeypatch.setattr(guard, "_dump_database", lambda _container: b"private-postgres-dump")
    monkeypatch.setattr(guard.recovery, "file_meta", lambda path, _root: {
        "relative_path": path.relative_to(root).as_posix(),
        "size": path.stat().st_size,
        "sha256": __import__("hashlib").sha256(path.read_bytes()).hexdigest(),
    })


def test_prepare_keeps_only_dpapi_ciphertext_and_sanitized_public_contract(monkeypatch, tmp_path):
    root = tmp_path
    _patch_prepare_dependencies(monkeypatch, root)
    restored = []
    manifest_path = root / ".reqsys-recovery" / f"public-dev-{CORRELATION}.manifest.json"
    manifest = guard.prepare(
        SHA,
        CORRELATION,
        manifest_path,
        root=root,
        hostname=guard.HOST,
        runner=object(),
        protect=lambda value, *, encrypt: b"ciphertext:" + value[::-1],
        restore=lambda dump, image, correlation, expected: restored.append(
            (dump, image, correlation, expected)
        ),
    )
    backup = root / manifest["database"]["backup"]["relative_path"]
    assert backup.read_bytes().startswith(b"ciphertext:")
    assert b"private-postgres-dump" not in backup.read_bytes()
    assert restored and restored[0][1:3] == (IMAGE, CORRELATION)
    assert manifest["database"]["isolated_restore_verified"] is True
    assert manifest["production_touched"] is False
    assert manifest_path.is_file()
    rendered = json.dumps(manifest)
    assert "POSTGRES_PASSWORD" not in rendered


def test_validate_rejects_outer_manifest_tamper(monkeypatch, tmp_path):
    root = tmp_path
    _patch_prepare_dependencies(monkeypatch, root)
    manifest_path = root / ".reqsys-recovery" / f"public-dev-{CORRELATION}.manifest.json"
    def protect(value, *, encrypt):
        return value[::-1]
    manifest = guard.prepare(
        SHA, CORRELATION, manifest_path, root=root, hostname=guard.HOST,
        runner=object(), protect=protect, restore=lambda *_args: None,
    )
    external = manifest["fingerprint"]
    manifest["expected_sha"] = "f" * 40
    manifest["fingerprint"] = guard._outer_fingerprint(
        {key: value for key, value in manifest.items() if key != "fingerprint"}
    )
    with pytest.raises(guard.CutoverBlocked, match="external_fingerprint_mismatch"):
        guard.validate(
            manifest, external, SHA, root=root, runner=object(),
            unprotect=lambda value, *, encrypt: value[::-1],
        )


def test_isolated_restore_uses_pinned_image_no_network_and_cleans_owned_resources(monkeypatch):
    calls = []

    def fake_text(argv, *, timeout=120):
        calls.append((tuple(argv), None))
        return ""

    def fake_docker(argv, *, data=None, timeout=120, can_fail=False):
        calls.append((tuple(argv), data))
        if argv[:2] == ["exec", "reqsys-public-dev-restore-" + __import__("hashlib").sha256(CORRELATION.encode()).hexdigest()[:16]] and "pg_isready" in argv:
            return b"accepting connections"
        return b""

    monkeypatch.setattr(guard, "_text", fake_text)
    monkeypatch.setattr(guard, "_docker", fake_docker)
    expected = {"table_count": 4, "row_count_total": 19, "fingerprint": "e" * 64}
    monkeypatch.setattr(guard, "database_snapshot", lambda *_args, **_kwargs: expected)
    guard._isolated_restore(b"dump", IMAGE, CORRELATION, expected, sleeper=lambda _value: None)
    argv = [item[0] for item in calls]
    create = next(item for item in argv if item and item[0] == "create")
    assert "--network" in create and create[create.index("--network") + 1] == "none"
    assert create[-1] == IMAGE
    restore = next(item for item in calls if "pg_restore" in item[0])
    assert restore[1] == b"dump"
    assert any(item[:2] == ("rm", "-f") for item in argv)
    assert any(item[:3] == ("volume", "rm", "-f") for item in argv)


def test_workflow_never_uploads_private_manifest_or_backup():
    raw = (Path(__file__).resolve().parents[1] / ".github" / "workflows" /
           "noteri-study-mode-dev-reconcile.yml").read_text(encoding="utf-8")
    upload = raw.split("- name: Upload public DEV physical evidence", 1)[1].split(
        "- name: Recover and validate Engineering Orchestrator DEV", 1
    )[0]
    assert "artifacts/pc24x7-public-dev/evidence.json" in upload
    assert ".reqsys-recovery" not in upload
    assert "pgdump" not in upload


def test_public_receipt_allows_only_sanitized_contract_in_fixed_directory(tmp_path):
    receipt = tmp_path / "artifacts" / "pc24x7-public-dev" / "cutover-prepare.json"
    guard.write_public_receipt(
        receipt,
        {
            "status": "prepared",
            "fingerprint": "f" * 64,
            "backup_verified": True,
            "isolated_restore_verified": True,
            "rollback_images_prepared": True,
            "production_touched": False,
        },
        root=tmp_path,
    )
    assert json.loads(receipt.read_text(encoding="utf-8"))["status"] == "prepared"

    with pytest.raises(guard.CutoverBlocked, match="private_fields"):
        guard.write_public_receipt(
            tmp_path / "artifacts" / "pc24x7-public-dev" / "cutover-private.json",
            {"status": "prepared", "database": {"private": True}},
            root=tmp_path,
        )
    with pytest.raises(guard.CutoverBlocked, match="path_refused"):
        guard.write_public_receipt(
            tmp_path / ".reqsys-recovery" / "cutover-prepare.json",
            {"status": "prepared"},
            root=tmp_path,
        )


@pytest.mark.parametrize(
    ("failure", "expected_reason", "expected_scope_diagnostic"),
    (
        (
            guard.recovery.RecoveryError(
                "command_failed:C:\\private\\docker.exe:secret-value"
            ),
            "governed_dependency_failed",
            "not_applicable",
        ),
        (
            guard.recovery.RecoveryError("working_dir_mismatch"),
            "runtime_scope_invalid",
            "working_dir_mismatch",
        ),
        (
            ValueError("credential=do-not-publish"),
            "cutover_failure_unclassified",
            "not_applicable",
        ),
    ),
)
def test_main_persists_allowlisted_failure_receipt_without_private_detail(
    monkeypatch, tmp_path, capsys, failure, expected_reason, expected_scope_diagnostic,
):
    receipt = tmp_path / "artifacts" / "pc24x7-public-dev" / "cutover-prepare-test.json"
    manifest = tmp_path / ".reqsys-recovery" / "private.manifest.json"
    original_write = guard.write_public_receipt

    def fail_prepare(*_args, **_kwargs):
        raise failure

    monkeypatch.setattr(guard, "prepare", fail_prepare)
    monkeypatch.setattr(
        guard,
        "write_public_receipt",
        lambda path, value: original_write(path, value, root=tmp_path),
    )
    monkeypatch.setattr(
        guard.sys,
        "argv",
        [
            "pc24x7_public_dev_cutover_guard.py",
            "prepare",
            "--expected-sha", SHA,
            "--correlation-id", CORRELATION,
            "--manifest", str(manifest),
            "--receipt-file", str(receipt),
            "--confirm", guard.PREPARE_CONFIRM,
        ],
    )

    assert guard.main() == 1
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload == {
        "status": "blocked",
        "reason_code": expected_reason,
        "scope_diagnostic_code": expected_scope_diagnostic,
        "backup_verified": False,
        "isolated_restore_verified": False,
        "rollback_images_prepared": False,
        "production_touched": False,
    }
    rendered = receipt.read_text(encoding="utf-8") + capsys.readouterr().out
    assert "private" not in rendered
    assert "secret-value" not in rendered
    assert "credential" not in rendered


def test_unknown_failure_is_reduced_to_allowlisted_generic_reason():
    payload = guard.public_failure_receipt(RuntimeError("credential=do-not-publish"))
    assert payload["reason_code"] == "cutover_failure_unclassified"
    assert payload["reason_code"] in guard.PUBLIC_FAILURE_REASON_CODES
    assert payload["scope_diagnostic_code"] == "not_applicable"
    assert "credential" not in json.dumps(payload)


def test_legacy_source_failures_have_bounded_public_classification():
    scope_codes = {
        "external_source_parent_refused",
        "external_compose_not_allowlisted",
        "external_source_scope_refused",
        "external_source_file_refused",
        "external_source_root_ambiguous",
        "external_environment_scope_refused",
        "external_snapshot_scope_refused",
        "external_snapshot_dir_refused",
    }
    aggregate_codes = {
        "external_source_read_failed": "recovery_source_invalid",
        "external_snapshot_collision": "recovery_source_invalid",
        "external_snapshot_write_failed": "private_recovery_storage_failed",
    }

    for code in scope_codes:
        payload = guard.public_failure_receipt(guard.recovery.RecoveryError(code))
        assert payload["reason_code"] == "runtime_scope_invalid"
        assert payload["scope_diagnostic_code"] == code
    for code, reason in aggregate_codes.items():
        payload = guard.public_failure_receipt(guard.recovery.RecoveryError(code))
        assert payload["reason_code"] == reason
        assert payload["scope_diagnostic_code"] == "not_applicable"


@pytest.mark.parametrize("code", sorted(
    guard.PUBLIC_SCOPE_DIAGNOSTIC_CODES - {"not_applicable"}
))
def test_runtime_scope_failure_preserves_only_allowlisted_diagnostic_code(code):
    payload = guard.public_failure_receipt(guard.recovery.RecoveryError(code))
    assert payload["reason_code"] == "runtime_scope_invalid"
    assert payload["scope_diagnostic_code"] == code


def test_owner_risk3_steps_keep_gateway_global_fail_closed_and_worktree_clean():
    root = Path(__file__).resolve().parents[1]
    raw = (root / ".github" / "workflows" / "noteri-study-mode-dev-reconcile.yml").read_text(
        encoding="utf-8"
    )
    ignore = (root / ".gitignore").read_text(encoding="utf-8")
    public_static = raw.split("- name: Prepare protected PostgreSQL backup", 1)[1].split(
        "- name: Recover and validate Engineering Orchestrator DEV", 1
    )[0]
    assert "owner_risk3_gateway.py" in public_static
    assert "set_owner_risk3_action.py" in public_static
    assert "set_owner_risk3_development_mode.py" not in public_static
    assert "AUTHORIZE-SPECIFIC-RISK3-ACTION" in public_static
    assert "broad_development_mode_changed -ne $false" in public_static
    assert "'--', $env:GATEWAY_PYTHON" not in public_static
    assert "'--risk', '3'" not in public_static
    assert "'--timeout', '1200'" not in public_static
    assert "'--timeout', '1500'" not in public_static
    assert "repo://reqsys/environment/dev/host/desktop-pdqk954" in public_static
    assert "prepare_failure_receipt_missing_or_invalid" in public_static
    assert "$allowedFailureReasons -notcontains [string]$blocked.reason_code" in public_static
    assert "$allowedScopeDiagnosticCodes -notcontains [string]$blocked.scope_diagnostic_code" in public_static
    assert "scope_diagnostic_code = $scopeDiagnosticCode" in public_static
    assert "$evidenceFile = Join-Path $env:GITHUB_WORKSPACE " \
        "'artifacts\\pc24x7-public-dev\\evidence.json'" in public_static
    assert "$evidenceFile = Join-Path $env:TARGET_PATH " \
        "'artifacts\\pc24x7-public-dev\\evidence.json'" not in public_static
    assert "WriteAllText($evidenceFile" in public_static
    assert "stdout =" not in public_static
    assert "stderr =" not in public_static
    for reason_code in guard.PUBLIC_FAILURE_REASON_CODES:
        assert f"'{reason_code}'" in public_static
    for diagnostic_code in guard.PUBLIC_SCOPE_DIAGNOSTIC_CODES:
        assert f"'{diagnostic_code}'" in public_static
    assert ".reqsys-recovery/" in ignore
    assert ".reqsys-runtime-inputs/" in ignore
    assert "artifacts/pc24x7-public-dev/evidence.json" in ignore
    assert "artifacts/pc24x7-public-dev/cutover-*.json" in ignore
