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


def test_send_request_uses_dynamic_policy_and_existing_gateway(monkeypatch):
    captured = {}

    def fake_send(**kwargs):
        captured.update(kwargs)
        return {
            "entregue": True,
            "canal_usado": "recipient_policy",
            "correlation_id": "abc",
            "provider_response": {"delivered": 2},
        }

    monkeypatch.setattr(module, "enviar_mensagem", fake_send)
    payload = module.send_request(
        request_title="Aprovar fluxo HITL",
        control_id="REQSYS-HITL-001",
        summary="Validar o novo fluxo de aprovacao.",
        request_url="https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/1111",
        evidence_url=None,
        base_url="https://reqsys-api.fly.dev",
        destination_id="fallback@example.com",
        recipient_policy="hitl-approvers",
        delivery_mode="all",
        mode="auto",
        destination_type="auto",
        dry_run=False,
        timeout=10,
    )
    assert captured["autor"] == "reqsys-hitl"
    assert captured["recipient_policy"] == "hitl-approvers"
    assert captured["delivery_mode"] == "all"
    assert captured["destino_id"] == "fallback@example.com"
    assert payload["notification"]["entregue"] is True
    assert payload["recipient_policy"] == "hitl-approvers"
    assert len(payload["request_sha256"]) == 64


def test_send_request_does_not_require_explicit_destination(monkeypatch):
    def fake_send(**kwargs):
        assert kwargs["destino_id"] is None
        assert kwargs["recipient_policy"] == "hitl-approvers"
        return {"entregue": True, "correlation_id": "dynamic"}

    monkeypatch.setattr(module, "enviar_mensagem", fake_send)
    payload = module.send_request(
        request_title="Aprovar fluxo HITL",
        control_id="REQSYS-HITL-001",
        summary="Validar o novo fluxo de aprovacao.",
        request_url="https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/1111",
        evidence_url=None,
        base_url="https://reqsys-api.fly.dev",
        destination_id=None,
        recipient_policy="hitl-approvers",
        delivery_mode="all",
        mode="auto",
        destination_type="auto",
        dry_run=False,
        timeout=10,
    )
    assert payload["explicit_destination_fallback_configured"] is False


def test_build_message_rejects_non_github_url():
    with pytest.raises(ValueError):
        module.build_message(
            request_title="Aprovar",
            control_id="REQSYS-HITL-001",
            summary="Resumo suficientemente claro.",
            request_url="https://example.com/request",
            evidence_url=None,
        )
