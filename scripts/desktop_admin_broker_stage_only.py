#!/usr/bin/env python3
"""Prepara release imutável do Admin Broker no Desktop, sem ativação/UAC.

Esta ferramenta é somente stage: não escreve metadata.json nem launchers ativos,
não registra tarefa ou serviço e não interpreta comando recebido da rede.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any

if __package__:
    from . import desktop_admin_broker as broker
else:
    import desktop_admin_broker as broker

CONFIRM = "STAGE-DESKTOP-ADMIN-BROKER-DEV"
REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,99}$")
REQUIRED = (
    "scripts/desktop_admin_broker.py",
    "scripts/desktop_admin_broker_uac_launcher.py",
    f"scripts/{broker.WATCHDOG_SCRIPT}",
    f"scripts/{broker.WATCHDOG_UAC_SCRIPT}",
    f"scripts/{broker.RDC_RECOVERY_SCRIPT}",
    f"scripts/{broker.RUNNER_BOOTSTRAP_SCRIPT}",
    f"scripts/{broker.RUNNER_INSTALL_SCRIPT}",
    f"scripts/{broker.RUNNER_ONBOARD_SCRIPT}",
    f"scripts/{broker.RUNNER_PREFLIGHT_SCRIPT}",
    f"config/{broker.RUNNER_POOL_POLICY}",
)


class StageBlocked(RuntimeError):
    """Erro com código sanitizado; nunca inclui conteúdo ou caminhos locais."""


def regular_file(path: Path) -> bool:
    try:
        mode = path.lstat().st_mode
        return stat.S_ISREG(mode) and not path.is_symlink()
    except (OSError, ValueError):
        return False


def require_safe_directory(path: Path) -> None:
    if path.is_symlink() or (
        hasattr(path, "is_junction") and path.is_junction()
    ):
        raise StageBlocked("stage_directory_link_forbidden")
    if path.exists() and not path.is_dir():
        raise StageBlocked("stage_directory_not_directory")


def _check_source(root: Path) -> dict[str, str]:
    digests: dict[str, str] = {}
    for relative in REQUIRED:
        item = root / relative
        if not regular_file(item):
            raise StageBlocked("stage_source_incomplete_or_unsafe")
        try:
            digests[relative] = hashlib.sha256(item.read_bytes()).hexdigest()
        except OSError as exc:
            raise StageBlocked("stage_source_unreadable") from exc
    return digests


def _manifest_digest(manifest: dict[str, str]) -> str:
    raw = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _verify_release(release: Path, manifest: dict[str, str]) -> None:
    require_safe_directory(release)
    if not release.is_dir():
        raise StageBlocked("stage_release_unavailable")
    expected = set(manifest)
    observed: set[str] = set()
    try:
        for item in release.rglob("*"):
            relative = item.relative_to(release).as_posix()
            if item.is_symlink() or (
                hasattr(item, "is_junction") and item.is_junction()
            ):
                raise StageBlocked("stage_release_unsafe")
            if item.is_dir():
                continue
            if not regular_file(item):
                raise StageBlocked("stage_release_unsafe")
            observed.add(relative)
        if observed != expected:
            raise StageBlocked("stage_release_file_set_mismatch")
        for relative, digest in manifest.items():
            if hashlib.sha256((release / relative).read_bytes()).hexdigest() != digest:
                raise StageBlocked("stage_release_digest_mismatch")
    except OSError as exc:
        raise StageBlocked("stage_release_readback_failed") from exc


def _acquire_lock(runtime: Path, correlation_id: str) -> Path:
    lock = runtime / "stage-only.lock"
    if lock.is_symlink():
        raise StageBlocked("stage_lock_unsafe")
    try:
        with lock.open("x", encoding="ascii") as stream:
            stream.write(correlation_id)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise StageBlocked("stage_lock_busy") from exc
    return lock


def _assert_no_active_mutation(runtime: Path, observed: dict[str, bytes | None]) -> None:
    for file, old in observed.items():
        path = runtime / file
        try:
            current = path.read_bytes() if path.exists() else None
        except OSError as exc:
            raise StageBlocked("stage_active_state_unreadable") from exc
        if current != old:
            raise StageBlocked("stage_active_state_changed")


def stage(
    source_root: Path, source_sha: str, correlation_id: str, confirm: str
) -> dict[str, Any]:
    if confirm != CONFIRM:
        raise StageBlocked("stage_confirmation_invalid")
    if not REQUEST_ID.fullmatch(correlation_id):
        raise StageBlocked("stage_correlation_invalid")
    host = broker.require_windows_desktop()
    sha = broker.validate_sha(source_sha)
    source = broker._validate_checkout(source_root, sha)
    python = Path(sys.executable).resolve()
    if not regular_file(python):
        raise StageBlocked("stage_python_unavailable")
    root = broker.default_runtime_root()
    for component in (root.parent.parent, root.parent, root):
        require_safe_directory(component)
    root.mkdir(parents=True, exist_ok=True)
    releases = root / "releases"
    receipts = root / "stage-receipts"
    for directory in (releases, receipts):
        require_safe_directory(directory)
        directory.mkdir(parents=True, exist_ok=True)
    lock = _acquire_lock(root, correlation_id)
    try:
        active = ("metadata.json", "run.py", "Activate-Desktop-Admin-Broker.cmd")
        snapshot: dict[str, bytes | None] = {}
        for name in active:
            current = root / name
            if current.is_symlink() or (
                hasattr(current, "is_junction") and current.is_junction()
            ):
                raise StageBlocked("stage_active_path_unsafe")
            snapshot[name] = current.read_bytes() if current.exists() else None
        manifest = _check_source(source)
        manifest_sha = _manifest_digest(manifest)
        release = releases / sha
        created = False
        if release.exists() or release.is_symlink():
            _verify_release(release, manifest)
        else:
            with tempfile.TemporaryDirectory(prefix=".stage-", dir=releases) as staging:
                pending = Path(staging) / "release"
                broker._copy_release(source, pending)
                _verify_release(pending, manifest)
                if release.exists() or release.is_symlink():
                    raise StageBlocked("stage_release_race")
                try:
                    pending.rename(release)
                except OSError as exc:
                    raise StageBlocked("stage_release_publish_failed") from exc
                created = True
        receipt_path = receipts / (sha + ".json")
        if receipt_path.is_symlink():
            raise StageBlocked("stage_receipt_unsafe")
        expected = {
            "schema_version": "1",
            "result": "BROKER_RELEASE_STAGED_NOT_ACTIVATED",
            "host": host,
            "environment": "local/DEV",
            "source_sha": sha,
            "manifest": manifest,
            "manifest_sha256": manifest_sha,
            "activation_pending": True,
            "metadata_active_modified": False,
            "admin_task_modified": False,
            "service_started": False,
            "python_present": True,
            "python_persistence_verified": False,
            "production_touched": False,
            "secrets_read": False,
            "reboot_performed": False,
        }
        if receipt_path.exists():
            if not regular_file(receipt_path):
                raise StageBlocked("stage_receipt_unsafe")
            try:
                stored = json.loads(receipt_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, ValueError) as exc:
                raise StageBlocked("stage_receipt_unreadable") from exc
            if stored != expected:
                raise StageBlocked("stage_receipt_conflict")
        else:
            broker.atomic_json(receipt_path, expected)
        if json.loads(receipt_path.read_text(encoding="utf-8")) != expected:
            raise StageBlocked("stage_receipt_readback_failed")
        _verify_release(release, manifest)
        _assert_no_active_mutation(root, snapshot)
        return {
            "result": "BROKER_RELEASE_STAGED_NOT_ACTIVATED",
            "ok": True,
            "host": host,
            "source_sha": sha,
            "correlation_id": correlation_id,
            "manifest_sha256": manifest_sha,
            "new_release": created,
            "activation_pending": True,
            "functional_ready": False,
            "admin_task_modified": False,
            "metadata_active_modified": False,
            "production_touched": False,
            "secrets_read": False,
        }
    finally:
        try:
            if regular_file(lock) and lock.read_text(encoding="ascii") == correlation_id:
                lock.unlink()
        except OSError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage-only do Admin Broker DEV")
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    try:
        result = stage(args.source_root, args.source_sha, args.correlation_id, args.confirm)
    except (StageBlocked, broker.BrokerError, OSError, ValueError) as exc:
        code = str(exc) if isinstance(exc, StageBlocked) else "stage_source_or_host_invalid"
        print(json.dumps({"ok": False, "result": "STAGE_BLOCKED", "reason": code}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
