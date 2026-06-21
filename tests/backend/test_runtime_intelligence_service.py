from app.models.operational_intelligence_models import SinalRuntime, StatusOperacional
from app.services.runtime_intelligence_service import RuntimeIntelligenceService


def test_diagnostico_saudavel_quando_sinais_estao_ok():
    diagnostico = RuntimeIntelligenceService().diagnosticar([
        SinalRuntime(
            nome="relatorio",
            sucesso=True,
            latencia_ms=100,
            retries=0,
            falhas_consecutivas=0,
            criticidade="alta",
        )
    ])

    assert diagnostico.status == StatusOperacional.saudavel
    assert diagnostico.score == 100


def test_diagnostico_bloqueia_sem_sinais():
    diagnostico = RuntimeIntelligenceService().diagnosticar([])

    assert diagnostico.status == StatusOperacional.bloqueado
    assert diagnostico.score == 0
    assert diagnostico.riscos
