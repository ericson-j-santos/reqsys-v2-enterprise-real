"""Caminhos críticos adicionais — reqsys orchestrator."""

from app.services.reqsys_orchestrator import OrchestratorDemand, classificar_demanda


def test_classificador_usa_coordenador_padrao_sem_match():
    rota = classificar_demanda(OrchestratorDemand(
        titulo='xyzqwerty',
        descricao='lorem ipsum dolor sit amet consectetur',
    ))
    assert rota['score'] == 0
    assert rota['confianca'] == 0.45
    assert rota['coordinator']['id'] == 'reqsys-intake-coordinator'


def test_classificador_respeita_prioridade_informada():
    rota = classificar_demanda(OrchestratorDemand(
        titulo='Assunto genérico',
        descricao='Sem match',
        prioridade_informada='critica',
    ))
    assert rota['prioridade_sugerida'] == 'critica'
    assert 'prioridade-alta' in rota['labels']


def test_classificador_score_medio_define_prioridade_media():
    rota = classificar_demanda(OrchestratorDemand(
        titulo='Pipeline deploy',
        descricao='Validar pipeline e deploy com evidência.',
    ))
    assert rota['prioridade_sugerida'] in {'media', 'alta', 'normal'}
