import hashlib
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import ocr_review
from app.ocr import redmine
from app.ocr.redmine import (
    ImportedRedmineAttachment,
    RedmineAttachment,
    RedmineAttachmentClient,
    RedmineAttachmentError,
    RedmineAttachmentUnsupported,
)
from app.services.runtime_core import RuntimeDeliveryResult, RuntimeEventStatus


class FakeResponse:
    def __init__(self, payload: bytes, url: str, *, headers: dict[str, str] | None = None):
        self.payload = payload
        self.url = url
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def geturl(self):
        return self.url

    def read(self, size: int = -1):
        if size is None or size < 0:
            return self.payload
        return self.payload[:size]


def test_redmine_client_lista_e_materializa_pdf_com_sha_idempotente(monkeypatch, tmp_path):
    pdf = b'%PDF-1.7\nconteudo-ocr\n%%EOF'
    payload = json.dumps(
        {
            'issue': {
                'id': 42,
                'attachments': [
                    {
                        'id': 77,
                        'filename': '../../nome-sensivel.pdf',
                        'filesize': len(pdf),
                        'content_type': 'application/pdf',
                        'content_url': 'https://redmine.example/attachments/download/77/doc.pdf',
                    }
                ],
            }
        }
    ).encode('utf-8')
    responses = iter(
        [
            FakeResponse(payload, 'https://redmine.example/issues/42.json?include=attachments'),
            FakeResponse(pdf, 'https://redmine.example/attachments/download/77/doc.pdf'),
            FakeResponse(pdf, 'https://redmine.example/attachments/download/77/doc.pdf'),
        ]
    )
    monkeypatch.setattr(redmine.request, 'urlopen', lambda req, timeout: next(responses))

    client = RedmineAttachmentClient(
        base_url='https://redmine.example',
        api_key='test-key',
        max_bytes=4096,
    )
    attachments = client.list_attachments(42)
    assert len(attachments) == 1

    first = client.import_attachment(42, attachments[0], input_root=tmp_path)
    second = client.import_attachment(42, attachments[0], input_root=tmp_path)

    expected_sha = hashlib.sha256(pdf).hexdigest()
    assert first == second
    assert first.sha256 == expected_sha
    assert first.document_ref == f'redmine/42/attachment-77-{expected_sha[:16]}.pdf'
    assert 'nome-sensivel' not in first.document_ref
    assert (tmp_path / first.document_ref).read_bytes() == pdf


def test_redmine_client_rejeita_content_url_fora_da_origem(tmp_path):
    client = RedmineAttachmentClient(
        base_url='https://redmine.example',
        api_key='test-key',
        max_bytes=4096,
    )
    attachment = RedmineAttachment(
        attachment_id=7,
        filename='doc.pdf',
        content_url='https://attacker.invalid/doc.pdf',
        filesize=100,
    )
    with pytest.raises(RedmineAttachmentError, match='origem não autorizada'):
        client.import_attachment(1, attachment, input_root=tmp_path)


def test_redmine_client_rejeita_formato_nao_suportado(tmp_path):
    client = RedmineAttachmentClient(
        base_url='https://redmine.example',
        api_key='test-key',
        max_bytes=4096,
    )
    attachment = RedmineAttachment(
        attachment_id=8,
        filename='planilha.xlsx',
        content_url='https://redmine.example/attachments/8',
        filesize=100,
    )
    with pytest.raises(RedmineAttachmentUnsupported, match='formato não suportado'):
        client.import_attachment(1, attachment, input_root=tmp_path)


def test_redmine_client_rejeita_assinatura_incompativel(monkeypatch, tmp_path):
    monkeypatch.setattr(
        redmine.request,
        'urlopen',
        lambda req, timeout: FakeResponse(b'MZ!!', 'https://redmine.example/attachments/9'),
    )
    client = RedmineAttachmentClient(
        base_url='https://redmine.example',
        api_key='test-key',
        max_bytes=4096,
    )
    attachment = RedmineAttachment(
        attachment_id=9,
        filename='falso.pdf',
        content_url='https://redmine.example/attachments/9',
        filesize=4,
    )
    with pytest.raises(RedmineAttachmentError, match='assinatura binária incompatível'):
        client.import_attachment(1, attachment, input_root=tmp_path)


def test_redmine_client_aplica_limite_antes_do_download(monkeypatch, tmp_path):
    called = False

    def never_called(req, timeout):
        nonlocal called
        called = True
        raise AssertionError('download não deveria ser iniciado')

    monkeypatch.setattr(redmine.request, 'urlopen', never_called)
    client = RedmineAttachmentClient(
        base_url='https://redmine.example',
        api_key='test-key',
        max_bytes=10,
    )
    attachment = RedmineAttachment(
        attachment_id=10,
        filename='grande.pdf',
        content_url='https://redmine.example/attachments/10',
        filesize=11,
    )
    with pytest.raises(RedmineAttachmentError, match='excede limite'):
        client.import_attachment(1, attachment, input_root=tmp_path)
    assert called is False


class RepoFake:
    def __init__(self, existing: dict[str, dict] | None = None):
        self.items = dict(existing or {})

    def obter(self, job_id, *, revelar_pii=False):
        assert revelar_pii is False
        return self.items.get(job_id)


class BusFake:
    def __init__(self, repo: RepoFake):
        self.repo = repo
        self.envelopes = []

    def publish(self, envelope):
        self.envelopes.append(envelope)
        self.repo.items[envelope.aggregate_id] = {
            'job_id': envelope.aggregate_id,
            'status_revisao': 'PENDENTE',
            'estado_ocr': 'VALIDACAO_ADICIONAL',
            'confianca': 0.91,
            'pii_exposta': False,
        }
        return [
            RuntimeDeliveryResult(
                event_id=envelope.event_id,
                handler_name='ocr-worker-fake',
                status=RuntimeEventStatus.DELIVERED,
                attempts=1,
            )
        ]


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
        assert input_root == '/tmp/ocr-redmine'
        return self.imported


def test_api_redmine_publica_ocr_com_job_deterministico(monkeypatch):
    repo = RepoFake()
    bus = BusFake(repo)
    monkeypatch.setenv('OCR_INPUT_ROOT', '/tmp/ocr-redmine')
    monkeypatch.setattr(ocr_review, '_repo', lambda: repo)
    monkeypatch.setattr(ocr_review, 'RedmineAttachmentClient', ClientFake)
    monkeypatch.setattr(ocr_review, '_runtime_ocr', lambda repo_arg, input_root: bus)

    response = ocr_review.processar_anexos_redmine(
        42,
        ocr_review.OcrRedmineAttachmentsRequest(),
        user={'sub': 'admin'},
        x_correlation_id='corr-redmine-001',
    )

    assert response['meta']['correlation_id'] == 'corr-redmine-001'
    assert response['data']['processed_count'] == 1
    assert response['data']['failed_count'] == 0
    assert response['data']['pii_exposta'] is False
    assert len(bus.envelopes) == 1
    envelope = bus.envelopes[0]
    assert envelope.aggregate_id == 'ocr-redmine-42-77-0123456789abcdef'
    assert envelope.source == 'redmine.attachment'
    assert envelope.correlation_id == 'corr-redmine-001'
    assert envelope.payload['document_ref'] == ClientFake.imported.document_ref
    assert envelope.payload['sha256'] == ClientFake.imported.sha256
    assert 'filename' not in envelope.payload


def test_api_redmine_nao_reprocessa_mesmo_sha(monkeypatch):
    job_id = 'ocr-redmine-42-77-0123456789abcdef'
    repo = RepoFake(
        {
            job_id: {
                'job_id': job_id,
                'status_revisao': 'PENDENTE',
                'pii_exposta': False,
            }
        }
    )
    monkeypatch.setenv('OCR_INPUT_ROOT', '/tmp/ocr-redmine')
    monkeypatch.setattr(ocr_review, '_repo', lambda: repo)
    monkeypatch.setattr(ocr_review, 'RedmineAttachmentClient', ClientFake)
    monkeypatch.setattr(
        ocr_review,
        '_runtime_ocr',
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('OCR não deve executar novamente')),
    )

    response = ocr_review.processar_anexos_redmine(
        42,
        ocr_review.OcrRedmineAttachmentsRequest(),
        user={'sub': 'admin'},
        x_correlation_id='corr-redmine-replay',
    )

    assert response['data']['processed_count'] == 0
    assert response['data']['already_processed_count'] == 1
    assert response['data']['items'][0]['status'] == 'JA_PROCESSADO'


def test_api_redmine_falha_fechado_em_anexo_invalido(monkeypatch):
    class ClientInvalid(ClientFake):
        def import_attachment(self, issue_id, attachment, *, input_root):
            raise RedmineAttachmentError('assinatura inválida')

    monkeypatch.setenv('OCR_INPUT_ROOT', '/tmp/ocr-redmine')
    monkeypatch.setattr(ocr_review, '_repo', lambda: RepoFake())
    monkeypatch.setattr(ocr_review, 'RedmineAttachmentClient', ClientInvalid)
    monkeypatch.setattr(
        ocr_review,
        '_runtime_ocr',
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('OCR não deve receber anexo inválido')),
    )

    with pytest.raises(HTTPException) as exc:
        ocr_review.processar_anexos_redmine(
            42,
            ocr_review.OcrRedmineAttachmentsRequest(),
            user={'sub': 'admin'},
            x_correlation_id='corr-redmine-invalid',
        )

    assert exc.value.status_code == 422
    assert exc.value.detail['code'] == 'OCR_REDMINE_ATTACHMENTS_PARTIAL_FAILURE'
    assert exc.value.detail['data']['failed_count'] == 1
    assert exc.value.detail['data']['items'][0]['status'] == 'QUARENTENA'


def test_api_redmine_mapeia_fonte_indisponivel_para_502(monkeypatch):
    class BrokenClient:
        def __init__(self):
            raise RedmineAttachmentError('Redmine indisponível')

    monkeypatch.setenv('OCR_INPUT_ROOT', '/tmp/ocr-redmine')
    monkeypatch.setattr(ocr_review, 'RedmineAttachmentClient', BrokenClient)

    with pytest.raises(HTTPException) as exc:
        ocr_review.processar_anexos_redmine(
            42,
            ocr_review.OcrRedmineAttachmentsRequest(),
            user={'sub': 'admin'},
            x_correlation_id='corr-redmine-offline',
        )

    assert exc.value.status_code == 502
    assert exc.value.detail['code'] == 'OCR_REDMINE_SOURCE_UNAVAILABLE'
    assert exc.value.detail['correlation_id'] == 'corr-redmine-offline'
