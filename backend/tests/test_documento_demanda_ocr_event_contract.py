from app.ocr.documento_worker import EVENTO_OCR_DOCUMENTO_DEMANDA_SOLICITADO
from app.services.runtime_core import RuntimeEventEnvelope


def test_evento_ocr_documento_nao_exige_texto_no_payload():
    envelope = RuntimeEventEnvelope(
        event_type=EVENTO_OCR_DOCUMENTO_DEMANDA_SOLICITADO,
        source='api.documento_demanda',
        aggregate_type='documento_demanda_ocr',
        aggregate_id='42',
        correlation_id='corr-42',
        payload={'document_ref': 'abc.pdf', 'content_type': 'application/pdf'},
    )
    audit = envelope.to_audit_payload()
    assert audit['payload_minimo'] == {'document_ref': 'abc.pdf', 'content_type': 'application/pdf'}
    assert 'texto' not in audit['payload_minimo']
