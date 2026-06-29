from app.models.requisito import Requisito
from app.services.requisitos_maturidade import enriquecer_maturidade_requisitos


def _criar_requisitos(db_session, quantidade: int) -> None:
    for indice in range(quantidade):
        db_session.add(
            Requisito(
                codigo=f'REQ-MAT-{indice:03d}',
                titulo=f'Requisito {indice}',
                descricao='Descrição operacional inicial.',
                urgencia='media',
                area='TI',
                sistema='ReqSys',
                solicitante='tester',
                status='recebido',
            )
        )
    db_session.commit()


def test_enriquecer_maturidade_eleva_bdd_e_conclusao(db_session):
    _criar_requisitos(db_session, 20)

    resultado = enriquecer_maturidade_requisitos(db_session)

    assert resultado.total == 20
    assert resultado.cobertura_bdd_percentual >= 40
    assert resultado.conclusao_percentual >= 40
    assert resultado.distribuicao_status.get('aprovado', 0) >= 1
    assert resultado.distribuicao_status.get('em_analise', 0) >= 1


def test_enriquecer_maturidade_e_idempotente(db_session):
    _criar_requisitos(db_session, 12)
    primeiro = enriquecer_maturidade_requisitos(db_session)
    segundo = enriquecer_maturidade_requisitos(db_session)

    assert primeiro.atualizados_status > 0
    assert primeiro.atualizados_bdd > 0
    assert segundo.atualizados_status == 0
    assert segundo.atualizados_bdd == 0
