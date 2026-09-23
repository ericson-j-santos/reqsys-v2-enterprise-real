from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "pc24x7_ollama_mcp_funnel.py"
SPEC = importlib.util.spec_from_file_location("pc24x7_ollama_mcp_funnel", MODULE)
assert SPEC and SPEC.loader
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def test_ingress_is_fixed_to_desktop_loopback_mcp() -> None:
    assert m.EXPECTED_HOST == "DESKTOP-PDQK954"
    assert m.MCP_TARGET == "http://127.0.0.1:8010"
    assert m.MCP_PATH == "/mcp"
    assert m.HTTPS_PORT == 443
    with pytest.raises(m.IngressError, match="host_not_authorized"):
        m.require_host("Noteri")


def test_apply_command_exposes_only_mcp_bridge() -> None:
    command = m.build_apply_command()
    assert command == [
        "tailscale",
        "funnel",
        "--bg",
        "--yes",
        "--https=443",
        "--set-path=/mcp",
        "http://127.0.0.1:8010",
    ]
    joined = " ".join(command)
    assert "11434" not in joined
    assert "8008" not in joined
    assert "8083" not in joined


def test_route_present_requires_path_and_exact_local_port() -> None:
    valid = {
        "configured": True,
        "payload": {
            "Web": {
                "https://desktop.example.ts.net:443": {
                    "Handlers": {
                        "/mcp": {"Proxy": "http://127.0.0.1:8010"}
                    }
                }
            }
        },
    }
    assert m.route_present(valid) is True
    assert m.route_present({"configured": True, "payload": {"/mcp": "http://127.0.0.1:8008"}}) is False
    assert m.route_present({"configured": True, "payload": {"/other": "http://127.0.0.1:8010"}}) is False


def test_stable_url_requires_tailscale_dns_name() -> None:
    status = {"Self": {"DNSName": "desktop.tail123.ts.net."}}
    assert m.stable_base_url(status) == "https://desktop.tail123.ts.net"
    with pytest.raises(m.IngressError, match="dns_name_invalid"):
        m.stable_base_url({"Self": {"DNSName": "desktop.example.com"}})


def test_apply_failure_distinguishes_one_time_funnel_consent() -> None:
    consent = subprocess.CompletedProcess(
        ["tailscale"], 1, stdout="", stderr="Enable Funnel at https://login.tailscale.com/admin/funnel"
    )
    other = subprocess.CompletedProcess(["tailscale"], 1, stdout="", stderr="unexpected failure")
    assert m.classify_apply_failure(consent) == "TAILSCALE_FUNNEL_CONSENT_REQUIRED"
    assert m.classify_apply_failure(other) == "TAILSCALE_FUNNEL_APPLY_FAILED"
