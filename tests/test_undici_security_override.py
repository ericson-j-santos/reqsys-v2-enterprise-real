import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_JSON = ROOT / "frontend" / "package.json"
PACKAGE_LOCK = ROOT / "frontend" / "package-lock.json"


def test_undici_override_and_lock_are_patched() -> None:
    package = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    lock = json.loads(PACKAGE_LOCK.read_text(encoding="utf-8"))

    assert package["overrides"]["undici"] == "7.30.1"

    locked = lock["packages"]["node_modules/undici"]
    assert locked["version"] == "7.30.1"
    assert locked["resolved"].endswith("/undici-7.30.1.tgz")
    assert locked["integrity"].startswith("sha512-")


def test_vulnerable_undici_override_is_absent() -> None:
    assert '"undici": "7.30.0"' not in PACKAGE_JSON.read_text(encoding="utf-8")
    assert '"version": "7.30.0"' not in PACKAGE_LOCK.read_text(encoding="utf-8")
