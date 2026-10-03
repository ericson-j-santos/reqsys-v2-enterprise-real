"""Testes de caminhos críticos — runtime intelligence e operação autônoma."""

from fastapi.testclient import TestClient

from app.main import app
from app.models.operational_intelligence_models import (
    DiagnosticoRuntime,
    SinalRuntime,
    StatusOperacional,
)
from app.services.autonomous_operation_service import AutonomousOperationService
from app.services.runtime_intelligence_service import RuntimeIntelligenceService

client = TestClient(app)
_runtime = RuntimeIntelligenceService()
_autonomous = AutonomousOperationService()


def _sinal(**overrides) -> SinalRuntime:
    base = {
        "nome": "pipeline-ci",
        "sucesso": True,
        "latencia_ms": 120,
        "retries": 0,
        "falhas_consecutivas": 0,
        "criticidade": "media",
    }
    base.update(overrides)
    return SinalRuntime(**base)


def test_diagnosticar_sem_sinais_bloqueia_operacao():
    diagnostico = _runtime.diagnosticar([])

    assert diagnostico.status == StatusOperacional.bloqueado
    assert diagnostico.score == 0
    assert "Nenhum sinal operacional recebido." in diagnostico.riscos


def test_diagnosticar_sinal_saudavel_mantem_score_alto():
    diagnostico = _runtime.diagnosticar([_sinal()])

    assert diagnostico.status == StatusOperacional.saudavel
    assert diagnostico.score == 100
    assert diagnostico.riscos == []
    assert "Manter monitoramento" in diagnostico.recomendacoes[0]


def test_diagnosticar_falha_alta_criticidade_penaliza_score():
    diagnostico = _runtime.diagnosticar([_sinal(sucesso=False, criticidade="alta")])

    assert diagnostico.score == 75
    assert diagnostico.status == StatusOperacional.atencao
    assert any("falha operacional" in risco for risco in diagnostico.riscos)


def test_diagnosticar_latencia_e_retries_degradam_score():
    diagnostico = _runtime.diagnosticar(
        [_sinal(latencia_ms=6000, retries=3, falhas_consecutivas=3)]
    )

    assert diagnostico.score == 50
    assert diagnostico.status == StatusOperacional.degradado
    assert len(diagnostico.riscos) == 3


def test_recomendar_acao_por_status_operacional():
    casos = [
        (StatusOperacional.saudavel, "CONTINUAR_MONITORAMENTO", False),
        (StatusOperacional.atencao, "REEXECUTAR_VALIDACOES", False),
        (StatusOperacional.degradado, "ABRIR_INCIDENTE_E_BLOQUEAR_PROMOCAO", True),
        (StatusOperacional.bloqueado, "BLOQUEAR_OPERACAO", True),
    ]
    for status, acao, exige_aprovacao in casos:
        diagnostico = DiagnosticoRuntime(status=status, score=50, riscos=[], recomendacoes=[])
        resultado = _autonomous.recomendar_acao(diagnostico)

        assert resultado["acao"] == acao
        assert resultado["exige_aprovacao"] is exige_aprovacao
        assert resultado["autonomo"] is True


def test_runtime_health_endpoint_expoe_capabilities():
    correlation_id = "corr-runtime-health-critical"
    res = client.get(
        "/monitoramento-operacional/runtime/health",
        headers={"X-Correlation-ID": correlation_id},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "SAUDAVEL"
    assert body["correlation_id"] == correlation_id
    assert "runtime-intelligence" in body["capabilities"]


def test_runtime_diagnostico_endpoint_integra_servicos():
    correlation_id = "corr-runtime-diagnostico-critical"
    res = client.post(
        "/monitoramento-operacional/runtime/diagnostico",
        headers={"X-Correlation-ID": correlation_id},
        json=[
            {
                "nome": "deploy-prod",
                "sucesso": False,
                "latencia_ms": 8000,
                "retries": 4,
                "falhas_consecutivas": 4,
                "criticidade": "alta",
            }
        ],
    )

    assert res.status_code == 200
    body = res.json()
    assert body["correlation_id"] == correlation_id
    assert body["diagnostico"]["status"] == StatusOperacional.bloqueado.value
    assert body["acao_recomendada"]["acao"] == "BLOQUEAR_OPERACAO"
    assert body["acao_recomendada"]["exige_aprovacao"] is True
