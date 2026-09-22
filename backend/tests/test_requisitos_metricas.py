from app.models.requisito import Requisito
from app.services.requisitos_metricas import calcular_metricas_requisitos


def test_calcular_metricas_requisitos_vazio(db_session):
    metricas = calcular_metricas_requisitos(db_session)
    assert metricas == {
        'total': 0,
        'em_analise': 0,
        'aprovados': 0,
        'rejeitados': 0,
        'pendentes': 0,
    }


def test_calcular_metricas_requisitos_distribuicao(db_session):
    db_session.add_all([
        Requisito(
            codigo='REQ-MET-001',
            titulo='Recebido',
            descricao='desc',
            urgencia='media',
            area='TI',
            sistema='ReqSys',
            solicitante='tester',
            status='recebido',
        ),
        Requisito(
            codigo='REQ-MET-002',
            titulo='Em análise',
            descricao='desc',
            urgencia='media',
            area='TI',
            sistema='ReqSys',
            solicitante='tester',
            status='em_analise',
        ),
        Requisito(
            codigo='REQ-MET-003',
            titulo='Aprovado',
            descricao='desc',
            urgencia='media',
            area='TI',
            sistema='ReqSys',
            solicitante='tester',
            status='aprovado',
        ),
        Requisito(
            codigo='REQ-MET-004',
            titulo='Rejeitado',
            descricao='desc',
            urgencia='media',
            area='TI',
            sistema='ReqSys',
            solicitante='tester',
            status='rejeitado',
        ),
    ])
    db_session.commit()

    metricas = calcular_metricas_requisitos(db_session)
    assert metricas['total'] == 4
    assert metricas['em_analise'] == 1
    assert metricas['aprovados'] == 1
    assert metricas['rejeitados'] == 1
    assert metricas['pendentes'] == 1


def test_calcular_metricas_requisitos_backlog_conta_como_em_analise(db_session):
    db_session.add(
        Requisito(
            codigo='REQ-MET-005',
            titulo='Publicado no Redmine',
            descricao='desc',
            urgencia='media',
            area='TI',
            sistema='ReqSys',
            solicitante='tester',
            status='backlog',
        )
    )
    db_session.commit()

    metricas = calcular_metricas_requisitos(db_session)
    assert metricas['total'] == 1
    assert metricas['em_analise'] == 1
    assert metricas['pendentes'] == 0
