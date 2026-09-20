from pathlib import Path
import importlib.util
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "configure_ollama_tailscale_serve.py"
SPEC = importlib.util.spec_from_file_location("configure_ollama_tailscale_serve", SCRIPT)
assert SPEC and SPEC.loader
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def test_backend_fail_closed_outside_loopback():
    with pytest.raises(m.ServeError, match="backend_must_remain_loopback"):
        m.validate_backend("http://192.168.1.60:11434")


def test_backend_accepts_exact_loopback():
    assert m.validate_backend("http://127.0.0.1:11434/") == "http://127.0.0.1:11434"


def test_dns_name_from_status():
    assert m.dns_name({"Self": {"DNSName": "noteri.example.ts.net."}}) == "noteri.example.ts.net"


def test_tailscale_ips_from_status():
    assert m.tailscale_ips({"Self": {"TailscaleIPs": ["100.64.0.10", "fd7a::1"]}}) == [
        "100.64.0.10",
        "fd7a::1",
    ]


def test_configure_uses_private_https_port_and_loopback(monkeypatch):
    seen = []

    monkeypatch.setattr(m, "backend_inventory", lambda _url: {"version": "x", "models": []})
    monkeypatch.setattr(m, "tailscale_status", lambda _binary: {"BackendState": "Running"})
    monkeypatch.setattr(m, "require_ok", lambda result, action: seen.append((result, action)) or "")
    monkeypatch.setattr(m, "run_tailscale", lambda binary, args, timeout=20: seen.append(args) or object())
    monkeypatch.setattr(
        m,
        "validate_private_path",
        lambda _binary, _base, port: {"ok": True, "host": f"https://node.ts.net:{port}/v1"},
    )

    result = m.configure(Path("tailscale.exe"), m.DEFAULT_BACKEND, 11443)

    assert result["ok"] is True
    assert ["serve", "--bg", "--yes", "--https=11443", "http://127.0.0.1:11434"] in seen
