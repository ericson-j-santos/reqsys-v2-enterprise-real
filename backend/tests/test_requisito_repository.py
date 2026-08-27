"""Testes do RequisitoRepository — porta de acesso a dados consolidada (ADR-001)."""

from app.models.orchestrator import OrchestratorRoutingEvent
from app.models.requisito import Requisito
from app.repositories.requisito_repository import RequisitoRepository


def _criar(db_session, **overrides) -> Requisito:
    base = {
        'codigo': 'REQ-REPO-001',
        'titulo': 'Requisito de teste',
        'descricao': 'Descricao operacional',
        'urgencia': 'media',
        'area': 'TI',
        'sistema': 'ReqSys',
        'solicitante': 'tester',
        'status': 'recebido',
    }
    base.update(overrides)
    requisito = Requisito(**base)
    db_session.add(requisito)
    db_session.commit()
    return requisito


def test_contar_total_vazio_e_apos_insercao(db_session):
    repo = RequisitoRepository(db_session)
    assert repo.contar_total() == 0

    _criar(db_session)
    assert repo.contar_total() == 1


def test_contar_por_status_in_case_insensitive(db_session):
    _criar(db_session, codigo='REQ-REPO-002', status='Aprovado')
    _criar(db_session, codigo='REQ-REPO-003', status='recebido')
    repo = RequisitoRepository(db_session)

    assert repo.contar_por_status_in({'aprovado', 'concluido'}) == 1


def test_contar_por_status_in_ou_contendo(db_session):
    _criar(db_session, codigo='REQ-REPO-004', status='em_analise')
    _criar(db_session, codigo='REQ-REPO-005', status='reanalise_tecnica')
    _criar(db_session, codigo='REQ-REPO-006', status='recebido')
    repo = RequisitoRepository(db_session)

    assert repo.contar_por_status_in_ou_contendo({'em_analise'}, 'analise') == 2


def test_contar_com_descricao_minima(db_session):
    _criar(db_session, codigo='REQ-REPO-007', descricao='curta')
    _criar(db_session, codigo='REQ-REPO-008', descricao='x' * 50)
    repo = RequisitoRepository(db_session)

    assert repo.contar_com_descricao_minima(40) == 1


def test_listar_todos_respeita_ordenacao(db_session):
    _criar(db_session, codigo='REQ-REPO-009')
    _criar(db_session, codigo='REQ-REPO-010')
    repo = RequisitoRepository(db_session)

    asc = repo.listar_todos(ordenar_por_id='asc')
    desc = repo.listar_todos(ordenar_por_id='desc')

    assert [r.id for r in asc] == sorted(r.id for r in asc)
    assert [r.id for r in desc] == sorted((r.id for r in desc), reverse=True)
    assert len(repo.listar_todos()) == 2


def test_buscar_por_id_e_por_codigo(db_session):
    criado = _criar(db_session, codigo='REQ-REPO-011')
    repo = RequisitoRepository(db_session)

    assert repo.buscar_por_id(criado.id).codigo == 'REQ-REPO-011'
    assert repo.buscar_por_codigo('REQ-REPO-011').id == criado.id
    assert repo.buscar_por_id(999999) is None
    assert repo.buscar_por_codigo('INEXISTENTE') is None


def test_buscar_por_codigo_ou_id(db_session):
    criado = _criar(db_session, codigo='REQ-REPO-012')
    repo = RequisitoRepository(db_session)

    assert repo.buscar_por_codigo_ou_id('REQ-REPO-012').id == criado.id
    assert repo.buscar_por_codigo_ou_id(str(criado.id)).codigo == 'REQ-REPO-012'
    assert repo.buscar_por_codigo_ou_id('nao-existe') is None


def test_buscar_com_filtro_texto(db_session):
    _criar(db_session, codigo='REQ-REPO-013', titulo='Pipeline de dados quebrado')
    _criar(db_session, codigo='REQ-REPO-014', titulo='Outro assunto qualquer')
    repo = RequisitoRepository(db_session)

    resultados = repo.buscar_com_filtro_texto('pipeline')
    assert len(resultados) == 1
    assert resultados[0].codigo == 'REQ-REPO-013'

    assert len(repo.buscar_com_filtro_texto(None)) == 2


def test_criar_inicia_refinamento_e_roteia_orquestrador(db_session):
    repo = RequisitoRepository(db_session)
    requisito = repo.criar(
        'REQ-REPO-015',
        titulo='Novo requisito',
        descricao='Descricao inicial ainda sem criterios de aceite suficientes.',
        urgencia='alta',
        area='TI',
        sistema='ReqSys',
        solicitante='tester',
    )

    assert requisito.id is not None
    assert requisito.status == 'refinamento'
    assert repo.buscar_por_codigo('REQ-REPO-015').status == 'refinamento'

    evento = db_session.query(OrchestratorRoutingEvent).one()
    assert evento.origem == 'cadastro_requisito'
    assert evento.coordinator_id.startswith('reqsys-')
    assert evento.prioridade == 'alta'
    assert evento.score >= 0
    assert 0.0 <= evento.confianca <= 1.0
    assert len(evento.payload_hash) == 64


def test_criar_preserva_status_quando_fluxo_governado_informa_explicitamente(db_session):
    repo = RequisitoRepository(db_session)
    requisito = repo.criar(
        'REQ-REPO-016',
        titulo='Requisito já governado',
        descricao='Entrada originada por fluxo que controla explicitamente a máquina de estados.',
        urgencia='media',
        area='TI',
        sistema='ReqSys',
        solicitante='tester',
        status='recebido',
    )

    assert requisito.status == 'recebido'
    assert db_session.query(OrchestratorRoutingEvent).count() == 0
