from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import ocr_review
from app.services.runtime_core import RuntimeDeliveryResult, RuntimeEventStatus


class RepoFake:
    def __init__(self):
        self.item = {
            'job_id': 'ocr-test-001',
            'status_revisao': 'PENDENTE',
            'estado_ocr': 'VALIDACAO_ADICIONAL',
            'confianca': 0.94,
        }
        self.decisoes = []

    def listar(self, *, status=None, limite=100):
        assert status == 'PENDENTE'
        assert limite == 25
        return [self.item]

    def obter(self, job_id, *, revelar_pii=False):
        if job_id == 'nao-existe':
            return None
        item = dict(self.item)
        if revelar_pii:
            item['valor'] = 'NOME TESTE'
            item['motivos'] = ['baixa confiança']
        return item

    def decidir(self, job_id, *, decisao, reviewer, observacao=''):
        if job_id == 'nao-existe':
            raise LookupError('resultado OCR não encontrado')
        if job_id == 'decidido':
            raise ValueError('resultado não está pendente de revisão: APROVADO')
        self.decisoes.append((job_id, decisao, reviewer, observacao))
        return {**self.item, 'job_id': job_id, 'status_revisao': decisao}


class BusFake:
    status = RuntimeEventStatus.DELIVERED
    error = None

    def __init__(self):
        self.envelopes = []

    def publish(self, envelope):
        self.envelopes.append(envelope)
        return [RuntimeDeliveryResult(
            event_id=envelope.event_id,
            handler_name='ocr-worker-fake',
            status=self.status,
            attempts=1,
            error=self.error,
        )]


def test_repo_falha_fechado_quando_chave_nao_esta_pronta(monkeypatch):
    class FalhaRepo:
        def __init__(self):
            raise RuntimeError('OCR_DATA_ENCRYPTION_KEY não configurada')

    monkeypatch.setattr(ocr_review, 'RepositorioResultadosOcrSqlAlchemy', FalhaRepo)
    with pytest.raises(HTTPException) as exc:
        ocr_review._repo()
    assert exc.value.status_code == 503
    assert 'OCR_STORE_NOT_READY' in exc.value.detail


def test_readiness_combina_store_e_input_root(monkeypatch):
    monkeypatch.setattr(ocr_review, 'ocr_store_readiness', lambda: {
        'ready': True,
        'encryption': 'AES-256-GCM',
        'key_configured': True,
        'plaintext_storage_allowed': False,
    })
    monkeypatch.setenv('OCR_INPUT_ROOT', '/tmp/ocr-input')
    response = ocr_review.readiness_ocr()
    assert response['data']['ready'] is True
    assert response['data']['input_root_configured'] is True
    assert response['data']['engine_language'] == 'por'


def test_readiness_bloqueia_sem_input_root(monkeypatch):
    monkeypatch.setattr(ocr_review, 'ocr_store_readiness', lambda: {'ready': True, 'key_configured': True})
    monkeypatch.delenv('OCR_INPUT_ROOT', raising=False)
    response = ocr_review.readiness_ocr()
    assert response['data']['ready'] is False
    assert response['data']['input_root_configured'] is False


def test_listagem_nao_revela_pii(monkeypatch):
    repo = RepoFake()
    monkeypatch.setattr(ocr_review, '_repo', lambda: repo)
    response = ocr_review.listar_revisao_ocr(status='PENDENTE', limite=25, user={'sub': 'admin'})
    assert response['data']['count'] == 1
    assert response['data']['pii_exposta'] is False
    assert 'valor' not in response['data']['items'][0]


def test_detalhe_revela_pii_somente_no_endpoint_autenticado(monkeypatch):
    repo = RepoFake()
    monkeypatch.setattr(ocr_review, '_repo', lambda: repo)
    response = ocr_review.detalhar_revisao_ocr('ocr-test-001', user={'sub': 'admin'})
    assert response['data']['valor'] == 'NOME TESTE'
    assert response['data']['pii_exposta'] is True
    assert 'não registrar em logs' in response['data']['exposicao']


def test_detalhe_inexistente_retorna_404(monkeypatch):
    monkeypatch.setattr(ocr_review, '_repo', lambda: RepoFake())
    with pytest.raises(HTTPException) as exc:
        ocr_review.detalhar_revisao_ocr('nao-existe', user={'sub': 'admin'})
    assert exc.value.status_code == 404


def test_decisao_persiste_revisor_e_observacao(monkeypatch):
    repo = RepoFake()
    monkeypatch.setattr(ocr_review, '_repo', lambda: repo)
    payload = ocr_review.OcrDecisionRequest(decisao='APROVADO', observacao='Conferido visualmente')
    response = ocr_review.decidir_revisao_ocr(
        'ocr-test-001', payload, user={'sub': 'admin-123', 'email': 'nao-usar@example.invalid'}
    )
    assert response['data']['status_revisao'] == 'APROVADO'
    assert repo.decisoes == [('ocr-test-001', 'APROVADO', 'admin-123', 'Conferido visualmente')]


def test_decisao_mapeia_nao_encontrado_e_conflito(monkeypatch):
    monkeypatch.setattr(ocr_review, '_repo', lambda: RepoFake())
    payload = ocr_review.OcrDecisionRequest(decisao='REJEITADO')
    with pytest.raises(HTTPException) as missing:
        ocr_review.decidir_revisao_ocr('nao-existe', payload, user={'email': 'admin@example.invalid'})
    assert missing.value.status_code == 404
    with pytest.raises(HTTPException) as conflict:
        ocr_review.decidir_revisao_ocr('decidido', payload, user={'email': 'admin@example.invalid'})
    assert conflict.value.status_code == 409


def test_criar_job_exige_input_root(monkeypatch):
    monkeypatch.delenv('OCR_INPUT_ROOT', raising=False)
    payload = ocr_review.OcrJobRequest(document_ref='doc.png', tipo_documento='CIN')
    with pytest.raises(HTTPException) as exc:
        ocr_review.criar_job_ocr(payload, user={'sub': 'admin'}, x_correlation_id='corr-001')
    assert exc.value.status_code == 503


def test_criar_job_publica_evento_e_retorna_metadata(monkeypatch):
    repo = RepoFake()
    monkeypatch.setenv('OCR_INPUT_ROOT', '/tmp/ocr-input')
    monkeypatch.setattr(ocr_review, '_repo', lambda: repo)
    monkeypatch.setattr(ocr_review, 'RuntimeEventBus', BusFake)
    monkeypatch.setattr(ocr_review, 'registrar_ocr_worker', lambda bus, worker: None)
    monkeypatch.setattr(ocr_review, 'MotorOcrEvidencia', lambda: SimpleNamespace())
    monkeypatch.setattr(ocr_review, 'OcrWorker', lambda *args, **kwargs: SimpleNamespace())
    payload = ocr_review.OcrJobRequest(
        document_ref='entrada/doc.png',
        tipo_documento='CIN',
        recorte=(1, 2, 300, 80),
    )
    response = ocr_review.criar_job_ocr(payload, user={'sub': 'admin'}, x_correlation_id='corr-001')
    assert response['data']['status_revisao'] == 'PENDENTE'
    assert response['correlation_id'] == 'corr-001'


def test_criar_job_mapeia_dlq_para_422(monkeypatch):
    class BusDlq(BusFake):
        status = RuntimeEventStatus.DEAD_LETTER
        error = 'documento inválido'

    monkeypatch.setenv('OCR_INPUT_ROOT', '/tmp/ocr-input')
    monkeypatch.setattr(ocr_review, '_repo', lambda: RepoFake())
    monkeypatch.setattr(ocr_review, 'RuntimeEventBus', BusDlq)
    monkeypatch.setattr(ocr_review, 'registrar_ocr_worker', lambda bus, worker: None)
    monkeypatch.setattr(ocr_review, 'MotorOcrEvidencia', lambda: SimpleNamespace())
    monkeypatch.setattr(ocr_review, 'OcrWorker', lambda *args, **kwargs: SimpleNamespace())
    payload = ocr_review.OcrJobRequest(document_ref='doc.png')
    with pytest.raises(HTTPException) as exc:
        ocr_review.criar_job_ocr(payload, user={'sub': 'admin'}, x_correlation_id=None)
    assert exc.value.status_code == 422
    assert exc.value.detail['code'] == 'OCR_PROCESSING_FAILED'
    assert exc.value.detail['status'] == 'dead_letter'


def test_criar_job_mapeia_falha_transiente_para_503(monkeypatch):
    class BusFailed(BusFake):
        status = RuntimeEventStatus.FAILED
        error = 'falha transitória'

    monkeypatch.setenv('OCR_INPUT_ROOT', '/tmp/ocr-input')
    monkeypatch.setattr(ocr_review, '_repo', lambda: RepoFake())
    monkeypatch.setattr(ocr_review, 'RuntimeEventBus', BusFailed)
    monkeypatch.setattr(ocr_review, 'registrar_ocr_worker', lambda bus, worker: None)
    monkeypatch.setattr(ocr_review, 'MotorOcrEvidencia', lambda: SimpleNamespace())
    monkeypatch.setattr(ocr_review, 'OcrWorker', lambda *args, **kwargs: SimpleNamespace())
    payload = ocr_review.OcrJobRequest(document_ref='doc.png')
    with pytest.raises(HTTPException) as exc:
        ocr_review.criar_job_ocr(payload, user={'sub': 'admin'}, x_correlation_id='corr-fail')
    assert exc.value.status_code == 503
    assert exc.value.detail['status'] == 'failed'
