"""Testes de caminhos críticos — prontidão de processos."""

from app.schemas.processos import ContextoAntecipacao, TipoProcesso, UsuarioExecucao
from app.services.prontidao import antecipar_validacoes, calcular_score_prontidao


def _contexto(**overrides):
    base = {
        "tipo_processo": TipoProcesso.DEMANDA,
        "acao": "iniciar",
        "usuario": UsuarioExecucao(id="u1", perfil="admin", escopos=["demanda:iniciar"]),
        "dados": {
            "titulo": "Titulo",
            "descricao": "Descricao",
            "responsavel": "time",
            "prioridade": "alta",
            "evidencias": [{"tipo": "doc", "referencia": "DOC-1"}],
            "criterio_aceite": "Aceite definido",
            "valor_negocio": "Alto",
        },
        "correlation_id": "corr-prontidao",
    }
    base.update(overrides)
    return ContextoAntecipacao(**base)


def test_antecipar_servico_sem_evidencia_aprova_com_alerta():
    resultado = antecipar_validacoes(
        _contexto(
            tipo_processo=TipoProcesso.SERVICO,
            usuario=UsuarioExecucao(id="u1", perfil="admin", escopos=["servico:iniciar"]),
            dados={
                "titulo": "Servico",
                "descricao": "Desc",
                "responsavel": "time",
                "prioridade": "media",
            },
        )
    )

    assert resultado.apto_para_iniciar is True
    assert resultado.status_validacao == "aprovado_com_alerta"
    assert any(alerta.codigo == "SERVICO_SEM_EVIDENCIA" for alerta in resultado.alertas)
    assert any(alerta.codigo == "SLA_AUSENTE" for alerta in resultado.alertas)


def test_antecipar_dossie_incompleto_bloqueia():
    resultado = antecipar_validacoes(
        _contexto(
            tipo_processo=TipoProcesso.DOSSIE,
            usuario=UsuarioExecucao(id="u1", perfil="admin", escopos=["dossie:iniciar"]),
            dados={
                "titulo": "Dossie",
                "descricao": "Desc",
                "responsavel": "time",
                "prioridade": "alta",
                "evidencias": [{"tipo": "doc", "referencia": "DOC-1"}],
                "documentos": [{"nome": "unico.pdf"}],
            },
        )
    )

    assert resultado.apto_para_iniciar is False
    assert resultado.status_validacao == "bloqueado"
    assert any(bloqueio.codigo == "DOSSIE_INCOMPLETO" for bloqueio in resultado.bloqueios)


def test_antecipar_demanda_sem_criterio_aceite_bloqueia():
    dados = _contexto().dados.copy()
    dados.pop("criterio_aceite")
    resultado = antecipar_validacoes(_contexto(dados=dados))

    assert resultado.apto_para_iniciar is False
    assert any(bloqueio.codigo == "CRITERIO_ACEITE_AUSENTE" for bloqueio in resultado.bloqueios)


def test_calcular_score_prontidao_nao_fica_negativo():
    bloqueios = [_ for _ in range(6)]
    alertas = [_ for _ in range(4)]
    pendencias = [_ for _ in range(3)]

    assert calcular_score_prontidao(bloqueios, alertas, pendencias) == 0
