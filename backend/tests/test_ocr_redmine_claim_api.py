from fastapi import HTTPException
import pytest

from app.api import ocr_review
from app.ocr.redmine import ImportedRedmineAttachment, RedmineAttachment
from app.services.runtime_core import RuntimeDeliveryResult, RuntimeEventStatus


class RepoFake:
    def __init__(self):
        self.items = {}

    def obter(self, job_id, *, revelar_pii=False):
        assert revelar_pii is False
        return self.items.get(job_id)


class ClaimsFake:
    def __init__(self, acquire=True):
        self.acquire = acquire
        self.acquired = []
        self.released = []

    def adquirir(self, job_id, owner_token):
        self.acquired.append((job_id, owner_token))
        return self.acquire

    def liberar(self, job_id, owner_token):
        self.released.append((job_id, owner_token))
        return True


class ClientFake:
    attachment = RedmineAttachment(
        attachment_id=77,
        filename='documento.pdf',
        content_url='https://redmine.example/attachments/77',
        filesize=100,
    )
    imported = ImportedRedmineAttachment(
        issue_id=42,
        attachment_id=77,
        document_ref='redmine/42/attachment-77-0123456789abcdef.pdf',
        sha256='0123456789abcdef' * 4,
        size_bytes=100,
        tipo_documento='REDMINE_PDF',
    )

    def list_attachments(self, issue_id):
        assert issue_id == 42
        return [self.attachment]

    def import_attachment(self, issue_id, attachment, *, input_root):
        assert issue_id == 42
        assert attachment.attachment_id == 77
        return self.imported


class BusFake:
    def __init__(self, repo):
        self.repo = repo
        self.calls = 0

    def publish(self, envelope):
        self.calls += 1
        self.repo.items[envelope.aggregate_id] = {
            'job_id': envelope.aggregate_id,
            'status_revisao': 'PENDENTE',
            'pii_exposta': False,
        }
        return [RuntimeDeliveryResult(
            event_id=envelope.event_id,
            handler_name='fake',
            status=RuntimeEventStatus.DELIVERED,
            attempts=1,
        )]


def _prepare(monkeypatch, repo, claims):
    monkeypatch.setenv('OCR_INPUT_ROOT', '/tmp/ocr-redmine')
    monkeypatch.setattr(ocr_review, '_repo', lambda: repo)
    monkeypatch.setattr(ocr_review, '_claims', lambda: claims)
    monkeypatch.setattr(ocr_review, 'RedmineAttachmentClient', ClientFake)


def test_segunda_execucao_com_claim_ativo_nao_dispara_ocr(monkeypatch):
    repo = RepoFake()
    claims = ClaimsFake(acquire=False)
    _prepare(monkeypatch, repo, claims)
    monkeypatch.setattr(
        ocr_review,
        '_runtime_ocr',
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('worker não deve iniciar')),
    )

    response = ocr_review.processar_anexos_redmine(
        42,
        ocr_review.OcrRedmineAttachmentsRequest(),
        user={'sub': 'admin'},
        x_correlation_id='corr-concorrente',
    )

    assert response['data']['processed_count'] == 0
    assert response['data']['in_progress_count'] == 1
    assert response['data']['failed_count'] == 0
    assert response['data']['distributed_claim'] is True
    assert response['data']['items'][0]['status'] == 'EM_PROCESSAMENTO'
    assert len(claims.acquired) == 1
    assert claims.released == []


def test_dono_do_claim_processa_e_libera_em_estado_terminal(monkeypatch):
    repo = RepoFake()
    claims = ClaimsFake(acquire=True)
    bus = BusFake(repo)
    _prepare(monkeypatch, repo, claims)
    monkeypatch.setattr(ocr_review, '_runtime_ocr', lambda *_args: bus)

    response = ocr_review.processar_anexos_redmine(
        42,
        ocr_review.OcrRedmineAttachmentsRequest(),
        user={'sub': 'admin'},
        x_correlation_id='corr-owner',
    )

    assert response['data']['processed_count'] == 1
    assert response['data']['in_progress_count'] == 0
    assert bus.calls == 1
    assert len(claims.acquired) == 1
    assert len(claims.released) == 1
    assert claims.acquired[0] == claims.released[0]


def test_claim_e_liberado_mesmo_quando_worker_falha(monkeypatch):
    repo = RepoFake()
    claims = ClaimsFake(acquire=True)
    _prepare(monkeypatch, repo, claims)

    class BrokenBus:
        def publish(self, envelope):
            return [RuntimeDeliveryResult(
                event_id=envelope.event_id,
                handler_name='fake',
                status=RuntimeEventStatus.DEAD_LETTER,
                attempts=3,
                error='falha simulada',
            )]

    monkeypatch.setattr(ocr_review, '_runtime_ocr', lambda *_args: BrokenBus())

    with pytest.raises(HTTPException) as exc:
        ocr_review.processar_anexos_redmine(
            42,
            ocr_review.OcrRedmineAttachmentsRequest(),
            user={'sub': 'admin'},
            x_correlation_id='corr-falha',
        )

    assert exc.value.status_code == 422
    assert exc.value.detail['code'] == 'OCR_REDMINE_ATTACHMENTS_PARTIAL_FAILURE'
    assert len(claims.acquired) == 1
    assert claims.acquired[0] == claims.released[0]
