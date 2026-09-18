from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "noteri_host_profile_agent_control.py"
SPEC = importlib.util.spec_from_file_location("noteri_host_profile_agent_control", MODULE_PATH)
assert SPEC and SPEC.loader
control = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = control
SPEC.loader.exec_module(control)


def test_build_command_mantem_loopback_e_script_fixo():
    origin = "https://reqsys.example"
    command = control.build_command(
        host="Noteri",
        port=8765,
        origins=[origin],
    )
    assert command[0] == sys.executable
    assert Path(command[1]).name == "noteri_host_profile_agent.py"
    assert command[command.index("--bind") + 1] == "127.0.0.1"
    assert command[command.index("--host") + 1] == "Noteri"
    assert command[command.index("--allow-origin") + 1] == origin


@pytest.mark.parametrize("origin", ["*", "https://*.example.com", "file:///tmp/test"])
def test_build_command_recusa_origin_insegura(origin: str):
    with pytest.raises(ValueError):
        control.build_command(host="Noteri", port=8765, origins=[origin])


def test_start_reutiliza_agente_saudavel(monkeypatch):
    monkeypatch.setattr(control.socket, "gethostname", lambda: "Noteri")
    monkeypatch.setattr(
        control,
        "probe",
        lambda port=8765, timeout=1.0: {
            "ok": True,
            "service": control.SERVICE_NAME,
            "host": "Noteri",
            "loopback_only": True,
        },
    )
    result = control.start_agent(host="Noteri", port=8765, origins=[])
    assert result["ok"] is True
    assert result["reused"] is True
    assert result["loopback_only"] is True


def test_start_recusa_execucao_em_host_diferente(monkeypatch):
    monkeypatch.setattr(control.socket, "gethostname", lambda: "DESKTOP-PDQK954")
    with pytest.raises(RuntimeError, match="host atual não corresponde"):
        control.start_agent(host="Noteri", port=8765, origins=[])
