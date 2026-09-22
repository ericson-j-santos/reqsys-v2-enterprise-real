from datetime import UTC, datetime
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import notify_hitl_approval_teams as module


class _FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


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


def test_build_adaptive_card_has_facts_actions_and_sao_paulo_time():
    url = "https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/pull/1116"
    card = module.build_adaptive_card(
        request_title="Aprovar fluxo HITL ReqSys - PR #1116",
        control_id="REQSYS-HITL-001",
        summary="Validar o novo fluxo de aprovacao.",
        request_url=url,
        evidence_url=f"{url}/files",
        environment="Governança (não produtivo)",
        correlation_id="corr-123",
        generated_at=datetime(2026, 7, 30, 19, 13, tzinfo=UTC),
    )

    assert card["type"] == "AdaptiveCard"
    assert card["version"] == "1.2"
    facts = next(item["facts"] for item in card["body"] if item["type"] == "FactSet")
    fact_map = {item["title"]: item["value"] for item in facts}
    assert fact_map["PR/Issue"] == "PR #1116"
    assert fact_map["Controle"] == "REQSYS-HITL-001"
    assert fact_map["Ambiente"] == "Governança (não produtivo)"
    assert fact_map["Horário"] == "30/07/2026 16:13 (America/Sao_Paulo)"
    assert fact_map["Correlation ID"] == "corr-123"
    assert fact_map["Produção"] == "production_touched=false"
    assert [action["title"] for action in card["actions"]] == [
        "Aprovar no GitHub",
        "Rejeitar no GitHub",
        "Solicitar ajuste",
    ]
    assert all(action["url"] == url for action in card["actions"])


def test_send_request_prefers_direct_adaptive_webhook(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return _FakeResponse({"accepted": True, "eventType": "hitl-approval-request"}, status=202)

    def gateway_must_not_run(**kwargs):
        raise AssertionError("gateway fallback nao deve executar quando o Adaptive Card foi aceito")

    monkeypatch.setattr(module, "urlopen", fake_urlopen)
    monkeypatch.setattr(module, "enviar_mensagem", gateway_must_not_run)

    payload = module.send_request(
        request_title="Aprovar fluxo HITL ReqSys - PR #1116",
        control_id="REQSYS-HITL-001",
        summary="Validar o novo fluxo de aprovacao.",
        request_url="https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/pull/1116",
        evidence_url="https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/pull/1116/files",
        environment="Governança (não produtivo)",
        base_url="https://reqsys-api.fly.dev",
        destination_id="fallback@example.com",
        webhook_url="https://flow.example.invalid/trigger",
        webhook_recipient="approver@example.com",
        recipient_policy="hitl-approvers",
        delivery_mode="all",
        mode="auto",
        destination_type="auto",
        dry_run=False,
        timeout=10,
        correlation_id="corr-adaptive-1",
        generated_at=datetime(2026, 7, 30, 19, 13, tzinfo=UTC),
    )

    assert captured["url"] == "https://flow.example.invalid/trigger"
    assert captured["body"]["to"] == "approver@example.com"
    assert captured["body"]["renderMode"] == "adaptive-card"
    assert captured["body"]["eventType"] == "hitl-approval-request"
    assert captured["body"]["correlationId"] == "corr-adaptive-1"
    assert captured["body"]["adaptiveCard"]["type"] == "AdaptiveCard"
    assert payload["notification"]["entregue"] is True
    assert payload["notification"]["canal_usado"] == "flow_bot_adaptive_direct"
    assert payload["direct_adaptive_route_configured"] is True
    assert payload["correlation_id"] == "corr-adaptive-1"


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
    assert payload["render_mode"] == "adaptive-card"
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
    assert payload["direct_adaptive_route_configured"] is False


def test_build_message_rejects_non_github_url():
    with pytest.raises(ValueError):
        module.build_message(
            request_title="Aprovar",
            control_id="REQSYS-HITL-001",
            summary="Resumo suficientemente claro.",
            request_url="https://example.com/request",
            evidence_url=None,
        )
