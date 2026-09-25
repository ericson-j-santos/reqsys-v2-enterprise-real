from pathlib import Path
import importlib.util

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "noteri_desktop_path_receiver.py"
spec = importlib.util.spec_from_file_location("receiver", SCRIPT)
m = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)


def test_sanitizes_localappdata_username():
    raw = r"C:\Users\SomeUser\AppData\Local\ReqSys\DesktopControlPlaneWatchdog\metadata.json"
    assert m.sanitize_path(raw) == r"%LOCALAPPDATA%\ReqSys\DesktopControlPlaneWatchdog\metadata.json"


def test_accepts_repo_watchdog_script():
    raw = r"C:\dev\reqsys-v2-enterprise-real\scripts\desktop_control_plane_watchdog.py"
    assert m.sanitize_path(raw) == raw


def test_rejects_unrelated_or_secret_paths():
    assert m.sanitize_path(r"C:\Users\x\.ssh\id_rsa") is None
    assert m.sanitize_path(r"C:\Windows\System32\drivers\etc\hosts") is None
