from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import notify_hitl_approval_teams as module


def test_build_message_contains_three_authenticated_decision_paths():
    url = "https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/1111"
    text = module.build_message(
        request_title="Aprovar fluxo HITL",
        control_id="REQSYS-HITL-001",
        summary="Validar o novo fluxo de aprovacao.",
        request_url=url,
        evidence_url=f"{url}#evidence",
    )
    assert "/approve <justificativa>" in text
    assert "/reject <justificativa>" in text
    assert "/adjust <justificativa>" in text
    assert "production_touched=false" in text


def test_send_request_uses_existing_gateway(monkeypatch):
    captured = {}

    def fake_send(**kwargs):
        captured.update(kwargs)
        return {"entregue": True, "canal_usado": "flow_bot", "correlation_id": "abc"}

    monkeypatch.setattr(module, "enviar_mensagem", fake_send)
    payload = module.send_request(
        request_title="Aprovar fluxo HITL",
        control_id="REQSYS-HITL-001",
        summary="Validar o novo fluxo de aprovacao.",
        request_url="https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/1111",
        evidence_url=None,
        base_url="https://reqsys-api.fly.dev",
        destination_id="owner@example.com",
        mode="auto",
        destination_type="chat",
        dry_run=False,
        timeout=10,
    )
    assert captured["autor"] == "reqsys-hitl"
    assert captured["titulo"].startswith("ReqSys HITL")
    assert payload["notification"]["entregue"] is True
    assert len(payload["request_sha256"]) == 64


def test_build_message_rejects_non_github_url():
    with pytest.raises(ValueError):
        module.build_message(
            request_title="Aprovar",
            control_id="REQSYS-HITL-001",
            summary="Resumo suficientemente claro.",
            request_url="https://example.com/request",
            evidence_url=None,
        )
