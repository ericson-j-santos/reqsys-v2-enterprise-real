from app.models.gestao_ti import RequisitoServico, ServicoTI
from app.models.requisito import Requisito
from app.services.gestao_ti_seed import REQSYS_SERVICO_ID, reconciliar_servico_reqsys


def _requisito() -> Requisito:
    return Requisito(
        codigo='REQ-SEED-001',
        titulo='Validar identidade canônica',
        descricao='Requisito usado para validar a preservação do vínculo durante a reconciliação.',
        urgencia='media',
        area='tecnologia',
        sistema='reqsys',
        solicitante='teste_seed',
        impacto_regulatorio=False,
    )


def test_seed_cria_uuid_canonico_e_e_idempotente(db_session):
    primeiro = reconciliar_servico_reqsys(db_session)
    segundo = reconciliar_servico_reqsys(db_session)

    assert primeiro.acao == 'criado'
    assert segundo.acao == 'atualizado'
    assert primeiro.servico_id == REQSYS_SERVICO_ID
    assert db_session.query(ServicoTI).filter(ServicoTI.codigo == 'REQSYS').count() == 1


def test_seed_migra_uuid_legado_preservando_vinculo(db_session):
    legado_id = '66c323cd-7b90-4899-8977-4d315594f4fb'
    legado = ServicoTI(
        servico_id=legado_id,
        codigo='REQSYS',
        nome='ReqSys',
        criticidade='alta',
        responsavel_tecnico='Equipe ReqSys',
        responsavel_negocio='Gestão de Produtos',
    )
    requisito = _requisito()
    db_session.add_all([legado, requisito])
    db_session.flush()
    db_session.add(
        RequisitoServico(
            requisito_id=requisito.id,
            servico_id=legado_id,
            criado_por='teste',
            correlation_id='corr-seed-legado',
        )
    )
    db_session.commit()

    resultado = reconciliar_servico_reqsys(db_session)
    db_session.expire_all()

    assert resultado.acao == 'migrado'
    assert resultado.vinculos_migrados == 1
    assert db_session.get(ServicoTI, legado_id) is None
    assert db_session.query(RequisitoServico).one().servico_id == REQSYS_SERVICO_ID
    assert db_session.get(ServicoTI, REQSYS_SERVICO_ID).codigo == 'REQSYS'
