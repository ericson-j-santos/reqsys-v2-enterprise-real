"""Stage-only de release do Broker: positivo, negativos, replay e preservação."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import desktop_admin_broker_stage_only as stage

SHA = "a" * 40
CORRELATION = "stage-broker-3096-dev-1"


@pytest.fixture
def setup_stage(monkeypatch, tmp_path: Path):
    source = tmp_path / "reqsys-source"
    scripts = source / "scripts"
    scripts.mkdir(parents=True)
    for relative in stage.REQUIRED:
        item = source / relative
        item.parent.mkdir(parents=True, exist_ok=True)
        item.write_text(f"immutable:{relative}\n", encoding="utf-8")
    root = tmp_path / "local-appdata" / "ReqSys" / "DesktopAdminBroker"
    monkeypatch.setattr(stage.broker, "require_windows_desktop", lambda: "DESKTOP-PDQK954")
    monkeypatch.setattr(stage.broker, "_validate_checkout", lambda given, sha: source)
    monkeypatch.setattr(stage.broker, "default_runtime_root", lambda: root)
    monkeypatch.setattr(stage.broker, "register_task",
                        lambda **kwargs: pytest.fail("stage called Task Scheduler"))
    monkeypatch.setattr(stage.broker, "run_task",
                        lambda: pytest.fail("stage started a task"))
    return source, root


def execute(source: Path, **kwargs):
    inputs = {
        "source_sha": SHA, "correlation_id": CORRELATION,
        "confirm": stage.CONFIRM,
    }
    inputs.update(kwargs)
    return stage.stage(source, **inputs)


def test_positive_release_stage_readback_and_idempotency(setup_stage):
    source, root = setup_stage
    first = execute(source)
    receipt = root / "stage-receipts" / (SHA + ".json")
    before = receipt.read_bytes()
    second = execute(source, correlation_id="stage-broker-3096-dev-replay")
    data = json.loads(receipt.read_text(encoding="utf-8"))
    assert data["first_correlation_id"] == CORRELATION
    assert first["ok"] is True and first["new_release"] is True
    assert second["ok"] is True and second["new_release"] is False
    assert first["manifest_sha256"] == second["manifest_sha256"]
    assert receipt.read_bytes() == before
    assert data["result"] == first["result"] == "BROKER_RELEASE_STAGED_NOT_ACTIVATED"
    assert data["python_persistence_verified"] is False
    assert data["manifest_sha256"] == first["manifest_sha256"]
    stage._verify_release(root / "releases" / SHA, data["manifest"])
    assert not (root / "stage-only.lock").exists()
    for active in ("metadata.json", "run.py", "Activate-Desktop-Admin-Broker.cmd"):
        assert not (root / active).exists()
    assert first["admin_task_modified"] is False
    assert first["functional_ready"] is False
    assert first["secrets_read"] is False


@pytest.mark.parametrize("arguments,reason", [
    ({"confirm": "WRONG"}, "stage_confirmation_invalid"),
    ({"correlation_id": "../../escape"}, "stage_correlation_invalid"),
    ({"source_sha": "bad"}, "source_sha inválido"),
])
def test_invalid_request_stops_before_stage(setup_stage, arguments, reason):
    source, root = setup_stage
    with pytest.raises((stage.StageBlocked, stage.broker.BrokerError), match=reason):
        execute(source, **arguments)
    assert not root.exists()


def test_rejects_other_host_before_mutation(setup_stage, monkeypatch):
    source, root = setup_stage
    def deny():
        raise stage.broker.BrokerError("host não autorizado")
    monkeypatch.setattr(stage.broker, "require_windows_desktop", deny)
    with pytest.raises(stage.broker.BrokerError, match="host não autorizado"):
        execute(source)
    assert not root.exists()


def test_missing_required_source_never_publishes_receipt(setup_stage):
    source, root = setup_stage
    (source / stage.REQUIRED[0]).unlink()
    with pytest.raises(stage.StageBlocked, match="stage_source_incomplete_or_unsafe"):
        execute(source)
    assert not (root / "stage-receipts" / (SHA + ".json")).exists()


def test_existing_corrupt_release_rejected_without_overwrite(setup_stage):
    source, root = setup_stage
    execute(source)
    item = root / "releases" / SHA / stage.REQUIRED[1]
    item.write_text("CORRUPTED\n", encoding="utf-8")
    receipt = root / "stage-receipts" / (SHA + ".json")
    before = receipt.read_bytes()
    with pytest.raises(stage.StageBlocked, match="stage_release_digest_mismatch"):
        execute(source)
    assert item.read_text() == "CORRUPTED\n"
    assert receipt.read_bytes() == before
    assert not (root / "stage-only.lock").exists()


def test_partial_release_cannot_be_silently_repaired(setup_stage):
    source, root = setup_stage
    item = root / "releases" / SHA / stage.REQUIRED[0]
    item.parent.mkdir(parents=True)
    item.write_text("partial\n", encoding="utf-8")
    with pytest.raises(stage.StageBlocked, match="stage_release_file_set_mismatch"):
        execute(source)
    assert item.read_text() == "partial\n"
    assert not (root / "metadata.json").exists()


def test_rejects_tampered_receipt_without_reset(setup_stage):
    source, root = setup_stage
    execute(source)
    receipt = root / "stage-receipts" / (SHA + ".json")
    data = json.loads(receipt.read_text(encoding="utf-8"))
    data["manifest_sha256"] = "0" * 64
    receipt.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(stage.StageBlocked, match="stage_receipt_conflict"):
        execute(source)
    assert json.loads(receipt.read_text())["manifest_sha256"] == "0" * 64


def test_exclusive_lock_blocks_second_actor_without_side_effect(setup_stage):
    source, root = setup_stage
    root.mkdir(parents=True)
    lock = root / "stage-only.lock"
    lock.write_text("another-actor", encoding="ascii")
    with pytest.raises(stage.StageBlocked, match="stage_lock_busy"):
        execute(source)
    assert lock.read_text() == "another-actor"
    assert not (root / "metadata.json").exists()


def test_active_invalid_metadata_preserved_as_bytes(setup_stage):
    source, root = setup_stage
    root.mkdir(parents=True)
    old = b"\xfflegacy-invalid-json"
    (root / "metadata.json").write_bytes(old)
    reply = execute(source)
    assert reply["ok"] is True
    assert (root / "metadata.json").read_bytes() == old
    assert reply["metadata_active_modified"] is False


def test_failed_receipt_write_preserves_existing_legacy_state(setup_stage, monkeypatch):
    source, root = setup_stage
    root.mkdir(parents=True)
    (root / "metadata.json").write_bytes(b"unchanged-active")
    real_writer = stage.broker.atomic_json
    def fail_write(path, payload):
        raise OSError("simulated interrupted stage receipt")
    monkeypatch.setattr(stage.broker, "atomic_json", fail_write)
    with pytest.raises(OSError, match="simulated interrupted"):
        execute(source)
    assert (root / "metadata.json").read_bytes() == b"unchanged-active"
    assert not (root / "stage-only.lock").exists()
    monkeypatch.setattr(stage.broker, "atomic_json", real_writer)
    recovered = execute(source)
    assert recovered["ok"] is True
    assert recovered["new_release"] is False


def test_staged_release_symlink_is_rejected(setup_stage, tmp_path):
    source, root = setup_stage
    external = tmp_path / "untrusted"
    external.mkdir()
    path = root / "releases"
    path.mkdir(parents=True)
    try:
        (path / SHA).symlink_to(external, target_is_directory=True)
    except (NotImplementedError, OSError):
        pytest.skip("symlinks unavailable to non-admin Windows test host")
    with pytest.raises(stage.StageBlocked, match="stage_directory_link_forbidden"):
        execute(source)
    assert not (external / stage.REQUIRED[0]).exists()


def test_persistent_stage_does_not_create_administrative_capability():
    raw = (Path(__file__).parents[1] / "scripts/desktop_admin_broker_stage_only.py").read_text()
    for forbidden in ("register_task(", "run_task(", "ShellExecuteW(", "runas", "schtasks.exe"):
        assert forbidden not in raw
    assert "broker._validate_checkout(source_root, sha)" in raw
    assert "broker.atomic_json(receipt_path, expected)" in raw


def test_tampered_correlation_in_receipt_blocks_replay(setup_stage):
    source, root = setup_stage
    execute(source)
    receipt = root / "stage-receipts" / (SHA + ".json")
    data = json.loads(receipt.read_text(encoding="utf-8"))
    data["first_correlation_id"] = "../../unsafe"
    receipt.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(stage.StageBlocked, match="stage_receipt_correlation_invalid"):
        execute(source)
