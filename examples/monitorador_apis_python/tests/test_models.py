from datetime import datetime

from app.domain.models import ResultadoMonitoramento


def test_deve_classificar_resultado_verde():
    resultado = ResultadoMonitoramento(
        nome="api",
        url="https://exemplo.com",
        status_code=200,
        sucesso=True,
        tempo_resposta_ms=900,
        erro=None,
        consultado_em=datetime.utcnow(),
    )

    assert resultado.status_operacional == "VERDE"


def test_deve_classificar_resultado_amarelo():
    resultado = ResultadoMonitoramento(
        nome="api",
        url="https://exemplo.com",
        status_code=200,
        sucesso=True,
        tempo_resposta_ms=2000,
        erro=None,
        consultado_em=datetime.utcnow(),
    )

    assert resultado.status_operacional == "AMARELO"


def test_deve_classificar_resultado_vermelho_quando_falha():
    resultado = ResultadoMonitoramento(
        nome="api",
        url="https://exemplo.com",
        status_code=500,
        sucesso=False,
        tempo_resposta_ms=100,
        erro="HTTP 500",
        consultado_em=datetime.utcnow(),
    )

    assert resultado.status_operacional == "VERMELHO"
