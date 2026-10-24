"""Guard GHSA-xjj6-f33q-929c / CVE-2026-109869 in the frontend npm lock."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
MINIMUM_7X = (7, 30, 1)


def _version(value: object) -> tuple[int, int, int]:
    if not isinstance(value, str):
        raise ValueError("undici_version_invalid")
    parts = value.split(".")
    if len(parts) != 3 or any(not part.isdecimal() for part in parts):
        raise ValueError("undici_version_invalid")
    return tuple(int(part) for part in parts)


def validate_undici_lock(package: dict, lock: dict) -> None:
    override = package.get("overrides", {}).get("undici")
    version = _version(override)
    if version[0] != 7 or version < MINIMUM_7X:
        raise ValueError("undici_override_vulnerable")

    root = lock.get("packages", {}).get("", {})
    if root.get("name") != package.get("name") or root.get("version") != package.get("version"):
        raise ValueError("frontend_lock_root_mismatch")

    entries = {
        path: entry
        for path, entry in lock.get("packages", {}).items()
        if path == "node_modules/undici" or path.endswith("/node_modules/undici")
    }
    if not entries:
        raise ValueError("undici_lock_entry_missing")

    for path, entry in entries.items():
        if entry.get("version") != override:
            raise ValueError(f"undici_lock_version_mismatch:{path}")
        expected = f"https://registry.npmjs.org/undici/-/undici-{override}.tgz"
        if entry.get("resolved") != expected:
            raise ValueError(f"undici_registry_resolution_mismatch:{path}")
        digest = entry.get("integrity")
        if not isinstance(digest, str) or not digest.startswith("sha512-") or len(digest) != 95:
            raise ValueError(f"undici_integrity_missing:{path}")


def _read() -> tuple[dict, dict]:
    return (
        json.loads((FRONTEND / "package.json").read_text(encoding="utf-8")),
        json.loads((FRONTEND / "package-lock.json").read_text(encoding="utf-8")),
    )


def test_patched_undici_override_and_lock_match() -> None:
    package, lock = _read()
    validate_undici_lock(package, lock)


def test_downgraded_override_is_rejected() -> None:
    package, lock = _read()
    package["overrides"]["undici"] = "7.30.0"
    with pytest.raises(ValueError, match="undici_override_vulnerable"):
        validate_undici_lock(package, lock)


def test_downgraded_lock_is_rejected() -> None:
    package, lock = _read()
    lock["packages"]["node_modules/undici"]["version"] = "7.30.0"
    with pytest.raises(ValueError, match="undici_lock_version_mismatch"):
        validate_undici_lock(package, lock)


def test_missing_integrity_is_rejected() -> None:
    package, lock = _read()
    lock["packages"]["node_modules/undici"].pop("integrity")
    with pytest.raises(ValueError, match="undici_integrity_missing"):
        validate_undici_lock(package, lock)
