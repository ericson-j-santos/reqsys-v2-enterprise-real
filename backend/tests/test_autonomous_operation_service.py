from app.models.operational_intelligence_models import DiagnosticoRuntime, StatusOperacional
from app.services.autonomous_operation_service import AutonomousOperationService


def test_estado_bloqueado_exige_aprovacao():
    diagnostico = DiagnosticoRuntime(
        status=StatusOperacional.bloqueado,
        score=10,
        riscos=["falha crítica"],
        recomendacoes=["bloquear"],
    )

    acao = AutonomousOperationService().recomendar_acao(diagnostico)

    assert acao["acao"] == "BLOQUEAR_OPERACAO"
    assert acao["exige_aprovacao"] is True


def test_estado_saudavel_pode_continuar_monitoramento():
    diagnostico = DiagnosticoRuntime(
        status=StatusOperacional.saudavel,
        score=100,
        riscos=[],
        recomendacoes=["monitorar"],
    )

    acao = AutonomousOperationService().recomendar_acao(diagnostico)

    assert acao["acao"] == "CONTINUAR_MONITORAMENTO"
    assert acao["exige_aprovacao"] is False
