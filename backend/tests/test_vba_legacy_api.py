from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from app.api.vba_legacy import analyze_vba_upload, vba_analyzer_readiness


def _arquivo(nome: str, conteudo: bytes) -> UploadFile:
    return UploadFile(
        file=BytesIO(conteudo),
        filename=nome,
        headers=Headers({'content-type': 'text/plain'}),
    )


async def test_upload_vba_retorna_envelope_com_correlation_id_e_sem_persistir_fonte():
    resposta = await analyze_vba_upload(
        arquivo=_arquivo('modTeste.bas', b'Sub X()\nIf A = 1 Then B = 2\nEnd Sub'),
        user={'papel': 'admin'},
        x_correlation_id='corr-vba-001',
    )

    assert resposta['success'] is True
    assert resposta['meta']['correlation_id'] == 'corr-vba-001'
    assert resposta['meta']['idempotent_analysis'] is True
    assert resposta['meta']['source_persisted'] is False
    assert resposta['data']['analysis_type'] == 'static_only'
    assert resposta['data']['execution_performed'] is False
    assert resposta['data']['summary']['requirement_candidates'] == 1


async def test_upload_cp1252_e_aceito():
    conteudo = 'Sub X()\nIf situação = "PENDENTE" Then ação = "ANALISAR"\nEnd Sub'.encode('cp1252')

    resposta = await analyze_vba_upload(
        arquivo=_arquivo('acentos.bas', conteudo),
        user={'papel': 'admin'},
        x_correlation_id=None,
    )

    assert resposta['success'] is True
    assert resposta['data']['summary']['business_rules'] == 1


async def test_conteiner_xlsm_e_bloqueado_com_proximo_incremento_explicito():
    with pytest.raises(HTTPException) as exc_info:
        await analyze_vba_upload(
            arquivo=_arquivo('legado.xlsm', b'PK\x03\x04'),
            user={'papel': 'admin'},
            x_correlation_id=None,
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail['code'] == 'VBA_BINARY_CONTAINER_NOT_SUPPORTED'
    assert 'vbaProject.bin' in exc_info.value.detail['next_increment']


async def test_limite_de_upload_e_configuravel_por_ambiente(monkeypatch):
    monkeypatch.setenv('VBA_ANALYZER_MAX_UPLOAD_BYTES', '10')

    with pytest.raises(HTTPException) as exc_info:
        await analyze_vba_upload(
            arquivo=_arquivo('grande.bas', b'01234567890'),
            user={'papel': 'admin'},
            x_correlation_id=None,
        )

    assert exc_info.value.status_code == 413
    assert exc_info.value.detail == {'code': 'VBA_SOURCE_TOO_LARGE', 'max_bytes': 10}


def test_readiness_deixa_claro_que_nao_executa_vba():
    resposta = vba_analyzer_readiness(user={'papel': 'admin'})

    assert resposta['success'] is True
    assert resposta['data']['ready'] is True
    assert resposta['data']['analysis_type'] == 'static_only'
    assert resposta['data']['execution_performed'] is False
    assert resposta['data']['binary_containers_supported'] is False
