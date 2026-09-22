import base64

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.ocr.storage import OcrDataProtector, OcrResultadoPersistido, RepositorioResultadosOcrSqlAlchemy
from app.ocr.worker import OcrResultado


def _repo():
    engine = create_engine('sqlite:///:memory:')
    OcrResultadoPersistido.__table__.create(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    key = base64.b64encode(b'K' * 32).decode('ascii')
    return RepositorioResultadosOcrSqlAlchemy(
        session_factory=factory,
        protector=OcrDataProtector(key, key_version='test-v1'),
    ), factory


def _resultado(estado='VALIDACAO_ADICIONAL'):
    return OcrResultado(
        job_id='ocr-test-001',
        correlation_id='corr-001',
        tipo_documento='CIN',
        campo='nome',
        estado_ocr=estado,
        confianca=0.94,
        valor='MARIA APARECIDA SILVA',
        motivos=('confiança abaixo do limiar AUTO',),
    )


def test_pii_nao_fica_em_plaintext_e_lista_nao_revela_valor():
    repo, factory = _repo()
    repo.salvar(_resultado())

    with factory() as db:
        item = db.scalar(select(OcrResultadoPersistido))
        assert item is not None
        assert 'MARIA APARECIDA SILVA' not in item.payload_protegido
        assert item.key_version == 'test-v1'

    lista = repo.listar(status='PENDENTE')
    assert len(lista) == 1
    assert 'valor' not in lista[0]
    assert lista[0]['pii_exposta'] is False

    detalhe = repo.obter('ocr-test-001', revelar_pii=True)
    assert detalhe['valor'] == 'MARIA APARECIDA SILVA'
    assert detalhe['motivos']


def test_decisao_humana_e_idempotencia_de_estado():
    repo, _factory = _repo()
    repo.salvar(_resultado())
    decidido = repo.decidir(
        'ocr-test-001',
        decisao='APROVADO',
        reviewer='reviewer@example.invalid',
        observacao='Conferido visualmente.',
    )
    assert decidido['status_revisao'] == 'APROVADO'
    assert 'reviewer' not in decidido

    with pytest.raises(ValueError, match='não está pendente'):
        repo.decidir('ocr-test-001', decisao='REJEITADO', reviewer='outro')


def test_auto_nao_entra_na_fila_humana():
    repo, _factory = _repo()
    repo.salvar(_resultado(estado='AUTO'))
    assert repo.listar(status='PENDENTE') == []
    assert repo.obter('ocr-test-001')['status_revisao'] == 'AUTO'


def test_chave_invalida_falha_fechado():
    with pytest.raises(RuntimeError, match='32 bytes'):
        OcrDataProtector(base64.b64encode(b'curta').decode('ascii'))
